# AGENTS.md — operating manual for the #share-tech resource library

This repo is a curated, browsable archive of developer resources shared in the
CheapInfra Discord server's `#share-tech` channel. It is designed so that any
agent with repo access can extend it: collect a week, curate it, regenerate,
push. This file is the full context you need. Read it before touching anything.

## Ground rules (non-negotiable)

1. **Scope: `#share-tech` on CheapInfra only.** Never expand to other channels, servers, or sources.
2. **Collection is read-only.** No posting, reacting, clicking links, or DMing anyone. Ever.
3. **Privacy.** Sharer names are Discord usernames already visible in the channel; keep them, but never add real names, emails, or anything not in the message itself.
4. **No credentials in the repo.** Tokens, keys, and secrets never get committed.

## How data flows

```
Discord #share-tech  →  raw/      (raw weekly logs, unfiltered)
                     →  notes/    (curated: filtered + ~2-sentence briefs)
                     →  scripts/build.py
                     →  index.html, data.json, weeks/, CHANGELOG.md  (generated)
                     →  push to main → deploy on any static host
```

## Repository layout

| Path | Rule |
|------|------|
| `notes/*.md` | **Source of truth.** Hand-written curated research notes, one file per collection batch. Edit these to change site content. |
| `raw/*.md` | Append-only provenance: every link-bearing message found per week, unfiltered. **Never edit or delete.** |
| `scripts/build.py` | Regenerates `index.html`, `data.json`, `weeks/`, `CHANGELOG.md` from `notes/`. Run after any `notes/` change: `python3 scripts/build.py` |
| `index.html`, `data.json`, `weeks/`, `CHANGELOG.md` | **Generated. Never hand-edit** — your edits will be overwritten. |
| `README.md`, `AGENTS.md` | Hand-maintained documentation. |

## The `notes/` format

Each file is one collection batch. Sections assign entries to weeks:

```markdown
## Week: 13–20 Aug 2026        <- entries below go to this week
## Fold into week: 3–10 Sep 2026  <- boundary-day catch-ups for an existing week

### Resource Title
- URL: https://example.com/
- Posted by: username, 14 Aug 12:00 IST
- Category: ai-tool, github
- Brief: Two sentences, tops. What it is and why it's useful.
```

- `build.py` auto-discovers every `notes/*.md`; week labels look like `13–20 Aug 2026` or `27 Aug–3 Sep 2026`. Weeks are ordered newest-first automatically.
- Keep a `## Dropped (and why)` section with bullets listing what you excluded and why — it's provenance, not clutter.

## Filter policy

**Keep:** AI tools, general tools, useful websites/webpages, GitHub repositories — things a developer would actually use.
**Drop:** hype-only posts, exact duplicates, redundant announcement tweets when the underlying resource is already present, content with no usable resource (videos, memes), links with no context that can't be classified.
**Briefs:** ~2 sentences. Descriptions come from message text and embed previews — links are *not* opened during collection. Flag unverified claims from announcement posts as unverified.

## Category taxonomy (fixed set)

`ai-tool` · `dev-tool` · `github` · `web-app` · `article`

Use one or two per resource. Do not invent new categories without discussion — the site's filter chips and colors are keyed to this set.

## The boundary-date rule (important)

Discord's `after:`/`before:` search filters **exclude** the boundary dates. A search for `after:2026-08-27 before:2026-09-03` covers 28 Aug–2 Sep only. So:

- Always overlap weekly windows by a day, and
- Re-query missed boundary days separately (`after:2026-09-02 before:2026-09-04` covers 3 Sep), then fold the results into their weeks with `## Fold into week:` sections and deduplicate.

## Adding a new week

1. **Collect** (read-only): run `in:#share-tech has:link after:<start> before:<end>` for the week, plus boundary-day catch-ups. Record author, date, message text/context, and every external URL. Save the raw table to `raw/share-tech_<YYYY-MM-DD>_to_<YYYY-MM-DD>.md`.
2. **Curate**: filter per the policy above, write ~2-sentence briefs, and save as `notes/week-<YYYY-MM-DD>_to_<YYYY-MM-DD>.md` using the format above.
3. **Regenerate**: `python3 scripts/build.py` — verify the resource counts it prints.
4. **Commit + push** to `main` (single commit; see below).
5. Update this file only if a convention changed.

## Pushing

The repo's token is scoped to this repository only. Push with the GitHub API:

- **Empty repo:** use the Contents API — `PUT /repos/{owner}/{repo}/contents/{path}` with base64 content, one call per file.
- **Existing repo:** prefer a single commit via the git data API — create blobs, then a tree, then a commit, then update `refs/heads/main`.

Never force-push. `main` is the only branch.

## Deploying

The site is a single `index.html` (+ `data.json`). Any static host works; it's built for Cloudflare Pages with no build command and the repo root as the output directory.

## What NOT to do

- Don't hand-edit `index.html`, `data.json`, `weeks/`, or `CHANGELOG.md`.
- Don't edit or delete anything under `raw/`.
- Don't rename categories or change the `notes/` section-header format without updating `scripts/build.py`.
- Don't widen the collection scope, and don't break the read-only rule.
