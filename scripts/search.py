#!/usr/bin/env python3
"""Phase 5: deterministic lexical search over the canonical catalog.

No embeddings, no external services. Scoring is a fixed weighted sum over
explicitly defined signals, so results are byte-reproducible for the same
catalog + taxonomy.

Index:  per-record token multisets (title, brief, taxonomy labels, curated
        aliases/synonyms) + corpus idf, all derived from catalog files.
Query:  exact-ID match and normalized-URL match short-circuit to rank 1;
        otherwise score = Σ weight(field) * Σ idf(token) over matched tokens,
        plus exact-phrase bonuses. Ties break by id (ascending).

Filters: resource_type, topic, use_case, interface, technology, channel,
         open_source. Each facet family accepts a single value or a list
         (CSV at the HTTP layer) — multiple values OR within the family,
         families AND together. Date bounds: from/to are inclusive
         YYYY-MM-DD filters on shared_on.
Sort: relevance | newest | oldest | title. Pagination: stable cursor
         over (sort-key, id) — same input always yields same pages.

CLI: python3 scripts/search.py "open source react components" --type library-framework --limit 10
"""
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# field weights — fixed, documented, versioned with the module
W_TITLE_TOKEN = 5.0
W_TITLE_PHRASE = 8.0
W_BRIEF_TOKEN = 2.0
W_BRIEF_PHRASE = 4.0
W_TAX_LABEL = 3.0     # resource-type / topic / use-case / interface / technology labels
W_ALIAS = 3.0         # curated synonym -> slug expansions

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)?")
STOP = frozenset("""
a an the and or of to in on for with by from as at is are was were be been
it its this that these those you your we our they their he she his her
with without into over under between through during each other more most
very can will just than then so such no not only own same too s t d ll m re ve
com org net www http https html
""".split())


def _stem_variants(t):
    """Deterministic light stemming: emit variant forms so morphological
    variants meet (generation/generator/generates, models/model,
    hosted/hosting/host). Applied symmetrically to index and query tokens,
    so it can only conflate forms that share these suffixes."""
    v = set()
    if len(t) > 6 and t.endswith("ation"):
        v.add(t[:-5] + "ate")          # generation -> generate
    if len(t) > 5 and t.endswith("ator"):
        v.add(t[:-4] + "ate")          # generator -> generate
    if len(t) > 5 and t.endswith("ing"):
        s = t[:-3]
        if len(s) >= 3 and s[-1] == s[-2]:
            s = s[:-1]                 # running -> run
        v.add(s)
    if len(t) > 4 and t.endswith("ed"):
        s = t[:-2]
        if len(s) >= 3 and s[-1] == s[-2]:
            s = s[:-1]
        v.add(s)                       # hosted -> host
    if len(t) > 4 and t.endswith("es"):
        v.add(t[:-2])                  # watches -> watch
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        v.add(t[:-1])                  # models -> model
    return {s for s in v if len(s) > 2 and s != t}


def tokenize(text):
    toks = []
    for t in TOKEN_RE.findall((text or "").lower()):
        t = t.strip("._-")
        if t and t not in STOP and len(t) > 1:
            toks.append(t)
            toks.extend(sorted(_stem_variants(t)))
    return toks


def norm_url(u):
    u = (u or "").lower().strip()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


def load_taxonomy():
    tax = {}
    base = ROOT / "catalog" / "taxonomy"
    for name in ("resource-types", "topics", "use-cases", "interfaces", "technologies"):
        tax[name] = json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
    tax["synonyms"] = json.loads((base / "synonyms.json").read_text(encoding="utf-8"))
    return tax


def slug_labels(tax):
    """slug -> set of label+alias tokens across all registries."""
    out = {}
    for reg in ("resource-types", "topics", "use-cases", "interfaces", "technologies"):
        for slug, entry in tax[reg]["values"].items():
            toks = tokenize(entry.get("label", ""))
            for a in entry.get("aliases", []):
                toks += tokenize(a)
            out.setdefault(slug, set()).update(toks)
    return out


def build_index(records, tax=None):
    tax = tax or load_taxonomy()
    labels = slug_labels(tax)
    # invert curated synonyms: slug -> alias tokens
    slug_aliases = {}
    for alias, slug in tax["synonyms"]["synonyms"].items():
        slug_aliases.setdefault(slug, set()).update(tokenize(alias))

    docs = {}
    df = Counter()
    for r in records:
        rid = r["id"]
        title_toks = tokenize(r["title"])
        brief_toks = tokenize(r["brief"] or "")
        tax_toks = []
        for s in [r["resource_type"]] + r["topics"] + r["use_cases"] + r["interfaces"] + r["technologies"]:
            tax_toks += sorted(labels.get(s, ()))
            tax_toks += sorted(slug_aliases.get(s, ()))
        alias_toks = []
        docs[rid] = {
            "title": Counter(title_toks),
            "brief": Counter(brief_toks),
            "tax": Counter(tax_toks),
            "alias": Counter(alias_toks),
            "title_text": r["title"].lower(),
            "brief_text": (r["brief"] or "").lower(),
            "url": norm_url(r["canonical_url"]),
            "record": r,
        }
        for t in set(title_toks) | set(brief_toks) | set(tax_toks):
            df[t] += 1
    n = len(records)
    idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
    return {"docs": docs, "idf": idf, "n": n}


