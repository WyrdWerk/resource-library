#!/usr/bin/env python3
"""Phase 6: framework-light local API adapter (stdlib only).

Serves the static api/v1 artifacts plus live lexical search over the
canonical catalog. No framework, no database, no auth — GET/HEAD/OPTIONS
only. This adapter is for LOCAL contract verification; production serving
is a Cloudflare operator concern (see docs/runbook.md) and is NOT claimed
here.

Routes:
  GET  /api/v1/index.json
  GET  /api/v1/taxonomy.json
  GET  /api/v1/resources.json[?fields=&limit=&cursor=]
  GET  /api/v1/resources/<id>
  GET  /api/v1/search?q=&resource_type=&topic=&use_case=&interface=&
                       technology=&channel=&open_source=&sort=&limit=&
                       cursor=&fields=
HEAD and OPTIONS are supported on every route. ETag (sha256 of the exact
response body) + If-None-Match -> 304. CORS: Access-Control-Allow-Origin: *.

Usage: python3 scripts/api_server.py [port]   (default 8765)
"""
import hashlib
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from search import build_index, load_taxonomy, search

API = ROOT / "api" / "v1"
MAX_LIMIT = 100

_state = {}


def load_state():
    records = json.loads((API / "resources.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((API / "taxonomy.json").read_text(encoding="utf-8"))
    manifest = json.loads((API / "index.json").read_text(encoding="utf-8"))
    _state.update(records=records, by_id={r["id"]: r for r in records},
                  taxonomy=taxonomy, manifest=manifest,
                  index=build_index(records, load_taxonomy()),
                  facets=_facets(taxonomy))


def _facets(taxonomy):
    out = {}
    for name, key in (("resource-types", "resource_type"), ("topics", "topic"),
                      ("use-cases", "use_case"), ("interfaces", "interface"),
                      ("technologies", "technology")):
        out[key] = set(taxonomy[name]["values"].keys())
    out["channel"] = {"share-tech", "providers"}
    out["sort"] = {"relevance", "newest", "oldest"}
    return out


FIELD_ALLOW = {"schema_version", "id", "title", "canonical_url", "brief", "caveat",
               "resource_type", "topics", "use_cases", "interfaces", "technologies",
               "license", "open_source", "display_period", "legacy_categories",
               "source", "shared_on", "verification"}


def sparse(rec, fields):
    if not fields:
        return rec
    return {k: rec[k] for k in fields if k in rec}


def err(code, message, status):
    return status, {"error": {"code": code, "message": message}}


def parse_fields(qs):
    raw = qs.get("fields", [None])[0]
    if not raw:
        return None, None
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    bad = [f for f in fields if f not in FIELD_ALLOW]
    if bad:
        return None, err("bad_fields", f"unknown fields: {', '.join(bad)}", 400)
    return fields, None


def parse_limit_cursor(qs):
    try:
        limit = int(qs.get("limit", ["20"])[0])
    except ValueError:
        return None, None, err("bad_limit", "limit must be an integer", 400)
    if not 1 <= limit <= MAX_LIMIT:
        return None, None, err("bad_limit", f"limit must be 1..{MAX_LIMIT}", 400)
    return limit, qs.get("cursor", [None])[0], None


def paginate(ids, limit, cursor):
    start = 0
    if cursor:
        for i, rid in enumerate(ids):
            if rid == cursor:
                start = i + 1
                break
        else:
            return None, err("bad_cursor", "unknown cursor", 400)
    page = ids[start:start + limit]
    nxt = page[-1] if len(ids) > start + limit else None
    return (page, nxt), None


def route_search(qs):
    q = qs.get("q", [""])[0]
    filters = {}
    for key in ("resource_type", "topic", "use_case", "interface", "technology", "channel"):
        v = qs.get(key, [None])[0]
        if v:
            if v not in _state["facets"][key]:
                return err("bad_filter", f"unknown {key}: {v}", 400)
            filters[key] = v
    # `type` is accepted as an alias of resource_type
    if "type" in qs and "resource_type" not in filters:
        v = qs["type"][0]
        if v not in _state["facets"]["resource_type"]:
            return err("bad_filter", f"unknown resource_type: {v}", 400)
        filters["resource_type"] = v
    os_raw = qs.get("open_source", [None])[0]
    if os_raw is not None:
        if os_raw == "true":
            filters["open_source"] = True
        elif os_raw == "false":
            filters["open_source"] = False
        else:
            return err("bad_filter", "open_source must be true or false", 400)
    sort = qs.get("sort", ["relevance"])[0]
    if sort not in _state["facets"]["sort"]:
        return err("bad_sort", "sort must be relevance|newest|oldest", 400)
    fields, e = parse_fields(qs)
    if e:
        return e
    limit, cursor, e = parse_limit_cursor(qs)
    if e:
        return e
    page, nxt = search(_state["index"], q, filters, sort, limit, cursor)
    docs = _state["index"]["docs"]
    return 200, {"query": q, "filters": filters, "sort": sort, "limit": limit,
                 "results": [sparse(docs[rid]["record"], fields) for rid, _ in page],
                 "next_cursor": nxt}


def route(path, qs):
    if path == "/api/v1/index.json":
        return 200, _state["manifest"]
    if path == "/api/v1/taxonomy.json":
        return 200, _state["taxonomy"]
    if path == "/api/v1/resources.json":
        fields, e = parse_fields(qs)
        if e:
            return e
        limit, cursor, e = parse_limit_cursor(qs)
        if e:
            return e
        ids = [r["id"] for r in _state["records"]]
        res, e = paginate(ids, limit, cursor)
        if e:
            return e
        page, nxt = res
        return 200, {"records": [sparse(_state["by_id"][i], fields) for i in page],
                     "next_cursor": nxt, "total": len(ids)}
    if path.startswith("/api/v1/resources/"):
        rid = urllib.parse.unquote(path[len("/api/v1/resources/"):])
        rec = _state["by_id"].get(rid)
        if rec is None:
            return err("not_found", f"no resource {rid!r}", 404)
        fields, e = parse_fields(qs)
        if e:
            return e
        return 200, sparse(rec, fields)
    if path == "/api/v1/search":
        return route_search(qs)
    return err("not_found", f"no route {path!r}", 404)


class Handler(BaseHTTPRequestHandler):
    server_version = "ResourceLibraryAPI/1.0"

    def _send(self, status, payload, head_only=False):
        body = b"" if head_only else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        etag = hashlib.sha256(body if body else json.dumps(
            payload, ensure_ascii=False).encode("utf-8")).hexdigest()
        if self.headers.get("If-None-Match") == etag and status == 200:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "If-None-Match")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _handle(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            status, payload = route(parsed.path, qs)
        except Exception as exc:  # never leak a traceback; stay JSON
            status, payload = err("internal", "unexpected error", 500)
        self._send(status, payload, head_only)

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle(head_only=True)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "If-None-Match")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


def main():
    load_state()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"api v1 listening on 127.0.0.1:{port} ({len(_state['records'])} records)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
