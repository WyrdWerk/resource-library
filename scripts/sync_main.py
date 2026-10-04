#!/usr/bin/env python3
"""Bring the current branch up to date with main without hand-merging.

    python3 scripts/sync_main.py [--base origin/main] [--test] [--force]

Parallel PRs that add resources all rewrite the same generated files
(index.html, data.json, api/v1/, the test baseline, ...), so they always
conflict with each other. Those files are pure functions of notes/ +
catalog/, so the right resolution is never a hand-merge — it is "merge the
sources, then rebuild". This script does exactly that:

  1. merge <base> into HEAD (no commit);
  2. if any conflict touches a hand-written file (notes/, scripts/, tests/*.py,
     ...), abort the merge and exit 2 — a human/agent must resolve that;
  3. otherwise take either side of each generated file (it is about to be
     rebuilt) and run scripts/regen.py;
  4. check no resource id was lost: the merged id set must equal
     (base ids ∪ head ids) minus ids either side deliberately removed;
  5. optionally run the test suite, then commit the merge.

Exit codes: 0 synced (or already up to date), 2 needs a human, 1 other failure.
Used by .github/workflows/sync-prs.yml after every merge to main; safe to run
locally too (needs pillow, and pytest + jsonschema==4.17.3 for --test).
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

GENERATED = [
    "index.html", "data.json", "CHANGELOG.md", "feed.xml", "og-image.png",
    "robots.txt", "sitemap.xml", "llms.txt", "weeks/*",
    "catalog/resources/*", "catalog/_migration_report.json", "catalog/_exceptions.json",
    "api/v1/*", "tests/manifest.baseline.json",
]
# Never meant to be tracked; dropped if a branch still carries them.
JUNK = [".pytest_cache/*", "*/__pycache__/*", "__pycache__/*"]


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def ids_at(ref):
    r = git("show", f"{ref}:data.json", check=False)
    return {row["id"] for row in json.loads(r.stdout)} if r.returncode == 0 else set()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--test", action="store_true", help="run pytest before committing")
    ap.add_argument("--force", action="store_true",
                    help="merge even if the branch touches no generated files")
    args = ap.parse_args()

    root = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("working tree has uncommitted changes; commit or stash first")
    if git("merge-base", "--is-ancestor", args.base, "HEAD", check=False).returncode == 0:
        print(f"already up to date with {args.base}")
        return 0
    mb = git("merge-base", args.base, "HEAD").stdout.strip()
    touched = git("diff", "--name-only", mb, "HEAD").stdout.split()
    if not args.force and not any(matches(p, GENERATED) for p in touched):
        print("branch touches no generated files; GitHub can merge it as-is")
        return 0

    base_ids, main_ids, head_ids = ids_at(mb), ids_at(args.base), ids_at("HEAD")
    expected = (main_ids | head_ids) - (base_ids - main_ids) - (base_ids - head_ids)

    merge = git("merge", "--no-commit", "--no-ff", args.base, check=False)
    conflicted = git("diff", "--name-only", "--diff-filter=U").stdout.split()
    manual = [p for p in conflicted if not matches(p, GENERATED + JUNK)]
    if manual:
        git("merge", "--abort", check=False)
        print("conflicts in hand-written files need a human/agent:")
        print("\n".join(f"  {p}" for p in manual))
        return 2
    if merge.returncode and not conflicted:
        git("merge", "--abort", check=False)
        sys.exit(f"merge failed:\n{merge.stdout}{merge.stderr}")

    for p in conflicted:
        # Either side will do — regen.py rewrites it. Fall back to deletion for
        # modify/delete conflicts where "ours" no longer has the file.
        if matches(p, JUNK) or git("checkout", "--ours", "--", p, check=False).returncode:
            git("rm", "-q", "--cached", "--ignore-unmatch", "--", p)
            (root / p).unlink(missing_ok=True)
        else:
            git("add", "--", p)
    for p in git("ls-files").stdout.split():
        if matches(p, JUNK):
            git("rm", "-q", "--cached", "--", p)

    def bail(msg):
        git("merge", "--abort", check=False)
        print(msg)
        return 2

    if subprocess.run([sys.executable, "scripts/regen.py"], cwd=root).returncode:
        return bail("regen failed (a new id may lack a reviewed classification)")
    got = {row["id"] for row in json.loads((root / "data.json").read_text(encoding="utf-8"))}
    if got != expected:
        return bail(f"id set changed unexpectedly: missing={sorted(expected - got)} "
                    f"extra={sorted(got - expected)}")
    if args.test and subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                                    cwd=root).returncode:
        return bail("tests failed after regenerating")

    for pat in GENERATED:
        git("add", "-A", "--", pat)
    git("commit", "-q", "--no-edit", "-m",
        f"Merge {args.base} and regenerate derived files\n\n"
        f"Generated-file conflicts resolved by scripts/sync_main.py "
        f"(rebuild, not hand-merge). {len(got)} records.")
    print(f"synced with {args.base}: {len(got)} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
