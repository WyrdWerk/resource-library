#!/usr/bin/env python3
"""Frozen-fixture build test: the builder must reproduce the approved
snapshot byte-for-byte from the fixture notes.

Runs scripts/build.py in an isolated temp copy of the repo skeleton
(scripts/ + fixture notes/) and compares the generated data.json bytes
against tests/fixtures/expected_data.json. Any change to parsing,
slugging, warning extraction, ordering, or the row shape breaks this test.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NOTES = REPO_ROOT / "tests" / "fixtures" / "notes-fixture"
EXPECTED = REPO_ROOT / "tests" / "fixtures" / "expected_data.json"


def run_fixture_build(tmp):
    scripts = tmp / "scripts"
    notes = tmp / "notes"
    scripts.mkdir(parents=True)
    notes.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "build.py", scripts / "build.py")
    for f in FIXTURE_NOTES.glob("*.md"):
        shutil.copy(f, notes / f.name)
    r = subprocess.run([sys.executable, "scripts/build.py"],
                       cwd=tmp, capture_output=True, text=True, timeout=120)
    return r, tmp


class TestFixtureBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="fixture-build-"))
        cls.proc, _ = run_fixture_build(cls.tmp)
        cls.data = json.loads((cls.tmp / "data.json").read_text())
        cls.expected = json.loads(EXPECTED.read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_succeeds(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-2000:])

    def test_data_json_bytes_match_snapshot(self):
        got = (self.tmp / "data.json").read_bytes()
        want = EXPECTED.read_bytes()
        self.assertEqual(got, want, "fixture build output drifted from approved snapshot")

    def test_providers_lead_ordering(self):
        weeks = [r["week"] for r in self.data]
        first_dated = next(i for i, w in enumerate(weeks) if w != "providers")
        self.assertTrue(all(w == "providers" for w in weeks[:first_dated]))
        self.assertEqual(len(self.data), 5)

    def test_slug_collisions_numbered(self):
        ids = [r["id"] for r in self.data]
        self.assertIn("fixture-widget", ids)
        self.assertIn("fixture-widget-2", ids)
        self.assertIn("fixture-provider", ids)
        self.assertIn("fixture-provider-2", ids)

    def test_warnings_extracted(self):
        by_id = {r["id"]: r for r in self.data}
        self.assertEqual(by_id["fixture-widget-2"]["warning"], "Expect rough edges.")
        self.assertEqual(by_id["fixture-provider-2"]["warning"], "Use at your own risk.")
        self.assertEqual(by_id["fixture-widget"]["warning"], "")

    def test_index_html_has_card_anchors(self):
        html = (self.tmp / "index.html").read_text()
        for r in self.data:
            self.assertIn(f'id="r-{r["id"]}"', html)


if __name__ == "__main__":
    unittest.main()
