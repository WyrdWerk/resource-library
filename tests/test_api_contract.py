"""Phase 6 gate: local API contract tests (no Cloudflare, no network).

Spins up scripts/api_server.py on 127.0.0.1 and verifies routes, filters,
sparse fields, pagination, errors, CORS, and ETag/304 behavior against the
contract in api/openapi.yaml. Static catalog remains usable with the
adapter disabled (test_static_files_usable).
"""
import http.client
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765


@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "api_server.py"), str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=2)
            c.request("GET", "/api/v1/index.json")
            if c.getresponse().status == 200:
                break
        except OSError:
            time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("api_server did not start")
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


def req(method, path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    c.request(method, path, headers=headers or {})
    r = c.getresponse()
    body = r.read()
    return r.status, dict(r.getheaders()), json.loads(body) if body else None


def test_index_manifest(server):
    s, _, b = req("GET", "/api/v1/index.json")
    assert s == 200
    assert b["api_version"] == "1" and b["record_count"] == 285


def test_taxonomy(server):
    s, _, b = req("GET", "/api/v1/taxonomy.json")
    assert s == 200
    assert "resource-types" in b and "synonyms" in b


def test_collection_pagination(server):
    s, _, b = req("GET", "/api/v1/resources.json?limit=5")
    assert s == 200 and b["total"] == 285 and len(b["records"]) == 5
    cur = b["next_cursor"]
    s, _, b2 = req("GET", f"/api/v1/resources.json?limit=5&cursor={cur}")
    ids1 = [r["id"] for r in b["records"]]
    ids2 = [r["id"] for r in b2["records"]]
    assert not set(ids1) & set(ids2)


def test_single_record(server):
    s, _, b = req("GET", "/api/v1/resources/openrouter")
    assert s == 200 and b["id"] == "openrouter" and b["resource_type"] == "provider"


def test_single_record_404(server):
    s, _, b = req("GET", "/api/v1/resources/no-such-id")
    assert s == 404 and b["error"]["code"] == "not_found"


def test_search_exact_id(server):
    s, _, b = req("GET", "/api/v1/search?q=openrouter")
    assert s == 200 and b["results"][0]["id"] == "openrouter"


def test_search_no_results(server):
    s, _, b = req("GET", "/api/v1/search?q=zzzzqqqjjj")
    assert s == 200 and b["results"] == []


def test_search_filters(server):
    s, _, b = req("GET", "/api/v1/search?q=inference&resource_type=provider&limit=50")
    assert s == 200
    assert all(r["resource_type"] == "provider" for r in b["results"])


def test_search_bad_filter_400(server):
    s, _, b = req("GET", "/api/v1/search?resource_type=bogus")
    assert s == 400 and b["error"]["code"] == "bad_filter"


def test_search_bad_limit_400(server):
    s, _, b = req("GET", "/api/v1/search?q=x&limit=500")
    assert s == 400


def test_sparse_fields(server):
    s, _, b = req("GET", "/api/v1/resources/openrouter?fields=id,title")
    assert s == 200 and set(b.keys()) == {"id", "title"}


def test_sparse_fields_bad_400(server):
    s, _, b = req("GET", "/api/v1/resources/openrouter?fields=id,nope")
    assert s == 400 and b["error"]["code"] == "bad_fields"


def test_head(server):
    s, h, b = req("HEAD", "/api/v1/index.json")
    assert s == 200 and b is None and "ETag" in h


def test_etag_304(server):
    s, h, _ = req("GET", "/api/v1/index.json")
    etag = h["ETag"]
    s2, _, b2 = req("GET", "/api/v1/index.json", {"If-None-Match": etag})
    assert s2 == 304 and b2 is None


def test_options_cors(server):
    s, h, _ = req("OPTIONS", "/api/v1/search")
    assert s == 204
    assert h["Access-Control-Allow-Origin"] == "*"


def test_unknown_route_404(server):
    s, _, b = req("GET", "/api/v1/bogus")
    assert s == 404


def test_static_files_usable():
    """The static catalog must not depend on the adapter."""
    recs = json.loads((ROOT / "api" / "v1" / "resources.json").read_text(encoding="utf-8"))
    assert len(recs) == 285 and recs[0]["id"]
