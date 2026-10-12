"""Phase 3 gate: the one-time migration produced a complete, faithful catalog.

Evidence files under test (committed, deterministic):
  catalog/resources/<id>.json   canonical records
  catalog/_migration_report.json per-field old/new comparison + date evidence
  catalog/_exceptions.json       must be [] — blocked rows abort loudly
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "catalog" / "resources"
# Record count comes from the baseline (refreshed by scripts/regen.py), never a
# literal: hard-coded counts made every parallel resource PR conflict here.
TOTAL = json.loads((ROOT / "tests" / "manifest.baseline.json").read_text())["inventory"]["total"]
PROV_START = date(2026, 7, 20)
# Upper bound is "not in the future" (+1 day: IST runs ahead of UTC CI), never a
# literal: hard-coded end dates made every daily PR edit this file and conflict.
LATEST = date.today() + timedelta(days=1)


@pytest.fixture(scope="module")
def rows():
    return json.loads((ROOT / "data.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records(rows):
    recs = {}
    for p in CAT.glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        recs[r["id"]] = r
    return recs


def test_catalog_covers_every_legacy_row(rows, records):
    ids = [r["id"] for r in rows]
    assert len(records) == len(rows) == TOTAL
    assert sorted(records) == sorted(ids)


def test_canonical_order_matches_legacy(rows):
    ordered = [json.loads((CAT / f"{r['id']}.json").read_text())["id"] for r in rows]
    assert ordered == [r["id"] for r in rows]


def test_protected_fields_preserved(rows, records):
    for row in rows:
        rec = records[row["id"]]
        assert rec["id"] == row["id"]
        assert rec["title"] == row["title"]
        assert rec["canonical_url"] == row["url"]
        assert rec["brief"] == row["brief"]
        assert (rec["caveat"] or "") == row["warning"]
        assert rec["source"]["sharer"] == row["sharer"]
        assert rec["display_period"] == row["week"]
        assert rec["legacy_categories"] == row["categories"]
        assert rec["source"]["channel"] == (
            "providers" if row["week"] == "providers" else "share-tech")


def test_shared_on_dates_are_real_and_evidenced(rows, records):
    for row in rows:
        rec = records[row["id"]]
        iso = rec["shared_on"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso), row["id"]
        dt = date.fromisoformat(iso)
        if rec["source"]["channel"] == "providers":
            # #providers backfill starts 2026-07-20 (raw/providers_2026-07-20_to_2026-09-25.md);
            # daily runs extend it
            assert PROV_START <= dt <= LATEST, row["id"]
        else:
            # share-tech collection is ongoing (daily since 2026-09-26); in-week
            # containment is proven per-row by the migration report
            assert date(2026, 6, 1) <= dt <= LATEST, row["id"]


def test_exceptions_file_is_empty():
    exc = json.loads((ROOT / "catalog" / "_exceptions.json").read_text(encoding="utf-8"))
    assert exc == []


def test_migration_report_claims_hold():
    rep = json.loads((ROOT / "catalog" / "_migration_report.json").read_text(encoding="utf-8"))
    assert rep["migrated"] == rep["source_rows"] == TOTAL
    assert rep["order_preserved"] is True
    assert rep["all_fields_equal"] is True
    assert all(r["all_equal"] for r in rep["rows"])
    assert all(r["date_evidence"] for r in rep["rows"])
