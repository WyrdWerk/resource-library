#!/usr/bin/env python3
"""Regenerate every derived artifact from notes/ + catalog/ in one command.

    python3 scripts/regen.py [--classification extra.json]

Runs, in order (docs/runbook.md §1):
  1. scripts/build.py              site files (index.html, data.json, weeks/, ...)
  2. scripts/migrate.py            catalog/resources/ — classification is exported
                                   from the existing catalog records, merged with
                                   --classification (reviewed entries for new ids)
  3. scripts/api_build.py          api/v1/
  4. scripts/validate_catalog.py   schema + taxonomy gate
  5. tests/manifest.baseline.json  ordered_ids, inventory, generated hashes

Idempotent: running it on a clean tree changes nothing except the build date
embedded in index.html on a new day. Exits non-zero on any failed step (most
commonly: a new id with no reviewed classification — supply one with
--classification).
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASS_KEYS = ["resource_type", "topics", "use_cases", "interfaces", "technologies", "open_source"]
SITE_FILES = ["CHANGELOG.md", "data.json", "feed.xml", "index.html", "llms.txt",
              "og-image.png", "robots.txt", "sitemap.xml"]


def run(*args):
    print("+", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def export_classification(extra):
    cls = {}
    for p in sorted((ROOT / "catalog" / "resources").glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        cls[rec["id"]] = {k: rec.get(k) for k in CLASS_KEYS}
    if extra:
        cls.update(json.loads(Path(extra).read_text(encoding="utf-8")))
    return cls


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_baseline():
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    prov = sum(1 for r in data if r["week"] == "providers")
    files = SITE_FILES + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "weeks").glob("*.md"))
    baseline = {
        "baseline_commit": "scripts/regen.py",
        "generated_sha256": {f: sha256(ROOT / f) for f in files},
        "inventory": {
            "categories": sorted({c for r in data for c in r["categories"]}),
            "https_urls": sum(1 for r in data if r["url"].startswith("https://")),
            "nonempty_warnings": sum(1 for r in data if r["warning"]),
            "providers": prov,
            "share_tech": len(data) - prov,
            "total": len(data),
            "unique_ids": len({r["id"] for r in data}),
            "unique_urls": len({r["url"] for r in data}),
        },
        "ordered_ids": [r["id"] for r in data],
    }
    (ROOT / "tests" / "manifest.baseline.json").write_text(
        json.dumps(baseline, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"baseline: {len(data)} records ({len(data) - prov} share-tech, {prov} providers)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--classification", help="JSON {id: {resource_type, topics, ...}} "
                    "with reviewed entries for new ids (merged over the exported catalog)")
    ap.add_argument("--skip-site", action="store_true", help="skip scripts/build.py")
    args = ap.parse_args()

    if not args.skip_site:
        run("scripts/build.py")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(export_classification(args.classification), f, indent=1)
    try:
        run("scripts/migrate.py", f.name)
    finally:
        Path(f.name).unlink()
    run("scripts/api_build.py")
    run("scripts/validate_catalog.py")
    refresh_baseline()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"regen failed at: {' '.join(map(str, e.cmd[1:]))}")
