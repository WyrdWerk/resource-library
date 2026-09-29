"""Phase 4 gate: canonical records round-trip to the exact legacy contract,
and the static api/v1 surface is well-formed.

The compatibility adapter is scripts/api_build.py::legacy_row. This test
re-derives every legacy row from the canonical catalog and requires
byte-level equality with data.json (the file scripts/build.py writes and
the site consumes). build.py itself is untouched.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from api_build import legacy_row

API = ROOT / "api" / "v1"


@pytest.fixture(scope="module")
def records():
    order = [r["id"] for r in json.loads((ROOT / "data.json").read_text(encoding="utf-8"))]
    recs = {}
    for p in (ROOT / "catalog" / "resources").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        recs[r["id"]] = r
    return [recs[i] for i in order]


def test_legacy_round_trip_is_exact(records):
    live = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    derived = [legacy_row(r) for r in records]
    assert len(derived) == len(live) == 285
    for d, l, rec in zip(derived, live, records):
        assert d == l, f"legacy row mismatch for {rec['id']}"


def test_legacy_key_order_matches_build_py(records):
    expected = ["title", "week", "url", "sharer", "date", "categories", "brief", "id", "warning"]
    assert list(legacy_row(records[0]).keys()) == expected


def test_api_artifacts_exist_and_parse():
    for name in ("resources.json", "taxonomy.json", "index.json", "_compat_report.json"):
        p = API / name
        assert p.exists(), name
        json.loads(p.read_text(encoding="utf-8"))


def test_api_resources_match_catalog(records):
    api_recs = json.loads((API / "resources.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in api_recs] == [r["id"] for r in records]
    assert api_recs == records


def test_api_manifest_is_consistent():
    manifest = json.loads((API / "index.json").read_text(encoding="utf-8"))
    assert manifest["api_version"] == "1"
    assert manifest["record_count"] == 285
    assert set(manifest["channels"]) == {"share-tech", "providers"}
    body = (API / "resources.json").read_bytes()
    assert manifest["resources_sha256"] == hashlib.sha256(body).hexdigest()


def test_compat_report_claims_hold():
    rep = json.loads((API / "_compat_report.json").read_text(encoding="utf-8"))
    assert rep["rows"] == 285
    assert rep["all_rows_equal"] is True
    assert rep["mismatched_ids"] == []
