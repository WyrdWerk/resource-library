# Contributing

Thanks for helping keep the library good. There are three ways to contribute:

## 1. Suggest a resource

Open an issue with:

- The URL
- What it is, in a sentence or two (and why a developer would care)
- Which category it fits: `ai-tool`, `dev-tool`, `github`, `web-app`, `article`

What gets accepted: AI tools, dev/general tools, useful websites and web apps, GitHub
repos, articles — the same bar as the `#share-tech` curation. What's skipped: hype-only
posts, duplicates of things already listed, and links with no usable description.

## 2. Fix a bad link or a wrong brief

Open a pull request **against `notes/`**, not against the generated files. The site
(`index.html`), `data.json`, `weeks/`, and `CHANGELOG.md` are regenerated from the notes
by `scripts/build.py` — edits to them directly will be overwritten.

A notes entry looks like this:

```markdown
### Resource Title
- URL: https://example.com/
- Posted by: your-username, 24 Sep 2026 IST
- Category: dev-tool
- Brief: Two sentences, tops. What it is and why it's useful.
```

Add it under the right `## Week: …` section (or a new one for the current week), then run
`python3 scripts/build.py` to regenerate and check the counts it prints.

## 3. Improve the site or tooling

PRs to `scripts/build.py`, the styles in the generated page, or `scripts/linkcheck.py`
are welcome. Keep the site dependency-free (single `index.html`, no build step) so it
stays deployable on any static host.

## Ground rules

- No spam, no affiliate links, no SEO junk.
- Briefs are editorial summaries in your own words — don't paste marketing copy.
- Mark unverified product/announcement claims as unverified.
- Never commit credentials, tokens, or personal data.
