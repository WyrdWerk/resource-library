# CheapInfra #share-tech — Resource Library

A curated, browsable archive of developer resources shared in the [CheapInfra](https://cheapinfra.com) Discord server's `#share-tech` channel — AI tools, dev tools, websites, articles, and GitHub repos, collected newest-first, week by week.

**Browse it:** the site is `index.html` — open it anywhere, or deploy to any static host (built for Cloudflare Pages; no build step, no dependencies).

## What's in here

| Path | What it is | Maintained by |
|------|-----------|---------------|
| `index.html` | The browsable site: search, category + week filters, weekly sections | Generated — run `scripts/build.py` |
| `data.json` | The full dataset: title, URL, sharer, share date, categories, brief, week, stable `id` | Generated — run `scripts/build.py` |
| `weeks/` | Per-week curated lists in Markdown, with briefs | Generated — run `scripts/build.py` |
| `notes/` | Curated research notes — the **source of truth** for site content | Hand-written |
| `raw/` | Raw weekly collection logs: every link-bearing message found, unfiltered | Append-only, never edit |
| `CHANGELOG.md` | One entry per collection batch | Generated — run `scripts/build.py` |
| `scripts/build.py` | Regenerates `index.html`, `data.json`, `weeks/`, `CHANGELOG.md` from `notes/` | Hand-written |
| `AGENTS.md` | Operating manual for agents working on this repo | Hand-written |

## Coverage

See [CHANGELOG.md](CHANGELOG.md) for the batch history. Weeks are collected newest-first; the archive currently runs from late August 2026 forward.

## Methodology

- **Collection is read-only.** Discord search (`has:link`, scoped to `#share-tech`) in weekly windows. Nothing is posted, reacted to, or clicked; no links are opened during collection.
- **Filtering.** Kept: AI tools, general tools, useful websites/webpages, GitHub repositories — things that are actually useful. Dropped: hype-only posts, exact duplicates, and redundant announcement tweets when the underlying resource is already present.
- **Boundary dates.** Discord's `after:`/`before:` filters *exclude* the boundary dates, so boundary days are re-queried separately and folded into their weeks (see `notes/` for the catch-up records).
- **Briefs.** Every retained resource gets a ~2-sentence editorial brief. Descriptions come from message text and embed previews; claims originating from announcement posts are unverified unless independently checked.

## Working on this repo

Read [AGENTS.md](AGENTS.md) — it documents the full workflow: how to collect a new week, the `notes/` format, the category taxonomy, and how to regenerate and push.

## Deploying

Any static host works. For Cloudflare Pages: create a Pages project from this repo (or drag-and-drop the files) — no build command, no output directory settings needed beyond the repo root.

## Contributing

Spotted a bad link or a miscategorized resource? Open an issue or PR against `notes/` — `index.html`, `data.json`, and `weeks/` are regenerated from it, so changes belong in the notes.

## License

TBD — the briefs are original editorial summaries; a license (e.g. CC-BY-4.0 for the curated content) still needs to be chosen.
