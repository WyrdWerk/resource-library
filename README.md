# CheapInfra #share-tech — Resource Library

A curated, browsable archive of developer resources shared in the [CheapInfra](https://cheapinfra.com) Discord server's `#share-tech` channel — AI tools, dev tools, websites, articles, and GitHub repos, collected newest-first, week by week.

**Browse it:** the site is `index.html` — open it anywhere, or deploy to any static host (built for Cloudflare Pages; no build step, no dependencies). It opens in the dossier's black editorial theme (near-black background, serif headlines, mint-green accent) with a light-mode toggle in the header (your choice is remembered), and has two tabs: **Library** (search, category + week filters, numbered weekly sections) and **Analytics** (weekly volume, top sharers, category mix over time with weekly/fortnightly views, and a sharer spotlight — all rendered as dependency-free inline SVG).

## What's in here

| Path | What it is | Maintained by |
|------|-----------|---------------|
| `index.html` | The browsable site: search, category + week filters, Clear all button, numbered weekly sections, dark/light theme toggle (black default), Analytics tab | Generated — run `scripts/build.py` |
| `data.json` | The full dataset: title, URL, sharer, share date, categories, brief, week, stable `id` | Generated — run `scripts/build.py` |
| `weeks/` | Per-week curated lists in Markdown, with briefs | Generated — run `scripts/build.py` |
| `feed.xml` | RSS feed of all resources, newest first | Generated — run `scripts/build.py` |
| `og-image.png` | Social card for link previews (1200×630) | Generated — run `scripts/build.py` |
| `notes/` | Curated research notes — the **source of truth** for site content | Hand-written |
| `raw/` | Raw weekly collection logs: every link-bearing message found, unfiltered | Append-only, never edit |
| `CHANGELOG.md` | One entry per collection batch | Generated — run `scripts/build.py` |
| `scripts/build.py` | Regenerates `index.html`, `data.json`, `weeks/`, `CHANGELOG.md`, `feed.xml`, `og-image.png` from `notes/` | Hand-written |
| `scripts/linkcheck.py` | Checks every URL in `data.json` for link rot | Hand-written |
| `catalog/` | Canonical per-resource JSON (`resources/<id>.json`) + taxonomy registries (`taxonomy/*.json`) — the machine-readable source behind the API | Generated — `scripts/migrate.py`, validated against `schemas/` |
| `api/v1/` | Static JSON API: `resources.json`, `taxonomy.json`, `index.json`, per-resource files | Generated — `scripts/api_build.py` |
| `api/openapi.yaml` | OpenAPI 3.1 contract for the API | Hand-written |
| `functions/api/v1/` | Cloudflare Pages Functions: dynamic `/api/v1/search` and `/api/v1/resources` routes (JS port of the adapter) | Hand-written |
| `schemas/` | JSON Schemas for catalog resources, taxonomy, and exports | Hand-written |
| `docs/runbook.md` | Exact build, test, audit, and smoke-test commands for the API surface | Hand-written |
| `tests/` | Test suite (79 tests), including build-freeze tests that fail if any generated site file drifts | Hand-written — `python3 -m pytest tests/ -q` |
| `AGENTS.md` | Operating manual for agents working on this repo | Hand-written |
| `CONTRIBUTING.md` | How to suggest resources or send fixes | Hand-written |
| `LICENSE` | CC-BY-4.0 — the curated content's license | Hand-written |

## Coverage

See [CHANGELOG.md](CHANGELOG.md) for the batch history. Weeks are collected newest-first; the archive currently runs from 4 Jun 2026 forward (15 weekly periods).

## Methodology

- **Collection is read-only.** Discord search (`has:link`, scoped to `#share-tech`) in weekly windows. Nothing is posted, reacted to, or clicked; no links are opened during collection.
- **Filtering.** Kept: AI tools, general tools, useful websites/webpages, GitHub repositories — things that are actually useful. Dropped: hype-only posts, exact duplicates, and redundant announcement tweets when the underlying resource is already present.
- **Boundary dates.** Discord's `after:`/`before:` filters *exclude* the boundary dates, so boundary days are re-queried separately and folded into their weeks (see `notes/` for the catch-up records).
- **Briefs.** Every retained resource gets a ~2-sentence editorial brief. Descriptions come from message text and embed previews; claims originating from announcement posts are unverified unless independently checked.

## Working on this repo

Read [AGENTS.md](AGENTS.md) — it documents the full workflow: how to collect a new week, the `notes/` format, the category taxonomy, and how to regenerate and push.

## Machine-readable API

The library is also served as data. `catalog/` holds one canonical JSON record per
resource plus the controlled taxonomy registries, and `api/v1/` holds the static JSON
API (`resources.json`, `taxonomy.json`, `index.json`, per-resource files), with its
contract in `api/openapi.yaml`. Everything there is generated — see
[docs/runbook.md](docs/runbook.md) for the exact build, test, and audit commands.
Search (`scripts/search.py`) is deterministic lexical search over the catalog: no
vector database, no model calls.

Dynamic endpoints — `GET /api/v1/search` (live query ranking and filters) and
`GET /api/v1/resources` (+ `/api/v1/resources/{id}`) — are served by Cloudflare Pages
Functions in `functions/api/v1/`, a faithful port of the local adapter
(`scripts/api_server.py`) that reads the same deployment's static assets.
`scripts/edge_parity.py` proves the port: it replays the 40-query gold set and the
whole local contract battery against any deployment (local wrangler or a live
preview URL) and requires identical responses.

## Deploying

Any static host works. For Cloudflare Pages: create a Pages project from this repo (or drag-and-drop the files) — no build command, no output directory settings needed beyond the repo root.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: suggest resources via issues,
and send fixes as PRs against `notes/` — `index.html`, `data.json`, and `weeks/` are
regenerated from it, so changes belong in the notes.

## License

[CC-BY-4.0](LICENSE) — the curated content (briefs, notes, and site) is yours to share
and adapt with attribution. Linked third-party resources keep their own licenses.
