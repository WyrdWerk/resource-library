#!/usr/bin/env python3
"""One-time deterministic migration: data.json + reviewed classification
-> catalog/resources/<id>.json, with preservation proofs.

Reads:
  notes-derived data.json (legacy rows, source of truth for editorial fields)
  <classification.json> (human-reviewed taxonomy per id)

Writes:
  catalog/resources/<id>.json   one canonical record per current ID
  catalog/_migration_report.json per-field old/new comparisons + evidence
  catalog/_exceptions.json       must be [] — any blocked row aborts loudly

Date evidence (no inference):
  share-tech: year comes from the record's own parsed week label; the
    day/month must fall inside that week, else the row is blocked.
  providers:  year 2026 is deduced from documented channel lifetime
    (created 2026-07-20, collection through 2026-09-25 — see
    raw/providers_2026-07-20_to_2026-09-25.md); the day/month must fall
    inside that window, else the row is blocked. This deliberately does
    NOT reuse build.py's RSS pubDate fallback (latest-week year).

Usage: python3 scripts/migrate.py <classification.json> [repo-root]
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build

CLASS_PATH = Path(sys.argv[1])
OUT_DIR = ROOT / "catalog" / "resources"

PROV_START = date(2026, 7, 20)
# Channel creation is fixed; the end bound tracks the calendar year because the
# #providers channel is ongoing (daily incremental collection since 2026-09-26).
# Year is hard-coded to 2026 in parse_posted, so this bound only guards against
# impossible/pre-channel dates. (Extended 2026-10-02: was 2026-09-25, the date
# of the original full-channel sweep.)
PROV_END = date(2026, 12, 31)


def parse_posted(posted_date, week_label):
    """Return (iso_date, evidence_str) or raise BlockedRow."""
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})", posted_date or "")
    if not m:
        raise BlockedRow(f"unparseable posted date {posted_date!r}")
    day, mon = int(m.group(1)), build.norm_mon(m.group(2))
    month = build.MONTHS[mon]
    if week_label == "providers":
        dt = date(2026, month, day)
        if not (PROV_START <= dt <= PROV_END):
            raise BlockedRow(f"provider date {dt} outside channel lifetime "
                             f"{PROV_START}..{PROV_END}")
        return dt.isoformat(), (
            f"posted '{posted_date}' within documented #providers lifetime "
            f"2026-07-20..2026-09-25 (raw/providers_2026-07-20_to_2026-09-25.md)")
    w = build.parse_week(week_label)
    year = w["start"][0]
    dt = date(year, month, day)
    start = date(*w["start"])
    end = date(*w["end"])
    if not (start <= dt <= end):
        raise BlockedRow(f"date {dt} outside its week {week_label} ({start}..{end})")
    return dt.isoformat(), f"posted '{posted_date}' inside week label '{week_label}'"


class BlockedRow(Exception):
    pass


def main():
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    classification = json.loads(CLASS_PATH.read_text(encoding="utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # drop stale migration outputs (deterministic rebuild)
    for p in OUT_DIR.glob("*.json"):
        p.unlink()

    report_rows, exceptions = [], []
    seen_order = []
    for row in data:
        rid = row["id"]
        cls = classification.get(rid)
        if cls is None:
            exceptions.append({"id": rid, "reason": "no reviewed classification"})
            continue
        try:
            shared_on, evidence = parse_posted(row["date"], row["week"])
        except BlockedRow as e:
            exceptions.append({"id": rid, "reason": str(e)})
            continue
        rec = {
            "schema_version": "1.0",
            "id": rid,
            "title": row["title"],
            "canonical_url": row["url"],
            "brief": row["brief"],
            "caveat": row["warning"] or None,
            "resource_type": cls["resource_type"],
            "topics": cls["topics"],
            "use_cases": cls["use_cases"],
            "interfaces": cls.get("interfaces", []),
            "technologies": cls.get("technologies", []),
            "license": None,
            "open_source": cls.get("open_source"),
            "display_period": row["week"],
            "legacy_categories": row["categories"],
            "source": {
                "channel": "providers" if row["week"] == "providers" else "share-tech",
                "sharer": row["sharer"],
            },
            "shared_on": shared_on,
            "verification": {"status": "unchecked", "checked_at": None, "final_url": None},
        }
        (OUT_DIR / f"{rid}.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        seen_order.append(rid)
        # preservation proof: protected legacy fields compare equal
        checks = {
            "id": rec["id"] == row["id"],
            "title": rec["title"] == row["title"],
            "url": rec["canonical_url"] == row["url"],
            "brief": rec["brief"] == row["brief"],
            "warning->caveat": (rec["caveat"] or "") == row["warning"],
            "sharer": rec["source"]["sharer"] == row["sharer"],
            "week->display_period": rec["display_period"] == row["week"],
            "categories->legacy_categories": rec["legacy_categories"] == row["categories"],
        }
        report_rows.append({
            "id": rid, "checks": checks, "all_equal": all(checks.values()),
            "shared_on": shared_on, "date_evidence": evidence,
        })

    order_ok = seen_order == [r["id"] for r in data]
    report = {
        "migrated": len(seen_order),
        "source_rows": len(data),
        "order_preserved": order_ok,
        "all_fields_equal": all(r["all_equal"] for r in report_rows),
        "rows": report_rows,
    }
    (ROOT / "catalog" / "_migration_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "catalog" / "_exceptions.json").write_text(
        json.dumps(exceptions, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"migrated {len(seen_order)}/{len(data)} | order_ok={order_ok} "
          f"| all_equal={report['all_fields_equal']} | exceptions={len(exceptions)}")
    for e in exceptions:
        print("  BLOCKED:", e["id"], "-", e["reason"])
    if exceptions or not order_ok or not report["all_fields_equal"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
