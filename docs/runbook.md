# API v1 — Runbook

The exact, copy-pasteable record of how the site, catalog, and API are
built, tested, audited, and deployed. Every command runs from the repo
root. Sections 8–11 are dated change records; §1–§3 are the current
procedure. (Originally written for the `api-v1` branch off `main@31773ab`,
2026-09-29; kept current since.)

## 0. Prerequisites

Python 3.10+ plus three packages:

```bash
pip install pillow pytest "jsonschema==4.17.3"
# or, without touching the system Python:
uv run --with pillow --with pytest --with jsonschema==4.17.3 --python 3.12 python -m pytest tests/ -q
```

- `pillow` — `scripts/build.py` renders `og-image.png`.
- `jsonschema` — `scripts/validate_catalog.py` and `tests/test_schemas.py`.
  Pinned: newer releases reword the "too short" error that one schema
  test asserts on (4.26 says "should be non-empty").
- `pytest` — the suite.

Edge work (§8) additionally needs Node + `npx wrangler`. Everything else
is stdlib.

## 1. Build (exact order)

Shortcut: `python3 scripts/regen.py [--classification new-ids.json]` runs
1a–1d below in order and refreshes `tests/manifest.baseline.json`. To bring a
branch up to date with `main` (resolving generated-file conflicts by
rebuilding), run `git fetch origin && python3 scripts/sync_main.py --test`;
CI does this automatically for open PRs (`.github/workflows/sync-prs.yml`).

```bash
# 1a. Legacy site files — UNCHANGED pipeline, sole writer of site output
python3 scripts/build.py

# 1b. Canonical catalog (reads data.json + a reviewed classification,
#     rewrites catalog/resources/ deterministically). The classification
#     is not stored in the repo: export it from the current catalog, add a
#     reviewed entry for each new id, then migrate. Any id without an entry
#     is BLOCKED and the script exits 1.
python3 - <<'EOF'
import json, glob
keys = ["resource_type", "topics", "use_cases", "interfaces", "technologies", "open_source"]
cls = {}
for p in glob.glob("catalog/resources/*.json"):
    r = json.load(open(p))
    cls[r["id"]] = {k: r[k] for k in keys}
json.dump(cls, open("/tmp/classification.json", "w"), indent=1)
EOF
# ...add reviewed entries for new ids to /tmp/classification.json...
python3 scripts/migrate.py /tmp/classification.json
# expect: migrated N/N | order_ok=True | all_equal=True | exceptions=0

# 1c. Static API artifacts (reads catalog/, writes api/v1/ only)
python3 scripts/api_build.py

# 1d. Catalog validation (schemas + taxonomy + every record)
python3 scripts/validate_catalog.py
```

Classification values must come from `catalog/taxonomy/*.json`
(`api/v1/facets.json` lists them with counts). `migrate.py` also carries
`details` through from `data.json`, so details-only changes need 1a →
1b → 1c with an unchanged classification. When resources are added,
refresh `tests/manifest.baseline.json` (`ordered_ids`, `inventory`, and
the generated-file hashes) in the same PR.

`api_build.py` never touches `index.html`, `data.json`, `weeks/`,
`feed.xml`, `CHANGELOG.md`, or `og-image.png`. If any of those drift,
the build-freeze tests fail (see §3).

## 2. Test

```bash
python3 -m pytest tests/ -q
# expected: 111 passed with agent-browser installed; without it (e.g. CI), 108 passed, 3 skipped (the browser-driven tests)
```

Suite breakdown:

