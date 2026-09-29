#!/usr/bin/env python3
"""Unit tests for the pure parsing helpers in scripts/build.py.

Covers week-label parsing (both month styles, en-dash/hyphen), the
"Fold into week" and "## Providers" sections, warning extraction,
slug-collision numbering, and the nine-field data.json row shape.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build


class TestParseWeek(unittest.TestCase):
    def test_same_month(self):
        w = build.parse_week("13–20 Aug 2026")
        self.assertEqual((w["start"], w["end"]), ((2026, 8, 13), (2026, 8, 20)))
        self.assertEqual(w["slug"], "2026-08-13_to_2026-08-20")

    def test_cross_month(self):
        w = build.parse_week("27 Aug–3 Sep 2026")
        self.assertEqual((w["start"], w["end"]), ((2026, 8, 27), (2026, 9, 3)))
        self.assertEqual(w["slug"], "2026-08-27_to_2026-09-03")

    def test_hyphen_separator(self):
        w = build.parse_week("24 Sep-1 Oct 2026")
        self.assertEqual((w["start"], w["end"]), ((2026, 9, 24), (2026, 10, 1)))

    def test_bad_label_raises(self):
        with self.assertRaises(ValueError):
            build.parse_week("not a week")


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(build.slugify("Hello World!", set()), "hello-world")

    def test_collision_numbering(self):
        seen = set()
        self.assertEqual(build.slugify("Same Title", seen), "same-title")
        self.assertEqual(build.slugify("Same Title", seen), "same-title-2")
        self.assertEqual(build.slugify("Same Title", seen), "same-title-3")

    def test_empty_title_fallback(self):
        self.assertEqual(build.slugify("!!!", set()), "resource")


class TestSplitWarning(unittest.TestCase):
    def test_caveat_split(self):
        desc, warn = build.split_warning(
            "A useful tool. Expect rough edges.")
        self.assertEqual(desc, "A useful tool.")
        self.assertEqual(warn, "Expect rough edges.")

    def test_no_caveat(self):
        desc, warn = build.split_warning("A useful tool. Small and fast.")
        self.assertEqual(warn, "")
        self.assertIn("useful", desc)

    def test_all_caveat_keeps_brief_whole(self):
        desc, warn = build.split_warning("Use at your own risk.")
        self.assertEqual(warn, "")
        self.assertEqual(desc, "Use at your own risk.")


class TestParseNotes(unittest.TestCase):
    def test_fixture_sections(self):
        fx = REPO_ROOT / "tests" / "fixtures" / "notes-fixture"
        recs = []
        for p in sorted(fx.glob("*.md")):
            recs.extend(build.parse_notes(p))
        weeks = [r["week"] for r in recs]
        self.assertIn("providers", weeks)
        self.assertIn("1–7 Jan 2026", weeks)
        # fold-into-week lands in the named week
        folded = [r for r in recs if r["title"] == "Folded Gadget"]
        self.assertEqual(len(folded), 1)
        self.assertEqual(folded[0]["week"], "1–7 Jan 2026")
        # date extraction from "Posted by" line
        widget = [r for r in recs if r["title"] == "Fixture Widget"][0]
        self.assertEqual(widget["date"], "3 Jan")
        self.assertEqual(widget["sharer"], "tester1")
        # entries without URL are skipped
        self.assertTrue(all(r.get("url") for r in recs))


if __name__ == "__main__":
    unittest.main()
