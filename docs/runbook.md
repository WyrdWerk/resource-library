# API v1 — Runbook

Branch `api-v1` off `main` (`31773ab`). This runbook is the exact,
copy-pasteable record of how the API surface is built, tested, and
audited. Every command runs from the repo root.

## 0. Prerequisites

Python 3.10+ stdlib only, plus `pytest` for the suite
(`pip install pytest`). No other dependencies anywhere in this branch.

## 1. Build (exact order)

```bash
# 1a. Legacy site files — UNCHANGED pipeline, sole writer of site output
python3 scripts/build.py

# 1b. Static API artifacts (reads catalog/, writes api/v1/ only)
python3 scripts/api_build.py

# 1c. Catalog validation (schemas + taxonomy + 285 records)
python3 scripts/validate_catalog.py
```

`api_build.py` never touches `index.html`, `data.json`, `weeks/`,
`feed.xml`, `CHANGELOG.md`, or `og-image.png`. If any of those drift,
the build-freeze tests fail (see §3).

## 2. Test

```bash
python3 -m pytest tests/ -q
# expected: 79 passed
```

Suite breakdown:

| File | What it gates | Count |
|---|---|---|
| `test_invariants.py` | legacy parsing invariants | 25 total Phase 1 |
| `test_parsing.py` | (with above) | |
| `test_build_freeze.py` | (with above) | |
| `test_schemas.py` | schema/taxonomy structural rules | 18 |
| `test_migration.py` | 285 records migrated, fields preserved, dates evidenced, exceptions empty | 7 |
| `test_compat.py` | canonical→legacy round-trip byte-exact; api/v1 well-formed; manifest hashes | 6 |
| `test_search.py` | 40 gold queries: 100% exact-ID top-1, 100% top-5 (gate ≥90%), no-result precision, stable cursors | 7 |
| `test_api_contract.py` | local adapter: routes, filters, sparse fields, pagination, errors, CORS, ETag/304 | 17 |

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
curl -sI localhost:8765/api/v1/index.json | grep -i etag
kill %1
```

## 4. Generated sizes (2026-09-29, 285 records)

| Path | Size |
|---|---|
| `api/v1/resources.json` | 289 KB |
| `api/v1/taxonomy.json` | 20 KB |
| `api/v1/index.json` | 335 B |
| `api/v1/_compat_report.json` | 162 B |
| `catalog/` (285 records + reports) | 1.3 MB |

## 5. Gold report (search)

40 queries reviewed 2026-09-29 against the 285-record catalog
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

Every phase is a separate commit on `api-v1`; nothing on `main` is
touched. To roll back:

```bash
git checkout main          # the branch is unmerged; delete it to drop everything
git branch -D api-v1      # local only — no force-push to main ever happened
```

To roll back one phase, `git revert <phase-commit>` in reverse order
(api → search → generator → migration → schemas → harness → baseline).
The static site does not read `catalog/`, `api/`, or `schemas/`, so
reverting cannot break the deployed site.

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
5. **The daily 08:00 IST updater is untouched.** It still writes
   `notes/` + `data.json` via `build.py`. A future change must teach it
   to also emit `catalog/resources/<id>.json`; until then, re-run
   `scripts/migrate.py` (with a reviewed classification) after any
   data update, then `api_build.py`.

## 8. Cloudflare handoff (issue #1) — preview-verified 2026-09-29

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

Preview evidence (deployment of this branch, 2026-09-29):

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
- [ ] Production: merge this branch to `main` → auto-deploy, then
      smoke-test both `https://cheapinfra-resources.wyrdwerk.com/` and
      `https://resource-library-7q4.pages.dev/` (custom domain last,
      per issue #1). **Pending owner approval of the preview evidence.**

Notes: the issue text (from docs/api-spec.md §8) mentions
`/api/v1/facets` and `/api/v1/meta` — those endpoints were never part
of the implemented contract (api/openapi.yaml is authoritative; the
manifest lives at `/api/v1/index.json` and facet values at
`/api/v1/taxonomy.json`). The spec's error names (`invalid_query`,
`invalid_filter`) similarly map to the implemented `bad_*` codes above.