| File | What it gates | Count |
|---|---|---|
| `test_invariants.py` | data.json invariants vs `manifest.baseline.json`: row count, ID order, uniqueness, HTTPS, categories, row shape, channel split | 8 |
| `test_parsing.py` | `parse_week`, `slugify`, `split_warning`, notes section handling | 11 |
| `test_build_freeze.py` | fixture build is byte-identical to `fixtures/expected_data.json` | 6 |
| `test_schemas.py` | schema/taxonomy structural rules | 18 |
| `test_migration.py` | every row migrated, fields preserved, dates evidenced, exceptions empty | 6 |
| `test_compat.py` | canonical→legacy round-trip byte-exact; api/v1 well-formed; manifest hashes | 6 |
| `test_search.py` | 40 gold queries: 100% exact-ID top-1, 100% top-5 (gate ≥90%), no-result precision, stable cursors; title sort, CSV (OR-within-family) filters, from/to date bounds | 13 |
| `test_api_contract.py` | local adapter: routes, filters, CSV + date-bound validation, sparse fields, pagination, errors, CORS, ETag/304, facets.json | 30 |
| `test_site_meta.py` | robots.txt, sitemap.xml, llms.txt shape/content; API tab wired into index.html | 5 |
| `test_library_sorting.py` | newest-first default + sort control; export/data order unchanged; one real-browser interaction test (skipped without `agent-browser`) | 6 |
| `test_random_share.py` | copy-only random-share dialog: drafts keep filters and caveats, library view unchanged (both real-browser; skipped without `agent-browser`) | 2 |

## 3. Audit / diff / smoke

```bash
# zero-drift proof for the frozen UI (compares against tests/manifest.baseline.json)
python3 - <<'EOF'
import json, hashlib
base = json.load(open('tests/manifest.baseline.json'))
bad = [f for f, h in base['generated_sha256'].items()
       if hashlib.sha256(open(f, 'rb').read()).hexdigest() != h]
print('drifted:', bad if bad else 'NONE')
EOF

# search smoke
python3 scripts/search.py "open source react components" --limit 5
python3 scripts/search.py "zero data retention" --limit 5

# local API smoke (contract tests already cover this end-to-end)
python3 scripts/api_server.py 8765 &
curl -s localhost:8765/api/v1/search?q=openrouter | head -c 300; echo
curl -s "localhost:8765/api/v1/search?q=react+components&topic=frontend,design&limit=2&fields=id"; echo
curl -sI localhost:8765/api/v1/index.json | grep -i etag
kill %1

# OpenAPI contract lint (optional; needs pyyaml + openapi-spec-validator,
# which want a newer jsonschema — use a throwaway env)
uv run --with pyyaml --with openapi-spec-validator python -c \
  "import yaml; from openapi_spec_validator import validate; validate(yaml.safe_load(open('api/openapi.yaml'))); print('openapi ok')"

# gold-set review harness (writes /tmp/apiv1/gold_observed.json)
mkdir -p /tmp/apiv1 && python3 scripts/review_gold.py
```

The drift audit only reports; it is expected to list files changed by a
PR until that PR refreshes the hashes in `tests/manifest.baseline.json`.
Note that `index.html` embeds the build date ("Last updated"), so its
hash changes whenever the site is rebuilt on a new day.

## 4. Generated sizes (2026-10-04, 310 records, 218 with details)

| Path | Size |
|---|---|
| `api/v1/resources.json` | 504 KB |
| `api/v1/taxonomy.json` | 20 KB |
| `api/v1/facets.json` | 1.8 KB |
| `api/v1/index.json` | 371 B |
| `api/v1/_compat_report.json` | 162 B |
| `catalog/` (310 records + reports) | 660 KB (apparent size) |

(2026-09-29 baseline at 285 records: resources.json 289 KB — the jump is
mostly the `details` breakdowns.)

## 5. Gold report (search)

The gates below run on every `pytest` invocation against the current
catalog; re-review with `scripts/review_gold.py` when new records change
rankings. Original review: 40 queries, 2026-09-29, against the 285-record catalog
(`tests/gold_queries.json`; review harness: `scripts/review_gold.py`):

- exact-ID queries top-1: **7/7 (100%)** — gate: 100%
- top-5 precision: **36/36 (100%)** — gate: ≥90%
- no-result queries (postgres — genuinely absent from catalog; `zzzzqqqjjj`; stopword `the`; off-topic phrase): **4/4 correct**

Engine notes: deterministic lexical scoring, fixed field weights
(title 5.0 / phrase 8.0 / brief 2.0 / taxonomy-label 3.0 / alias 3.0),
light symmetric stemming (generation/generator/generates meet),
domain-style queries (`openrouter.com`) also tried with dots split,
exact-ID and normalized-URL matches short-circuit to rank 1.

