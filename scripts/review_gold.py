#!/usr/bin/env python3
"""Phase 5 gold-query review harness.

Runs candidate queries through scripts/search.py's engine and prints the
top-5 per query so a human can lock in reviewed expectations into
tests/gold_queries.json. Usage: python3 scripts/review_gold.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from search import build_index, load_taxonomy, search

CANDIDATES = [
    # (query, filters)
    ("openrouter", {}),
    ("tokenwatch", {}),
    ("privacywatch", {}),
    ("deepseek-clock", {}),
    ("saving-100tb-of-ram-with-math", {}),
    ("OpenRouter", {}),
    ("TokenWatch", {}),
    ("DeepSeek clock", {}),
    ("inference providers", {}),
    ("LLM gateway", {}),
    ("price comparison", {}),
    ("open source react components", {}),
    ("coding agent", {}),
    ("mcp server", {}),
    ("rust", {}),
    ("model weights huggingface", {}),
    ("vector graphics", {}),
    ("cheap inference", {"resource_type": "provider"}),
    ("components", {"topic": "frontend", "resource_type": "library-framework"}),
    ("inference", {"channel": "providers"}),
    ("tutorial", {"resource_type": "article-guide"}),
    ("journal", {}),
    ("postgres", {}),
    ("cli", {"interface": "cli"}),
    ("browser extension", {}),
    ("self-host", {}),
    ("observability dashboard", {}),
    ("agent skills", {}),
    ("next.js template", {}),
    ("sqlite", {}),
    ("video generation", {}),
    ("free unlimited inference", {}),
    ("zero data retention", {}),
    ("openrouter.com", {}),
    ("github.com/anthropics", {}),
    ("quantum computing blockchain metaverse", {}),
    ("zzzzqqqjjj", {}),
    ("the", {}),
    ("API", {"interface": "api", "resource_type": "provider"}),
    ("benchmark", {}),
]


def main():
    records = json.loads((ROOT / "api" / "v1" / "resources.json").read_text(encoding="utf-8"))
    index = build_index(records, load_taxonomy())
    out = []
    for q, f in CANDIDATES:
        page, _ = search(index, q, f, limit=5)
        top = [(rid, round(s, 2)) for rid, s in page]
        print(f"Q: {q!r} filters={f}")
        for rid, s in top:
            r = index["docs"][rid]["record"]
            print(f"    {s:>10} {rid} [{r['resource_type']}] {r['title'][:70]}")
        if not top:
            print("    (no results)")
        out.append({"query": q, "filters": f, "observed_top5": [rid for rid, _ in top]})
    json.dump(out, open("/tmp/apiv1/gold_observed.json", "w"), indent=1)
    print(f"\n{len(out)} queries observed -> /tmp/apiv1/gold_observed.json")


if __name__ == "__main__":
    main()
