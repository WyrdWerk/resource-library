#!/usr/bin/env python3
"""Phase 4: build the static API surface from the canonical catalog.

Reads:  catalog/resources/*.json (canonical records, canonical order)
        catalog/taxonomy/*.json (registries)
Writes: api/v1/resources.json   full canonical record array (canonical order)
        api/v1/taxonomy.json    flattened taxonomy registries + synonyms
        api/v1/facets.json      per-family facet values + corpus counts
        api/v1/index.json       manifest: version, counts, content hashes
        api/v1/_compat_report.json  proof that legacy rows round-trip

Determinism: records are emitted in canonical (data.json) order, which the
migrator preserves and the compat test verifies. Legacy site files
(index.html, data.json, weeks/, feed.xml, CHANGELOG.md, og-image.png) are
NEVER touched by this script — scripts/build.py remains their sole writer.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "catalog" / "resources"
TAX = ROOT / "catalog" / "taxonomy"
OUT = ROOT / "api" / "v1"


def load_records():
    # canonical order = data.json order (migrator guarantees, test asserts)
    order = [r["id"] for r in json.loads((ROOT / "data.json").read_text(encoding="utf-8"))]
    recs = {}
    for p in CAT.glob("*.json"):
        rec = json.loads(p.read_text(encoding="utf-8"))
        recs[rec["id"]] = rec
    missing = [i for i in order if i not in recs]
    extra = [i for i in recs if i not in order]
    assert not missing, f"catalog records missing for ids: {missing}"
    assert not extra, f"catalog records with no legacy row: {extra}"
    return [recs[i] for i in order]


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def facet_counts(records, tax):
    """Per-family facet value -> corpus count, matching the filter-param
    names of the API (resource_type, topic, use_case, interface, technology,
    channel, open_source). Every vocabulary value appears, count 0 if unused.
    Deterministic order: count desc, then slug asc. Facet families must
    satisfy schemas/exports.schema.json $defs.facets."""
    families = [
        ("resource_type", "resource-types", lambda r: [r["resource_type"]]),
        ("topic", "topics", lambda r: r["topics"]),
        ("use_case", "use-cases", lambda r: r["use_cases"]),
        ("interface", "interfaces", lambda r: r["interfaces"]),
        ("technology", "technologies", lambda r: r["technologies"]),
    ]
    out = {}
    for name, reg, get in families:
        counts = {slug: 0 for slug in tax[reg]["values"]}
        for r in records:
            for v in get(r):
                counts[v] = counts.get(v, 0) + 1
        out[name] = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    chan = {"share-tech": 0, "providers": 0}
    for r in records:
        chan[r["source"]["channel"]] += 1
    out["channel"] = dict(sorted(chan.items(), key=lambda kv: (-kv[1], kv[0])))
    out["open_source"] = {
        "true": sum(1 for r in records if r.get("open_source") is True),
        "false": sum(1 for r in records if r.get("open_source") is False),
    }
    return out


def legacy_row(rec):
    """Derive the exact legacy data.json row shape from a canonical record.

    Key order must match scripts/build.py exactly:
    title, week, url, sharer, date, categories, brief, id, warning, details.
    """
    shared = datetime.strptime(rec["shared_on"], "%Y-%m-%d").date()
    return {
        "title": rec["title"],
        "week": rec["display_period"],
        "url": rec["canonical_url"],
        "sharer": rec["source"]["sharer"],
        "date": f"{shared.day} {shared.strftime('%b')}",
        "categories": rec["legacy_categories"],
        "brief": rec["brief"],
        "id": rec["id"],
        "warning": rec["caveat"] or "",
        "details": rec.get("details") or "",
    }


def main():
    records = load_records()

    tax = {}
    for name in ("resource-types", "topics", "use-cases", "interfaces", "technologies", "synonyms"):
        tax[name] = json.loads((TAX / f"{name}.json").read_text(encoding="utf-8"))

    OUT.mkdir(parents=True, exist_ok=True)

    resources_text = json.dumps(records, indent=2, ensure_ascii=False)
    (OUT / "resources.json").write_text(resources_text, encoding="utf-8")
    (OUT / "taxonomy.json").write_text(
        json.dumps(tax, indent=2, ensure_ascii=False), encoding="utf-8")

    facets = facet_counts(records, tax)
    (OUT / "facets.json").write_text(
        json.dumps(facets, indent=2, ensure_ascii=False), encoding="utf-8")

    # compat proof: derived legacy rows must equal the live data.json rows
    live = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    derived = [legacy_row(r) for r in records]
    row_equal = [d == l for d, l in zip(derived, live)]
    compat = {
        "rows": len(records),
        "all_rows_equal": len(derived) == len(live) and all(row_equal),
        "mismatched_ids": [records[i]["id"] for i, ok in enumerate(row_equal) if not ok],
        "note": "derived via scripts.api_build.legacy_row vs data.json written by scripts/build.py",
    }
    (OUT / "_compat_report.json").write_text(
        json.dumps(compat, indent=2, ensure_ascii=False), encoding="utf-8")

    channels = sorted({r["source"]["channel"] for r in records})
    manifest = {
        "api_version": "1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(records),
        "channels": channels,
        "resources_sha256": sha256_text(resources_text),
        "endpoints": {
            "records": "api/v1/resources.json",
            "taxonomy": "api/v1/taxonomy.json",
            "facets": "api/v1/facets.json",
        },
    }
    (OUT / "index.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"api/v1: {len(records)} records | compat all_equal={compat['all_rows_equal']} "
          f"| mismatches={len(compat['mismatched_ids'])} | facets families={len(facets)}")
    return 0 if compat["all_rows_equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