## 6. Rollback

Everything lands on `main` through merged PRs, and Cloudflare Pages
auto-deploys each `main` commit. To roll back:

- **Fastest:** in the Pages dashboard (or `npx wrangler pages deployment
  list --project-name resource-library`), roll production back to an
  earlier deployment. No git change needed; the next merge redeploys.
- **Durable:** `git revert -m 1 <merge-commit>` on a branch, open a PR,
  merge. Never force-push `main`.

The static site does not read `catalog/`, `api/`, or `schemas/`, so
reverting API-only changes cannot break the Library or Analytics tabs.
The Pages Functions read `api/v1/*.json` from the same deployment, so a
rollback always moves functions and catalog together.

## 7. Unresolved decisions (deliberately left open)

1. **`cozy` (journal app) use-case fit.** None of the 15 use cases covers
   journaling/note-taking; `create-media` was the least-wrong pick
   (photo/audio capture is a real feature). Candidate: add a
   `capture-notes` use case in a future taxonomy revision.
2. **Announcement posts are `article-guide`.** The linked page is a
   read, so the record is typed as what the user gets, not the
   announced product. If the library later prefers product-typing,
   ~8 records need retagging (listed in the Phase 3 review notes).
3. **Model weights are `dataset`.** Hugging Face weight artifacts type
   as `dataset` ("model weights" is in that type's definition), not
   `tool`. Consistent across all 5 weight records.
4. **`open_source: true` requires the literal string** "open-source" /
   "open source" in the brief. "MIT-licensed", "Apache 2.0", and "open
   weights" stay `null` — license is never inferred.
5. ~~**The daily 08:00 IST updater is untouched.**~~ Resolved: daily
   runs now execute the full §1 pipeline (build → migrate with a
   reviewed classification for new ids → api_build → validate → tests)
   inside each `daily/<date>` PR (e.g. PR #8, PR #14).

## 8. Cloudflare handoff (issue #1) — production-verified 2026-09-29

The dynamic routes ship as Pages Functions in `functions/api/v1/`
(`search.js`, `resources.js`, `resources/[id].js`, shared engine in
`_lib.js`). The engine is a faithful port of `scripts/search.py`; the
function loads `api/v1/*.json` from its own deployment's static assets
(`env.ASSETS`), so function and catalog can never skew across deploys.

Commands (run from the repo root; needs a Pages-enabled token):

```bash
# local parity gate (adapter on 8765, functions via workerd on 8788)
python3 scripts/api_server.py 8765 &
npx wrangler pages dev . --port 8788 &
python3 scripts/edge_parity.py --edge http://127.0.0.1:8788

# preview deployment (direct upload; no git push)
npx wrangler pages deploy . --project-name resource-library \
  --branch <preview-branch> --commit-dirty=true
python3 scripts/edge_parity.py --edge https://<preview>.resource-library-7q4.pages.dev

# live function logs for a deployment (needs the full deployment UUID)
npx wrangler pages deployment list --project-name resource-library
npx wrangler pages deployment tail <uuid> --project-name resource-library
```

Preview evidence (direct-upload preview deployment, pre-merge, 2026-09-29):

- [x] `edge_parity.py` vs the local adapter: **120/120** — all 40 gold
      queries byte-parity (parsed JSON), full contract battery
      (filters, fields, limit/cursor walks, all error envelopes), and
      static assets unshadowed (`/`, `/weeks/*`, `api/v1/*.json` raw).
- [x] Routing: `/api/v1/index.json`, `taxonomy.json`, `resources.json`
      still serve as static assets; unknown `/api/v1/*` paths get the
      same site fallback as before the Functions existed.
- [x] Edge HTTP behavior: `Cache-Control` (60s search / 300s
      resources / 3600s record), strong `ETag` + `If-None-Match` → 304,
      `Access-Control-Allow-Origin: *` (no credentials), HEAD/OPTIONS
      (204), 405 `method_not_allowed` for POST/PUT/DELETE, 400/404
      envelopes match the adapter.
- [x] Latency (measured from one client, edge colo SEA, 200 sequential
      requests over the gold queries): p50 **76 ms**, p95 **106 ms**,
      p99 133 ms — inside the spec's p95 < 200 ms target. The target is
      now a measurement from this location, not a claim for all
      clients. Function CPU per request: 1–2 ms (from `wrangler tail`).
- [x] Ops: live logs via `wrangler pages deployment tail`; abuse
      control active ahead of the function (Cloudflare WAF 403s
      known-bot user agents, e.g. `Python-urllib`); rollback for
      git-connected production = redeploy any earlier commit (see §6).
- [x] Production: PR #4 merged to `main` (`8e15bac`) → Pages
      auto-deploy `2f1ddab0` (2026-09-29). Both domains smoke-tested
      with the full parity gate: `https://cheapinfra-resources.wyrdwerk.com`
      and `https://resource-library-7q4.pages.dev` each **120/120**
      (gold queries, contract battery, statics unshadowed, site root
      200). Production latency on the custom domain (edge colo SEA,
      200 requests over the gold queries): **p50 101 ms, p95 144 ms**,
      p99 203 ms, 200/200 HTTP 200 — inside the spec's p95 < 200 ms
      target. Preview numbers above were measured before the merge on
      the direct-upload preview deployment.

Notes: the issue text (from docs/api-spec.md §8) mentions
`/api/v1/meta` — that endpoint was never part of the implemented
contract (api/openapi.yaml is authoritative; the manifest lives at
`/api/v1/index.json`). The spec's error names (`invalid_query`,
`invalid_filter`) similarly map to the implemented `bad_*` codes above.
`/api/v1/facets` originally fell into this bucket too; it shipped (as
the static `facets.json`, see §9) in the 2026-09-29 follow-up.

## 9. Spec-gap follow-up — facets.json, CSV filters, date bounds, sort=title (2026-09-29)

The four practical gaps between docs/api-spec.md and the deployed V1
surface, closed additively within V1 (spec §8: additive optional fields
may ship within V1):

- `api/v1/facets.json` — static per-family facet values + corpus
  counts, generated by `scripts/api_build.py` (keyed by filter-param
  names; satisfies `schemas/exports.schema.json` `$defs.facets`).
- CSV multi-value filters — OR within a facet family, families AND
  (previously 400 `bad_filter`; single value echoes as string,
  multiple as a deduped array).
- `from`/`to` — inclusive YYYY-MM-DD bounds on `shared_on`, strictly
  validated identically in adapter and JS port (previously silently
  ignored).
- `sort=title` — title ascending, id tiebreak.

Deliberately not built (evidence recorded in the PR #5 discussion):
`{data, meta}` envelope and error renames (spec's own rule: renaming
requires V2), `meta.json`/`catalog.json`/`openapi.json` (duplicate
existing artifacts / stdlib-only constraint), q-length validation,
search-weight retune (gold set already 100%).

- [x] Tests: 98 passed (79 + 19 new; gold set unchanged, still 100%
      top-1 and top-5). `validate_catalog.py`: catalog valid.
- [x] Local edge: `wrangler pages dev` parity gate extended 120 → 134
      checks; 134/134 before merging.
- [x] Production: PR #5 merged to `main` (`e5b2a9b`) → Pages auto-deploy
      `af5b65ec` (2026-09-29). Both domains smoke-tested with the full
      gate: custom domain and `resource-library-7q4.pages.dev` each
      **134/134**, including facets.json byte-equality vs the repo
      file and the new CSV/date/title battery. Live feature smoke:
      `facets.json` (ai-agents 121, inference 104, providers 82),
      `?topic=frontend,design` → 15 results with array echo,
      `from=2026-09-01` narrows `q=inference` 100 → 36,
      `sort=title` ascending, malformed `from=2026-02-30` → 400.

## 10. Site agent docs + SEO meta (PR #6, 2026-09-29)

In-site API documentation and crawler/agent entry points, all generated
by `scripts/build.py` (never hand-edit):

- Third SPA tab **API** (`#view=api`, shareable + restored on load):
  quick-start curl examples, endpoints/parameters tables, conventions &
  errors, machine-readable doc links. Sidebar "For agents" block +
  footer API link.
- `robots.txt` (allow all + Sitemap line), `sitemap.xml` (SPA root),
  `llms.txt` (llmstxt.org format: H1 + blockquote + linked sections with
  full param/error/cache facts for agents).
- New `tests/test_site_meta.py` (5 tests; suite 98 → 103). Baseline
  sha refresh for `index.html` + the three new files; drift audit clean.

- [x] Correction (2026-09-29, `248405f` follow-up): `sitemap.xml`
      `<lastmod>` is derived from the newest collection window end, not
      the build clock — rebuilds with unchanged notes are byte-identical
      (verified by double-build diff) and crawlers only see a new
      lastmod when content actually changes.
- [x] Tests: 103 passed. Headless-Chromium render checks at 1280 px
      (dark + light) and 390 px: no horizontal overflow, no clipped
      content (DOM-measured, plus native-res crops), tab switching,
      sidebar link, and hash restore verified in-DOM.
- [x] Production: PR #6 merged to `main` (`f2a05ea`) → Pages auto-deploy
      `274981a6` (2026-09-29). Both domains smoke-tested: `robots.txt`,
      `sitemap.xml`, `llms.txt` HTTP 200 and byte-identical to the repo
      files and to each other; `index.html` carries the API-tab markers;
      linked assets (`api/openapi.yaml`, `docs/runbook.md`,
      `docs/api-spec.md`, `api/v1/facets.json`) all 200; live search
      `q=vector&limit=1` → 1 result. Prod render check via headless
      Chromium on the custom domain: API tab active, no overflow.

## 11. Documentation refresh + API gap register (2026-10-04)

Docs brought in line with the shipped state at 310 records (README,
AGENTS.md, CONTRIBUTING.md, tests/README.md, this runbook, the
docs/api-spec.md status banner, api/openapi.yaml, and the build.py
templates for the API tab and llms.txt). No API behavior changed.

Corrections to previously published docs, each verified against the
local adapter and production:

- The API tab and llms.txt examples used `topic=ai-inference` and
  `topic=quantization`, which are not taxonomy values; both returned
  400 `bad_filter`. Replaced with examples that return results.
- "q optional — filters alone work" was wrong: `/search` scores only
  records that match a non-empty `q`, so a filter-only request returns
  `results: []` (production: `?topic=frontend` → 0 results). Now
  documented as a v1 limit, with `/resources` as the browse path.
- `open_source=false` matches every record whose flag is not `true`,
  including the unknown (`null`) ones. Now documented.
- The `details` field (218 records) was missing from the docs, and
  `fields=details` is rejected (400 `bad_fields`) because it is absent
  from `FIELD_ALLOW` in both implementations.
- llms.txt now uses H2 sections (llmstxt.org shape). OpenAPI gained
  operationIds, tags, absolute servers, full facet enums, response
  headers, 304/405/500/503 responses, and Facets/Taxonomy/SearchResponse/
  ResourcePage schemas. It validates under openapi-spec-validator.

API expansion candidates, roughly ordered by value and risk. Each one is
additive within v1 and needs matching changes in `scripts/api_server.py`,
`functions/api/v1/_lib.js`, tests, and `edge_parity.py`:

1. **Filter-only search (browse mode).** When `q` is empty and filters are
   set, return every matching record (sorted by `sort`, defaulting to
   `newest`) instead of `[]`. The `sort=newest` branch in `search.py`
   already expects a query-less case.
2. **`details` in `FIELD_ALLOW`.** One-line change on each side, plus a
   contract test.
3. **Index `details` for search.** Low-weight field (below brief) so
   long-form breakdowns improve recall. This changes ranking, so re-run
   the gold set.
4. **`total` on `/search`.** Clients currently can't size a result set
   without paging to the end.
5. **Filters on `/resources`.** Accept the same facet/date params as
   `/search` for a list view with a real browse path.
6. **JSON 404 for unknown `/api/v1/*` paths** via a catch-all function
   (today they fall back to the SPA HTML).
7. **Link verification.** Populate `verification` from
   `scripts/linkcheck.py` (every record says `unchecked` today).
