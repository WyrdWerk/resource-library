#!/usr/bin/env python3
"""Invariant tests over the live data.json, guarded by the frozen baseline.

These tests fail loudly if a rebuild changes the published dataset in any
way the frozen baseline did not approve: lost rows, reordered rows, changed
IDs (build.py derives IDs from titles, so a title edit silently changes the
ID — this is the tripwire for that), duplicate IDs/URLs, non-HTTPS URLs,
unknown categories, or a changed row shape.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((REPO_ROOT / "tests" / "manifest.baseline.json").read_text())
KNOWN_CATEGORIES = {"ai-tool", "dev-tool", "github", "web-app", "article", "providers"}
EXPECTED_KEYS = ["title", "week", "url", "sharer", "date", "categories",
                 "brief", "id", "warning", "details"]


def load_data():
    return json.loads((REPO_ROOT / "data.json").read_text())


class TestDatasetInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()

    def test_row_count_matches_baseline(self):
        self.assertEqual(len(self.data), MANIFEST["inventory"]["total"])

    def test_ordered_ids_match_baseline(self):
        """IDs are title-derived slugs; any drift means a title changed."""
        self.assertEqual([r["id"] for r in self.data], MANIFEST["ordered_ids"])

    def test_ids_unique(self):
        ids = [r["id"] for r in self.data]
        self.assertEqual(len(ids), len(set(ids)))

    def test_urls_unique(self):
        urls = [r["url"] for r in self.data]
        self.assertEqual(len(urls), len(set(urls)))

    def test_all_urls_https(self):
        bad = [r["id"] for r in self.data if not r["url"].startswith("https://")]
        self.assertEqual(bad, [])

    def test_known_categories_only(self):
        seen = {c for r in self.data for c in r["categories"]}
        self.assertTrue(seen <= KNOWN_CATEGORIES, f"unknown categories: {seen - KNOWN_CATEGORIES}")

    def test_row_shape(self):
        for r in self.data:
            self.assertEqual(list(r.keys()), EXPECTED_KEYS, f"shape drift in {r.get('id')}")
            self.assertTrue(r["title"] and r["url"] and r["id"], f"empty key field in {r['id']}")
            self.assertIsInstance(r["categories"], list)
            self.assertTrue(r["categories"], f"no categories in {r['id']}")

    def test_channel_split_matches_baseline(self):
        prov = sum(1 for r in self.data if r["week"] == "providers")
        self.assertEqual(prov, MANIFEST["inventory"]["providers"])
        self.assertEqual(len(self.data) - prov, MANIFEST["inventory"]["share_tech"])


if __name__ == "__main__":
    unittest.main()
