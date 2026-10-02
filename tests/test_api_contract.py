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
    assert b["api_version"] == "1" and b["record_count"] == 291


def test_taxonomy(server):
    s, _, b = req("GET", "/api/v1/taxonomy.json")
    assert s == 200
    assert "resource-types" in b and "synonyms" in b


def test_collection_pagination(server):
    s, _, b = req("GET", "/api/v1/resources.json?limit=5")
    assert s == 200 and b["total"] == 291 and len(b["records"]) == 5
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
    assert len(recs) == 291 and recs[0]["id"]


def test_facets_json(server):
    s, _, b = req("GET", "/api/v1/facets.json")
    assert s == 200
    assert b["topic"]["ai-agents"] == 123
    assert b["resource_type"]["provider"] == 72
    assert sum(b["channel"].values()) == 291
    assert set(b) == {"resource_type", "topic", "use_case", "interface",
                      "technology", "channel", "open_source"}


def test_facets_json_matches_catalog():
    """Independent recount from resources.json must reproduce facets.json."""
    facets = json.loads((ROOT / "api" / "v1" / "facets.json").read_text(encoding="utf-8"))
    recs = json.loads((ROOT / "api" / "v1" / "resources.json").read_text(encoding="utf-8"))
    assert facets["channel"] == {
        "share-tech": sum(1 for r in recs if r["source"]["channel"] == "share-tech"),
        "providers": sum(1 for r in recs if r["source"]["channel"] == "providers")}
    assert facets["topic"]["inference"] == sum("inference" in r["topics"] for r in recs)
    assert facets["open_source"]["true"] == sum(r.get("open_source") is True for r in recs)


def test_search_sort_title(server):
    s, _, b = req("GET", "/api/v1/search?q=inference&sort=title&limit=50")
    assert s == 200
    titles = [r["title"].lower() for r in b["results"]]
    assert titles == sorted(titles)
    assert b["sort"] == "title"


def test_search_sort_title_cursor_stable(server):
    s, _, p1 = req("GET", "/api/v1/search?q=inference&sort=title&limit=10")
    cur = p1["next_cursor"]
    s, _, p2 = req("GET", f"/api/v1/search?q=inference&sort=title&limit=10&cursor={cur}")
    assert s == 200
    ids1 = {r["id"] for r in p1["results"]}
    ids2 = {r["id"] for r in p2["results"]}
    assert not ids1 & ids2


def test_search_csv_filter_ors_within_family(server):
    s, _, both = req("GET", "/api/v1/search?q=tool&topic=frontend,design&limit=100")
    assert s == 200
    assert both["filters"]["topic"] == ["frontend", "design"]
    assert all({"frontend", "design"} & set(r["topics"]) for r in both["results"])
    _, _, a = req("GET", "/api/v1/search?q=tool&topic=frontend&limit=100")
    _, _, d = req("GET", "/api/v1/search?q=tool&topic=design&limit=100")
    union = {r["id"] for r in a["results"]} | {r["id"] for r in d["results"]}
    assert {r["id"] for r in both["results"]} == union


def test_search_csv_single_value_keeps_string_echo(server):
    s, _, b = req("GET", "/api/v1/search?q=tool&topic=frontend&limit=5")
    assert s == 200 and b["filters"]["topic"] == "frontend"


def test_search_csv_unknown_value_400(server):
    s, _, b = req("GET", "/api/v1/search?topic=frontend,bogus")
    assert s == 400 and b["error"]["code"] == "bad_filter"
    assert "bogus" in b["error"]["message"]


def test_search_bad_sort_message_lists_title(server):
    s, _, b = req("GET", "/api/v1/search?q=x&sort=bogus")
    assert s == 400 and b["error"]["code"] == "bad_sort"
    assert "title" in b["error"]["message"]


def test_search_from_bound_narrows(server):
    s, _, bounded = req("GET", "/api/v1/search?q=inference&from=2026-09-01&limit=100")
    assert s == 200
    assert bounded["filters"]["from"] == "2026-09-01"
    assert all(r["shared_on"] >= "2026-09-01" for r in bounded["results"])
    s, _, unbounded = req("GET", "/api/v1/search?q=inference&limit=100")
    assert len(bounded["results"]) < len(unbounded["results"]), "bound must actually narrow"


def test_search_to_bound_excludes_newer(server):
    s, _, b = req("GET", "/api/v1/search?q=inference&to=2026-06-30&limit=100")
    assert s == 200
    assert all(r["shared_on"] <= "2026-06-30" for r in b["results"])


def test_search_bad_date_400(server):
    for bad in ("2026-02-30", "2026-9-1", "not-a-date", "20260901"):
        s, _, b = req("GET", f"/api/v1/search?q=x&from={bad}")
        assert s == 400, bad
        assert b["error"]["code"] == "bad_filter"
        assert "invalid from" in b["error"]["message"], bad
    s, _, b = req("GET", "/api/v1/search?q=x&to=2026-13-01")
    assert s == 400 and "invalid to" in b["error"]["message"]


def test_search_from_after_to_400(server):
    s, _, b = req("GET", "/api/v1/search?q=x&from=2026-09-29&to=2026-06-09")
    assert s == 400 and b["error"]["code"] == "bad_filter"
    assert b["error"]["message"] == "from must be <= to"


def test_search_date_bound_applies_to_exact_id(server):
    s, _, b = req("GET", "/api/v1/search?q=openrouter&from=2099-01-01")
    assert s == 200 and b["results"] == []
