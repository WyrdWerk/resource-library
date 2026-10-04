# Contributing

Thanks for helping keep the library good. There are three ways to contribute:

## 1. Suggest a resource

Open an issue with:

- The URL
- What it is, in a sentence or two (and why a developer would care)
- Which category it fits: `ai-tool`, `dev-tool`, `github`, `web-app`, `article`, or
  `providers` (inference providers and provider comparisons)

What gets accepted: AI tools, dev/general tools, useful websites and web apps, GitHub
repos, articles, inference providers — the same bar as the `#share-tech` and
`#providers` curation. What's skipped: hype-only
posts, duplicates of things already listed, and links with no usable description.

## 2. Fix a bad link or a wrong brief

Open a pull request **against `notes/`**, not against the generated files. The site
(`index.html`), `data.json`, `weeks/`, `CHANGELOG.md`, and the API artifacts
(`catalog/`, `api/v1/`) are regenerated — edits to them directly will be overwritten.

If you're building tooling on the data rather than fixing content, use
`catalog/resources/<id>.json` (canonical record) or `api/v1/` (static API, contract
in `api/openapi.yaml`) as your source. Both are generated; don't edit them.

A notes entry looks like this:

```markdown
### Resource Title
- URL: https://example.com/
- Posted by: your-username, 24 Sep 2026 IST
- Category: dev-tool
- Brief: Two sentences, tops. What it is and why it's useful.
```

Add it under the right `## Week: …` section (or a new one for the current week; providers
go under `## Providers`), then run `python3 scripts/build.py` to regenerate and check the
counts it prints. To fix a long-form "In detail" breakdown, edit the record's entry in
`notes/details-*.md` (keyed by record id). New records also need a catalog entry — the
maintainers handle the taxonomy classification (`docs/runbook.md` §1).

## 3. Improve the site or tooling

PRs to `scripts/build.py`, the styles in the generated page, or `scripts/linkcheck.py`
are welcome. Keep the site dependency-free (single `index.html`, no build step) so it
stays deployable on any static host. If you touch anything under `scripts/`,
`catalog/`, `api/`, `functions/`, or `schemas/`, run `python3 -m pytest tests/ -q`
(needs `pillow`, `pytest`, `jsonschema==4.17.3`) — the build-freeze tests fail if
generated site files drift, and the contract tests cover the API surface. Changes to
`functions/api/v1/` must also pass `scripts/edge_parity.py` (see `docs/runbook.md` §8).
API behavior changes update `api/openapi.yaml`, the API tab and `llms.txt` templates in
`scripts/build.py`, and the README together.

## Ground rules

- No spam, no affiliate links, no SEO junk.
- Briefs are editorial summaries in your own words — don't paste marketing copy.
- Mark unverified product/announcement claims as unverified.
- Never commit credentials, tokens, or personal data.
