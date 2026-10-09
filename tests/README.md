# Tests

Regression harness for the resource library: builder, catalog, search, and
API. Tests are written with `unittest`/plain asserts and run under `pytest`.

## Layout

- `manifest.baseline.json` — approved snapshot: the ordered list of all
  record IDs (310 at the time of writing), inventory counts (total,
  providers/share-tech split, categories), and SHA-256 of each generated
  site file. The invariant tests enforce IDs and counts; the hashes feed
  the drift audit in `docs/runbook.md` §3. Refresh it deliberately in the
  same PR that adds or removes resources.
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
- `test_schemas.py` — schema/taxonomy structural rules (Phase 2).
- `test_migration.py` — Phase 3 gate: one canonical record per data.json
  row, protected fields preserved, dates evidenced, `_exceptions.json` empty.
- `test_compat.py` — Phase 4 gate: canonical→legacy round-trip is
  byte-exact; `api/v1` artifacts well-formed; manifest hashes match.
- `gold_queries.json` — 40 reviewed search queries (Phase 5); review
  harness: `scripts/review_gold.py`.
- `test_search.py` — Phase 5 gate: 100% exact-ID top-1, 100% top-5
  (gate ≥90%), no-result precision, stable pagination cursors.
- `test_api_contract.py` — Phase 6 gate: local adapter contract (routes,
  filters, CSV + date bounds, sparse fields, pagination, errors, CORS,
  ETag/304, facets.json).
- `test_site_meta.py` — robots.txt, sitemap.xml, llms.txt shape (H1,
  blockquote, absolute links, key facts) and the API tab wiring in
  index.html.
- `test_library_sorting.py` — site chronology: newest-first default,
  sort options, unchanged export order; one test drives a real browser
  via `agent-browser` and skips when it is not installed.
- `fixtures/schema/` — deliberately invalid records for `test_schemas.py`.

## Run

From the repo root:

    python3 -m pytest tests/ -q
    # expected: 111 passed (the browser-driven sorting test skips if agent-browser is not installed)

## Environment

- Python 3.10+ (CI-style runs use 3.12).
- `pip install pytest pillow "jsonschema==4.17.3"` — `pillow` because
  the fixture build renders og-image.png; jsonschema is pinned because
  newer releases reword the "too short" message `test_schemas.py`
  asserts on.
