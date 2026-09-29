#!/usr/bin/env python3
"""Edge parity gate: compare the deployed Pages Functions (local wrangler
or a live preview URL) against scripts/api_server.py, request by request.

The JS engine in functions/api/v1/_lib.js is a port of scripts/search.py;
this script proves the port by replaying the 40-query gold set plus the
full local contract battery against both implementations and requiring
identical parsed JSON. It also asserts the edge-only HTTP behaviors the
Cloudflare handoff checklist requires (CORS, ETag/304, HEAD, OPTIONS,
405, static-asset routing).

Usage:
  python3 scripts/api_server.py 8765 &            # local adapter
  npx wrangler pages dev . --port 8788 &          # local edge
  python3 scripts/edge_parity.py --edge http://127.0.0.1:8788

Or against a real preview deployment:
  python3 scripts/edge_parity.py --edge https://<hash>.resource-library-7q4.pages.dev

Stdlib only. Exits 1 on any mismatch.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES = []
CHECKS = 0


def http(method, url, headers=None, timeout=30):
    # Cloudflare's bot filtering 403s the default "Python-urllib/x" UA
    hdrs = {"User-Agent": "resource-library-edge-parity/1.0"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def get_json(base, path, retries=2):
    for attempt in range(retries + 1):
        status, headers, body = http("GET", base.rstrip("/") + path)
        if status in (403, 429, 524) and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        break
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = {"_unparseable": body[:200].decode("utf-8", "replace"),
                  "_status": status, "_content_type": headers.get("Content-Type", "")}
    return status, headers, parsed


def check(label, ok, detail=""):
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}{(' :: ' + detail) if detail else ''}")
        FAILURES.append(label)


def diff_snippet(a, b):
    sa, sb = json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
    for i in range(min(len(sa), len(sb))):
        if sa[i] != sb[i]:
            return f"first divergence at char {i}: ...{sa[max(0, i-40):i+40]!r} vs ...{sb[max(0, i-40):i+40]!r}"
    return f"lengths differ ({len(sa)} vs {len(sb)})"


def compare(label, edge, adapter):
    check(label, edge == adapter, diff_snippet(edge, adapter) if edge != adapter else "")


def search_path(params):
    return "/api/v1/search?" + urllib.parse.urlencode(params)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", required=True, help="base URL of the edge (wrangler dev or preview)")
    ap.add_argument("--adapter", default="http://127.0.0.1:8765")
    ap.add_argument("--skip-static", action="store_true",
                    help="skip repo-file comparisons (use when running against a preview "
                         "whose static assets come from the same commit)")
    args = ap.parse_args()
    edge = args.edge.rstrip("/")
    adapter = args.adapter.rstrip("/")

    print(f"edge parity: {edge} vs adapter {adapter}")

    # --- 1. static assets are live and unshadowed -------------------------
    print("[static assets]")
    for path, repo_file in [
        ("/api/v1/index.json", "api/v1/index.json"),
        ("/api/v1/taxonomy.json", "api/v1/taxonomy.json"),
        ("/api/v1/resources.json", "api/v1/resources.json"),
    ]:
        status, _, body = http("GET", edge + path)
        check(f"GET {path} -> 200", status == 200, f"status {status}")
        if status == 200:
            edge_json = json.loads(body)
            if args.skip_static:
                check(f"{path} parses as JSON", isinstance(edge_json, (list, dict)))
            else:
                compare(f"{path} == repo file", edge_json,
                        json.loads((ROOT / repo_file).read_text(encoding="utf-8")))
    raw = http("GET", edge + "/api/v1/resources.json")
    check("static resources.json is the raw array (not the paginated object)",
          isinstance(json.loads(raw[2]), list) and len(json.loads(raw[2])) == 285)
    st_home, h_home, b_home = http("GET", edge + "/")
    check("GET / -> 200 HTML (functions do not shadow the site)",
          st_home == 200 and "html" in (h_home.get("Content-Type") or ""),
          f"status {st_home}, type {h_home.get('Content-Type')}")
    weeks = sorted((ROOT / "weeks").glob("*.md"))
    st_w, _, _ = http("GET", edge + "/weeks/" + weeks[0].name)
    check(f"GET /weeks/{weeks[0].name} -> 200", st_w == 200, f"status {st_w}")
    st_head, h_head, b_head = http("HEAD", edge + "/api/v1/index.json")
    check("HEAD /api/v1/index.json -> 200", st_head == 200, f"status {st_head}")
    st_lib, h_lib, b_lib = http("GET", edge + "/api/v1/_lib.js")
    check("GET /api/v1/_lib.js -> site fallback, helper module not routed/leaked",
          "text/html" in (h_lib.get("Content-Type") or "") and b"W_TITLE_TOKEN" not in b_lib,
          f"status {st_lib}, type {h_lib.get('Content-Type')}")
    st_bogus, h_bogus, _ = http("GET", edge + "/api/v1/bogus")
    check("GET /api/v1/bogus -> same as today's not-found behavior (site fallback)",
          "text/html" in (h_bogus.get("Content-Type") or ""), f"status {st_bogus}, type {h_bogus.get('Content-Type')}")

    # --- 2. gold query parity: edge == adapter -----------------------------
    print("[gold queries: search parity]")
    gold = json.loads((ROOT / "tests" / "gold_queries.json").read_text(encoding="utf-8"))
    for i, case in enumerate(gold):
        params = {"q": case["query"], "limit": "100"}
        for key, val in (case.get("filters") or {}).items():
            params[key] = "true" if val is True else "false" if val is False else val
        path = search_path(params)
        se, _, pe = get_json(edge, path)
        sa, _, pa = get_json(adapter, path)
        ok = (se == sa == 200) and pe == pa
        check(f"gold[{i}] {case['query']!r}" + (f" {case.get('filters')}" if case.get("filters") else ""),
              ok, diff_snippet(pe, pa) if pe != pa else f"status edge={se} adapter={sa}")
        if ok and not case.get("expect_none") and case.get("expect_top1"):
            check(f"gold[{i}] top-1 == {case['expect_top1']}",
                  pe["results"] and pe["results"][0]["id"] == case["expect_top1"])

    # --- 3. contract battery ------------------------------------------------
    print("[collection: /api/v1/resources (edge) vs /api/v1/resources.json (adapter)]")

    def both(path_edge, path_adapter, label):
        se, _, pe = get_json(edge, path_edge)
        sa, _, pa = get_json(adapter, path_adapter)
        ok = (se == sa) and pe == pa
        check(label, ok, diff_snippet(pe, pa) if pe != pa else f"status edge={se} adapter={sa}")
        return se, pe

    se, pe = both("/api/v1/resources", "/api/v1/resources.json", "default page")
    check("default page: 20 records of 285", pe.get("total") == 285 and len(pe.get("records", [])) == 20)
    both("/api/v1/resources?limit=5", "/api/v1/resources.json?limit=5", "limit=5")
    both("/api/v1/resources?fields=id,title", "/api/v1/resources.json?fields=id,title", "sparse fields")
    both("/api/v1/resources?fields=id,nope", "/api/v1/resources.json?fields=id,nope", "bad fields -> 400")
    both("/api/v1/resources?limit=abc", "/api/v1/resources.json?limit=abc", "bad limit -> 400")
    both("/api/v1/resources?limit=500", "/api/v1/resources.json?limit=500", "limit=500 -> 400")
    both("/api/v1/resources?cursor=bogus", "/api/v1/resources.json?cursor=bogus", "bad cursor -> 400")

    # cursor walk: three pages, no overlap, identical to adapter pages
    seen_ids, cursors = [], None
    for page_no in range(3):
        q = "/api/v1/resources?limit=5" + (f"&cursor={urllib.parse.quote(cursors)}" if cursors else "")
        se, pe = both(q, q.replace("/resources?", "/resources.json?"), f"cursor walk page {page_no + 1}")
        ids = [r["id"] for r in pe["records"]]
        check(f"cursor walk page {page_no + 1}: no overlap",
              not (set(ids) & set(seen_ids)))
        seen_ids += ids
        cursors = pe["next_cursor"]
    check("cursor walk advanced", cursors is not None)

    print("[single record: /api/v1/resources/{id}]")
    both("/api/v1/resources/openrouter", "/api/v1/resources/openrouter", "openrouter")
    both("/api/v1/resources/no-such-id", "/api/v1/resources/no-such-id", "404 unknown id")
    both("/api/v1/resources/no-such-id?fields=nope", "/api/v1/resources/no-such-id?fields=nope",
         "404 wins over bad fields")
    both("/api/v1/resources/openrouter?fields=id,title", "/api/v1/resources/openrouter?fields=id,title",
         "sparse fields")

    print("[search contract]")
    cases = [
        ("empty q + filter", search_path({"topic": "frontend"})),
        ("domain-style q", search_path({"q": "openrouter.com"})),
        ("phrase q", search_path({"q": "open source react components"})),
        ("no results", search_path({"q": "zzzzqqqjjj"})),
        ("filter", search_path({"q": "inference", "resource_type": "provider", "limit": "50"})),
        ("type alias", search_path({"q": "tool", "type": "provider"})),
        ("explicit type", search_path({"q": "tool", "resource_type": "provider"})),
        ("open_source=true", search_path({"q": "model", "open_source": "true"})),
        ("open_source=bogus", search_path({"q": "model", "open_source": "maybe"})),
        ("bad filter", search_path({"resource_type": "bogus"})),
        ("bad sort", search_path({"q": "x", "sort": "bogus"})),
        ("bad limit", search_path({"q": "x", "limit": "500"})),
        ("bad fields", search_path({"q": "x", "fields": "id,nope"})),
        ("blank limit falls back to default", search_path({"q": "x", "limit": ""})),
        ("newest sort", search_path({"q": "agent", "sort": "newest", "limit": "10"})),
        ("oldest sort", search_path({"q": "agent", "sort": "oldest", "limit": "10"})),
    ]
    for label, path in cases:
        both(path, path, f"search {label}")

    # sort=newest cursor walk must be stable and adapter-identical
    seen, cursors = [], None
    for page_no in range(2):
        params = {"q": "agent", "sort": "newest", "limit": "10"}
        if cursors:
            params["cursor"] = cursors
        path = search_path(params)
        se, pe = both(path, path, f"search newest walk page {page_no + 1}")
        ids = [r["id"] for r in pe["results"]]
        check(f"search newest walk page {page_no + 1}: no overlap", not (set(ids) & set(seen)))
        seen += ids
        cursors = pe["next_cursor"]

    # --- 4. edge-only HTTP behaviors ---------------------------------------
    print("[edge HTTP behavior]")
    st, hdrs, body = http("GET", edge + search_path({"q": "openrouter"}))
    check("search: 200", st == 200)
    check("search: Access-Control-Allow-Origin: *", hdrs.get("Access-Control-Allow-Origin") == "*")
    check("search: JSON content type", "application/json" in (hdrs.get("Content-Type") or ""))
    check("search: Cache-Control public max-age=60", "max-age=60" in (hdrs.get("Cache-Control") or ""),
          str(hdrs.get("Cache-Control")))
    etag = hdrs.get("ETag")
    check("search: ETag present", bool(etag))
    check("search: Last-Modified present", bool(hdrs.get("Last-Modified")))
    st304, h304, b304 = http("GET", edge + search_path({"q": "openrouter"}),
                             headers={"If-None-Match": etag or "x"})
    check("search: If-None-Match -> 304", st304 == 304 and b304 == b"", f"status {st304}")
    check("search: 304 keeps ETag + CORS",
          h304.get("ETag") == etag and h304.get("Access-Control-Allow-Origin") == "*")
    stH, hH, bH = http("HEAD", edge + search_path({"q": "openrouter"}))
    check("search: HEAD -> 200, no body, ETag kept", stH == 200 and bH == b"" and bool(hH.get("ETag")),
          f"status {stH}, body {len(bH)}B")
    stO, hO, _ = http("OPTIONS", edge + "/api/v1/search")
    check("search: OPTIONS -> 204 + CORS", stO == 204 and hO.get("Access-Control-Allow-Origin") == "*",
          f"status {stO}")
    for method in ("POST", "PUT", "DELETE"):
        stM, hM, bM = http(method, edge + "/api/v1/search")
        code = (json.loads(bM) or {}).get("error", {}).get("code")
        check(f"search: {method} -> 405 method_not_allowed",
              stM == 405 and code == "method_not_allowed", f"status {stM}, code {code}")
    stM, _, bM = http("POST", edge + "/api/v1/resources/openrouter")
    check("resource: POST -> 405 method_not_allowed", stM == 405)

    # timing sanity (single warm request, informational)
    t0 = time.time()
    http("GET", edge + search_path({"q": "openrouter"}))
    print(f"  info  one warm search round-trip: {1000 * (time.time() - t0):.0f} ms")

    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL PARITY CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
