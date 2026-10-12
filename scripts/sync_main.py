#!/usr/bin/env python3
"""Bring the current branch up to date with main without hand-merging.

    python3 scripts/sync_main.py [--base origin/main] [--test] [--force]

Parallel PRs that add resources all rewrite the same generated files
(index.html, data.json, api/v1/, the test baseline, ...), so they always
conflict with each other. Those files are pure functions of notes/ +
catalog/, so the right resolution is never a hand-merge — it is "merge the
sources, then rebuild". This script does exactly that:

  1. merge <base> into HEAD (no commit);
  2. merge tests/gold_queries.json entry by entry (keyed by query + filters):
     daily PRs re-review different gold queries, so a text-level conflict is
     usually two independent edits; only both sides changing the *same* query
     differently still needs a human;
  3. if any other conflict touches a hand-written file (notes/, scripts/,
     tests/*.py, ...), abort the merge and exit 2 — a human/agent must resolve that;
  4. otherwise take either side of each generated file (it is about to be
     rebuilt) and run scripts/regen.py;
  5. check no resource id was lost: the merged id set must equal
     (base ids ∪ head ids) minus ids either side deliberately removed;
  6. optionally run the test suite, then commit the merge.

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
GOLD = "tests/gold_queries.json"
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


def merge_gold(root):
    """Three-way merge GOLD per entry from the index stages; True if resolved.

    The suite's precision gate (--test) still judges the merged expectations.
    """
    def stage(n):
        r = git("show", f":{n}:{GOLD}", check=False)
        return json.loads(r.stdout) if r.returncode == 0 else None

    base, ours, theirs = stage(1), stage(2), stage(3)
    if base is None or ours is None or theirs is None:
        return False
    key = lambda e: (e["query"], json.dumps(e.get("filters", {}), sort_keys=True))
    b, o, t = ({key(e): e for e in side} for side in (base, ours, theirs))
    if len(b) != len(base) or len(o) != len(ours) or len(t) != len(theirs):
        return False  # duplicate keys: not safe to merge mechanically
    merged = {}
    for k in [*o, *(k for k in t if k not in o)]:  # ours' order, then their additions
        bv, ov, tv = b.get(k), o.get(k), t.get(k)
        if ov == tv or tv == bv:
            res = ov
        elif ov == bv:
            res = tv
        else:
            print(f"  {GOLD}: both sides changed {k[0]!r} differently")
            return False
        if res is not None:
            merged[k] = res
    # match the file's existing format (1-space indent, no trailing newline)
    (root / GOLD).write_text(json.dumps(list(merged.values()), indent=1, ensure_ascii=False),
                             encoding="utf-8")
    git("add", "--", GOLD)
    print(f"merged {GOLD} entry by entry")
    return True


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
    had_conflicts = bool(conflicted)
    if GOLD in conflicted and merge_gold(root):
        conflicted.remove(GOLD)
    manual = [p for p in conflicted if not matches(p, GENERATED + JUNK)]
    if manual:
        git("merge", "--abort", check=False)
        print("conflicts in hand-written files need a human/agent:")
        print("\n".join(f"  {p}" for p in manual))
        return 2
    if merge.returncode and not had_conflicts:
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
        # --abort alone keeps regen's unstaged rewrites; the tree was clean
        # before we started, so a hard reset loses nothing.
        git("merge", "--abort", check=False)
        git("reset", "-q", "--hard")
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
