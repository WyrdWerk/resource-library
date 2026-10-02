"""Phase 5 gate: deterministic lexical search meets its precision bars.

Gold set: tests/gold_queries.json — 40 queries reviewed 2026-09-29 against
the 285-record catalog. Gates (from the evidence-gated plan):
  - exact-ID queries rank the ID top-1 (100%)
  - >=90% of queries have all expected ids inside the top-5
  - no-result queries return nothing
Also: pagination cursors are stable and deterministic.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from search import build_index, load_taxonomy, search


@pytest.fixture(scope="module")
def index():
    records = json.loads((ROOT / "api" / "v1" / "resources.json").read_text(encoding="utf-8"))
    return build_index(records, load_taxonomy())


@pytest.fixture(scope="module")
def gold():
    return json.loads((ROOT / "tests" / "gold_queries.json").read_text(encoding="utf-8"))


def run(index, entry, limit=5):
    page, nxt = search(index, entry["query"], entry["filters"], limit=limit)
    return [rid for rid, _ in page], nxt


def test_gold_count(gold):
    assert len(gold) == 40


def test_exact_id_top1(index, gold):
    id_queries = [g for g in gold if g["query"] in
                  ("openrouter", "tokenwatch", "privacywatch", "deepseek-clock",
                   "saving-100tb-of-ram-with-math", "OpenRouter", "TokenWatch")]
    assert len(id_queries) == 7
    for g in id_queries:
        top, _ = run(index, g, limit=3)
        assert top[0] == g["expect_top1"], g["query"]


def test_top5_precision(index, gold):
    hits, total = 0, 0
    misses = []
    for g in gold:
        if g["expect_none"] or not g["expect_top5"]:
            continue
        total += 1
        top, _ = run(index, g, limit=5)
        if all(e in top for e in g["expect_top5"]):
            hits += 1
        else:
            misses.append((g["query"], g["expect_top5"], top))
    precision = hits / total
    print(f"\ntop-5 precision: {hits}/{total} = {precision:.1%}")
    assert precision >= 0.90, f"misses: {misses}"


def test_no_result_queries(index, gold):
    for g in gold:
        if not g["expect_none"]:
            continue
        top, _ = run(index, g)
        assert top == [], g["query"]


def test_expected_top1(index, gold):
    for g in gold:
        if g["expect_none"] or not g["expect_top1"]:
            continue
        top, _ = run(index, g, limit=5)
        assert top[0] == g["expect_top1"], (g["query"], top)


def test_pagination_is_stable(index):
    seen = []
    cursor = None
    for _ in range(30):
        page, cursor = search(index, "inference", limit=10, cursor=cursor)
        seen.extend(rid for rid, _ in page)
        if cursor is None:
            break
    assert len(seen) == len(set(seen)), "cursor pages must not repeat ids"
    # same query twice -> identical pages
    p1, _ = search(index, "inference", limit=10)
    p2, _ = search(index, "inference", limit=10)
    assert p1 == p2


def test_filters_narrow_results(index):
    page_all, _ = search(index, "inference", limit=50)
    page_f, _ = search(index, "inference", {"resource_type": "provider"}, limit=50)
    assert len(page_f) <= len(page_all)
    docs = index["docs"]
    assert all(docs[rid]["record"]["resource_type"] == "provider" for rid, _ in page_f)


def test_sort_title_is_ascending_and_stable(index):
    docs = index["docs"]
    p1, _ = search(index, "inference", sort="title", limit=100)
    p2, _ = search(index, "inference", sort="title", limit=100)
    assert [rid for rid, _ in p1] == [rid for rid, _ in p2], "title sort must be deterministic"
    titles = [docs[rid]["record"]["title"].lower() for rid, _ in p1]
    assert titles == sorted(titles)
    # id tiebreak: no two pages can reorder records with equal titles
    ids = [rid for rid, _ in p1]
    assert len(ids) == len(set(ids))


def test_csv_filter_ors_within_family(index):
    # multi-value topic filter == union of the single-value filters
    q = "agent"
    fa, _ = search(index, q, {"topic": "frontend"}, limit=100)
    fd, _ = search(index, q, {"topic": "design"}, limit=100)
    fboth, _ = search(index, q, {"topic": ["frontend", "design"]}, limit=100)
    assert {rid for rid, _ in fboth} == {rid for rid, _ in fa} | {rid for rid, _ in fd}


def test_csv_filters_and_across_families(index):
    docs = index["docs"]
    page, _ = search(index, "tool", {"topic": ["frontend", "design"],
                                     "resource_type": ["tool", "library-framework"]}, limit=100)
    assert page, "expected at least one tool/library-framework in frontend+design"
    for rid, _ in page:
        r = docs[rid]["record"]
        assert ({"frontend", "design"} & set(r["topics"]))
        assert r["resource_type"] in ("tool", "library-framework")


def test_date_bounds_filter(index):
    docs = index["docs"]
    page, _ = search(index, "inference", {"from": "2026-09-01"}, limit=100)
    assert page, "q=inference must have September records"
    assert all(docs[rid]["record"]["shared_on"] >= "2026-09-01" for rid, _ in page)
    page, _ = search(index, "inference", {"to": "2026-06-30"}, limit=100)
    assert all(docs[rid]["record"]["shared_on"] <= "2026-06-30" for rid, _ in page)
    # inclusive on both ends
    page, _ = search(index, "inference", {"from": "2026-06-09", "to": "2026-06-09"}, limit=100)
    assert all(docs[rid]["record"]["shared_on"] == "2026-06-09" for rid, _ in page)


def test_date_bounds_apply_to_exact_id_shortcut(index):
    # the exact-ID short-circuit must respect filters, including dates
    page, _ = search(index, "openrouter", {"from": "2099-01-01"}, limit=10)
    assert page == []


def test_inverted_date_bounds_yield_no_results(index):
    # engine applies bounds literally; from>to is an adapter-level 400
    page, _ = search(index, "inference", {"from": "2026-09-29", "to": "2026-06-09"}, limit=100)
    assert page == []
