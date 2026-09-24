#!/usr/bin/env python3
"""Link health checker for the resource library.

Checks every URL in data.json (HEAD, falling back to a ranged GET) and
reports dead or unreachable ones. Exit code 1 if any are dead.

Usage: python3 scripts/linkcheck.py
"""
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; resource-library linkcheck)"}


def check(res):
    url = res["url"]
    try:
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.status
        if code in (405, 501):  # HEAD not allowed; try a ranged GET
            req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                code = resp.status
        return (res["id"], url, code, code < 400)
    except urllib.error.HTTPError as e:
        return (res["id"], url, f"HTTP {e.code}", False)
    except Exception as e:
        return (res["id"], url, type(e).__name__, False)


def main():
    data = json.loads((ROOT / "data.json").read_text())
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, data))
    dead = [r for r in results if not r[3]]
    print(f"checked: {len(results)} | alive: {len(results) - len(dead)} | dead: {len(dead)}")
    for rid, url, code, _ in dead:
        print(f"  DEAD [{code}] {rid}\n         {url}")
    raise SystemExit(1 if dead else 0)


if __name__ == "__main__":
    main()