def _aslist(v):
    """Facet filter values may be a single slug or a CSV-parsed list."""
    return v if isinstance(v, list) else [v]


def _matches_filters(r, f):
    if not f:
        return True
    if f.get("resource_type") and r["resource_type"] not in _aslist(f["resource_type"]):
        return False
    if f.get("topic") and not any(t in r["topics"] for t in _aslist(f["topic"])):
        return False
    if f.get("use_case") and not any(t in r["use_cases"] for t in _aslist(f["use_case"])):
        return False
    if f.get("interface") and not any(t in r["interfaces"] for t in _aslist(f["interface"])):
        return False
    if f.get("technology") and not any(t in r["technologies"] for t in _aslist(f["technology"])):
        return False
    if f.get("channel") and r["source"]["channel"] not in _aslist(f["channel"]):
        return False
    if f.get("open_source") is not None and bool(r["open_source"]) != f["open_source"]:
        return False
    # inclusive date bounds on shared_on (ISO strings compare lexically)
    if f.get("from") and r["shared_on"] < f["from"]:
        return False
    if f.get("to") and r["shared_on"] > f["to"]:
        return False
    return True


def search(index, query, filters=None, sort="relevance", limit=20, cursor=None):
    """Return (results, next_cursor). results = [(id, score), ...]."""
    docs, idf = index["docs"], index["idf"]
    q = (query or "").strip()
    ql = q.lower()
    qtoks = tokenize(q)
    if "." in q:
        # domain-style queries ("openrouter.com"): also try dots as separators
        for t in tokenize(q.replace(".", " ")):
            if t not in qtoks:
                qtoks.append(t)
    scored = []

    # exact id / url short-circuit: rank 1 with a fixed top score
    if ql:
        for rid, d in docs.items():
            if rid == ql or d["url"] == norm_url(q):
                r = d["record"]
                if _matches_filters(r, filters):
                    scored = [(rid, 1e9)]
                break

    if not scored and qtoks:
        for rid, d in docs.items():
            r = d["record"]
            if not _matches_filters(r, filters):
                continue
            s = 0.0
            for t in qtoks:
                w = idf.get(t, 0.0)
                if not w:
                    continue
                s += W_TITLE_TOKEN * w * min(d["title"].get(t, 0), 3)
                s += W_BRIEF_TOKEN * w * min(d["brief"].get(t, 0), 3)
                s += W_TAX_LABEL * w * min(d["tax"].get(t, 0), 2)
                s += W_ALIAS * w * min(d["alias"].get(t, 0), 2)
            if len(qtoks) > 1:
                if ql in d["title_text"]:
                    s += W_TITLE_PHRASE
                elif ql in d["brief_text"]:
                    s += W_BRIEF_PHRASE
            if s > 0:
                scored.append((rid, s))

    if sort == "newest":
        scored.sort(key=lambda x: (docs[x[0]]["record"]["shared_on"], x[0]), reverse=True)
        scored = [(rid, 0.0) for rid, _ in scored] if not qtoks else scored
        if qtoks:
            scored.sort(key=lambda x: (-x[1], docs[x[0]]["record"]["shared_on"], x[0]), reverse=False)
            scored.sort(key=lambda x: (docs[x[0]]["record"]["shared_on"], x[0]), reverse=True)
    elif sort == "oldest":
        scored.sort(key=lambda x: (docs[x[0]]["record"]["shared_on"], x[0]))
    elif sort == "title":
        scored.sort(key=lambda x: (docs[x[0]]["record"]["title"].lower(), x[0]))
    else:  # relevance
        scored.sort(key=lambda x: (-x[1], x[0]))

    # stable cursor: "<sort-key-of-last>::<id>"
    start = 0
    if cursor:
        for i, (rid, _) in enumerate(scored):
            if rid == cursor:
                start = i + 1
                break
    page = scored[start:start + limit]
    next_cursor = page[-1][0] if len(scored) > start + limit else None
    return page, next_cursor


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--type", dest="resource_type")
    ap.add_argument("--topic")
    ap.add_argument("--use-case", dest="use_case")
    ap.add_argument("--interface", dest="interface")
    ap.add_argument("--technology")
    ap.add_argument("--channel")
    ap.add_argument("--open-source", dest="open_source", action="store_true")
    ap.add_argument("--from", dest="date_from",
                    help="inclusive YYYY-MM-DD lower bound on shared_on")
    ap.add_argument("--to", dest="date_to",
                    help="inclusive YYYY-MM-DD upper bound on shared_on")
    ap.add_argument("--sort", default="relevance", choices=["relevance", "newest", "oldest", "title"])
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args(argv)

    records = json.loads((ROOT / "api" / "v1" / "resources.json").read_text(encoding="utf-8"))
    index = build_index(records)
    filters = {k: v for k, v in {
        "resource_type": args.resource_type, "topic": args.topic,
        "use_case": args.use_case, "interface": args.interface,
        "technology": args.technology, "channel": args.channel,
        "open_source": True if args.open_source else None,
        "from": args.date_from, "to": args.date_to}.items() if v is not None}
    page, nxt = search(index, args.query, filters, args.sort, args.limit)
    for rid, score in page:
        r = index["docs"][rid]["record"]
        print(f"{score:10.2f}  {rid}  [{r['resource_type']}] {r['title']}")
    if nxt:
        print(f"-- more -- cursor={nxt}")


if __name__ == "__main__":
    main(sys.argv[1:])
