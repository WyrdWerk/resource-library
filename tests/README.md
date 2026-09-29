# Tests

Dependency-light regression harness for the resource library builder.
Standard library only (`unittest`); the fixture build needs whatever
`scripts/build.py` needs (pure stdlib at the time of writing).

## Layout

- `manifest.baseline.json` — frozen Phase 0 evidence: SHA-256 of every
  generated file at main@31773ab, the ordered list of all 285 IDs, and
  inventory counts. The invariant tests fail if a rebuild drifts from this.
- `test_invariants.py` — dataset invariants over the live `data.json`,
  guarded by the manifest (row count, ID order/stability, uniqueness,
  HTTPS, known categories, nine-field row shape).
- `test_parsing.py` — unit tests for `parse_week`, `slugify`,
  `split_warning`, and `parse_notes` section handling.
- `test_build_freeze.py` — runs `scripts/build.py` against the frozen
  fixture in `fixtures/notes-fixture/` and requires byte-identical
  `data.json` vs `fixtures/expected_data.json`.
- `fixtures/expected_data.json` — approved snapshot. Regenerate only by
  deliberate review: run the fixture build, inspect the diff, then copy.

## Run

From the repo root:

    python3 -m unittest discover -s tests -v

## Environment

- Python 3.12 (stdlib only).
- `jsonschema` (pip install jsonschema) is required by the catalog/API
  validation scripts added in later phases, not by these builder tests.
