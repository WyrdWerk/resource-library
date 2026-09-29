#!/usr/bin/env python3
"""Phase 4: build the static API surface from the canonical catalog.

Reads:  catalog/resources/*.json (canonical records, canonical order)
        catalog/taxonomy/*.json (registries)
Writes: api/v1/resources.json   full canonical record array (canonical order)
        api/v1/taxonomy.json    flattened taxonomy registries + synonyms
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


def legacy_row(rec):
    """Derive the exact legacy data.json row shape from a canonical record.

    Key order must match scripts/build.py exactly:
    title, week, url, sharer, date, categories, brief, id, warning.
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
        },
    }
    (OUT / "index.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"api/v1: {len(records)} records | compat all_equal={compat['all_rows_equal']} "
          f"| mismatches={len(compat['mismatched_ids'])}")
    return 0 if compat["all_rows_equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
