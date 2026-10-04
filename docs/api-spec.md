# Resource Library — API & Search: Technical Specification

> Converted from the reviewed specification document (baseline: repo `main` @ `31773ab`, 29 September 2026). This is the reference for the API v1 implementation (PR #2) and the Cloudflare handoff (issue #1).

> **Status (2026-10-04): implemented, and kept here for history.** API v1 shipped in PRs #2–#6, and the Pages Functions have been serving production since 2026-09-29. The authoritative contract is [`api/openapi.yaml`](../api/openapi.yaml), and agents should start from [`llms.txt`](../llms.txt). Where this spec and the shipped API differ, the shipped API wins:
>
> | Spec (this document) | Shipped v1 |
> | --- | --- |
> | `{data, meta}` response envelope | Bare payloads: search returns `{query, filters, sort, limit, results, next_cursor}`, `/resources` returns `{records, next_cursor, total}`, and a single record is returned unwrapped. Renaming would need v2. |
> | Error codes `invalid_query`, `invalid_filter`, `internal_error`, `rate_limited`; `field` and `meta` in the error body | `bad_fields`, `bad_limit`, `bad_cursor`, `bad_filter`, `bad_sort`, `not_found`, `method_not_allowed`, `internal`, `catalog_unavailable`; the body is `{error: {code, message}}`. Rate limiting is Cloudflare WAF, outside the API. |
> | `GET /api/v1/facets`, `/taxonomy`, `/meta`, `/catalog.json`, `/openapi.json` | Static `facets.json`, `taxonomy.json`, and `index.json` (the manifest), plus `resources.json` (the full export). The contract lives at `/api/openapi.yaml`. |
> | `/resources` lists **and filters** | `/resources` paginates only. Filtering happens on `/search`, and only when `q` is set (filter-only browse is a candidate, see runbook §11). |
> | `q` 2–256 chars | No length validation. An empty `q` returns no results. |
> | `sort`: relevance, newest, title | Also `oldest`. |
> | Single canonical record fields (§5) | As specified, plus `details`: a researched long-form breakdown added 2026-10-03, which is null until enriched. |

---

| DRAFT TECHNICAL SPECIFICATION  /  VERSION 1.0<br>Resource Library<br>API & Search<br>An evidence-backed implementation plan for a canonical catalog, search index, and public read-only API — with the current interface held unchanged.<br>**Baseline: repository main @ 31773ab  ·  29 September 2026** |
| --- |

| **DECISION IN ONE SENTENCE**<br>Make normalized resource records the catalog of record; generate the existing site, a full JSON export, a search index, and a small versioned API from the same build. |
| --- |

**Prepared for review**

Status: implementation-ready plan — no repository, interface, layout, Cloudflare configuration, or deployment changes are included in this document revision.

# Contents

1. Executive decision

2. Current state and hard constraints

3. Goals, non-goals, and success measures

4. Target architecture

5. Canonical resource model

6. Taxonomy and organization

7. Search and ranking

8. HTTP API contract

9. Build and compatibility

10. Evidence-gated implementation plan

11. Cloudflare handoff boundary

12. Validation and acceptance

13. Decisions and assumptions

14. Evidence register

# 1. Executive decision

The library should become a versioned catalog rather than a page that happens to emit JSON. Each retained resource gets one immutable identity and one normalized record. A deterministic build then produces the existing site artifacts, a public catalog export, facet metadata, per-resource JSON, and a search index. A single read-only Cloudflare Pages Function handles query ranking and filtered pagination.

This approach solves organization and API delivery together. The same classification used by the API — resource type, topics, use cases, interfaces, technologies, source, and date — becomes the retrieval vocabulary. The current editorial brief remains searchable and display-safe; the current site can continue rendering exactly as it does today.

| **RECOMMENDED V1**<br>Public, read-only, lexical and faceted search. Preserve all 285 existing IDs. Keep the present UI byte-identical. Defer semantic/vector search, write endpoints, accounts, and personalized ranking. |
| --- |

| **Layer** | **Decision** | **Why** |
| --- | --- | --- |
| Catalog | One JSON record per resource | Stable, reviewable source of truth |
| Organization | Orthogonal controlled facets | Searchable without rewriting briefs |
| Search | Weighted lexical index | Fast, explainable, deterministic |
| Delivery | Static assets + one function | Fits current Cloudflare Pages setup |
| Compatibility | Generate legacy outputs | No UI or consumer breakage |

# 2. Current state and hard constraints

The baseline examined is repository main at commit 31773ab. It contains 285 records: 203 from #share-tech and 82 from #providers. All 285 rows carry the same nine fields; IDs and exact URLs are unique, and all published URLs use HTTPS. A clean local rerun of scripts/build.py changed no tracked output. [E1] [E4] [E5]

| **Current field** | **State** | **Retrieval implication** |
| --- | --- | --- |
| id | Unique slug | Keep immutable |
| title / brief | Editorial text | Index with different weights |
| url | One published URL | Normalize only for matching |
| categories | 6 mixed labels | Split into orthogonal facets |
| date | Day + month | Backfill ISO 8601 year |
| week | Display period / providers | Separate chronology from collection |
| sharer | Public handle | Low-weight searchable attribution |
| warning | Optional caveat text | Expose as nullable caveat |

| **EVIDENCE DISCIPLINE**<br>Observed facts carry [E] citations. Standards-dependent behavior carries [S] citations. Design choices and numeric thresholds are labeled recommendations or targets; they are not presented as measured production facts. |
| --- |

## What blocks stronger discovery today

- The current categories mix different concepts: “github” is a host, “web-app” is an interface, “article” is a resource type, and “ai-tool” / “dev-tool” are broad topics.

- The human-readable week label is serving both display and chronology; the providers collection uses the same field as a non-date sentinel.

- Briefs contain most of the useful intent, but there is no controlled vocabulary for queries such as “component libraries,” “parallel coding agents,” or “self-hosted observability.”

- The dataset is downloadable, but there is no stable query contract, pagination, facet discovery, error model, or version policy.

## Constraints that must remain true

- No interface, layout, theme, badge, week-numbering, section-order, or other visual change is part of this work.

- Earliest occurrence wins during deduplication. A later same-project duplicate is dropped; the earlier published title, URL, brief, date, and attribution are not merged or rewritten.

- Existing resource IDs and permalinks remain stable. IDs are never recycled.

- Raw collection logs remain append-only. Internal provenance is not exposed through the public API.

- The daily pipeline may add data, rebuild outputs, and verify deployment; it must not use API work as permission to redesign the site.

# 3. Goals, non-goals, and success measures

## V1 goals

- Make every resource retrievable by exact ID, title, canonical URL, brief terms, use case, topic, technology, interface, source channel, and date range.

- Offer a documented, versioned, read-only HTTP API that works without authentication for public catalog data.

- Provide deterministic relevance ranking, predictable filters, cursor pagination, cache validators, and machine-readable errors.

- Preserve the current site and data.json contract while moving the source of truth to normalized records.

- Keep classification governed: new tags must come from a registry with labels, definitions, and aliases.

- Make the daily update fail loudly on schema errors, duplicate identities, unknown tags, or compatibility regressions.

## Explicit non-goals

- No UI search redesign, filter redesign, navigation change, or new on-site interaction.

- No semantic embeddings, vector database, large language model reranker, or conversational answer endpoint in V1.

- No write API, user accounts, API keys, saved searches, comments, ratings, or personalization.

- No automatic rewriting of existing briefs, titles, canonical URLs, or attribution during taxonomy backfill.

- No promise of real-time freshness; the catalog continues to publish on the existing daily cadence.

## Success measures

| **Measure** | **Launch threshold** | **How measured** |
| --- | --- | --- |
| Identity | 285/285 IDs preserved | Migration diff |
| Classification | 100% typed | Schema validation |
| Search quality | ≥90% top-5 | 40-query gold set |
| Correctness | 0 unknown facets | Build gate |
| Compatibility | 0 UI template diffs | Frozen-input diff |
| Performance | p95 < 200 ms | Edge smoke test |

# 4. Target architecture

The catalog is the center of the system. Human curation writes normalized records and controlled vocabulary files. One build validates them and emits every public representation. The browser-facing site and API do not maintain separate copies of editorial content.

| raw Discord logs (append-only)<br>            \|<br>            v<br>curated notes + research evidence<br>            \|<br>            v<br>catalog/resources/<id>.json  +  catalog/taxonomy/*.json<br>            \|<br>            v<br>validate -> dedupe check -> search-index build -> compatibility render<br>            \|<br>    +-------+-------------------+----------------------+ <br>    \|                           \|                      \|<br>existing site outputs      static API outputs     search function<br>index.html, data.json      catalog, facets, meta   /api/v1/search<br>weeks/, feed.xml           per-resource JSON       /api/v1/resources |
| --- |

## Repository target layout

| catalog/<br>  resources/<id>.json        # canonical public record, one file per resource<br>  taxonomy/<br>    resource-types.json<br>    topics.json<br>    use-cases.json<br>    interfaces.json<br>    technologies.json<br>    synonyms.json<br>  internal/<br>    identity-index.json      # dedupe aliases; never copied to public output<br>api/v1/<br>  catalog.json               # full export<br>  facets.json                # counts and allowed values<br>  taxonomy.json              # public definitions and aliases<br>  meta.json                  # build version and freshness<br>  openapi.json               # OpenAPI 3.1 contract<br>  resources/<id>.json        # static resource representation<br>  _index/search.json         # generated postings used by the function<br>functions/api/v1/<br>  resources.js<br>  search.js |
| --- |

| **NO DUPLICATED AUTHORSHIP**<br>Only catalog records and taxonomy registries are edited. data.json, weekly Markdown, RSS, per-resource JSON, facets, metadata, and the search index are generated and must never be hand-edited. |
| --- |

## Why individual record files

- A daily addition changes only the new resource files and generated artifacts, producing readable review diffs.

- A schema failure points to one ID, not a 285-element array offset.

- Stable filenames reinforce stable IDs and make per-resource static JSON trivial.

- Concurrent curation produces fewer merge conflicts than one monolithic source file.

# 5. Canonical resource model

The public resource schema separates immutable identity, editorial content, classification, source chronology, and verification. Legacy display fields remain derivable, but they no longer carry multiple meanings.

## Required public fields

| **Field** | **Type** | **Rule** | **Purpose** |
| --- | --- | --- | --- |
| schema_version | string | Always 1.0 | Record contract |
| id | slug | Immutable, unique | Lookup + permalink |
| title | string | 1–160 chars | Display + search |
| canonical_url | URI | HTTP(S), unique | Primary destination |
| brief | string | 1–1,200 chars | Editorial summary |
| resource_type | enum | Exactly one | Primary facet |
| topics | slug[] | 1–5 values | Subject facets |
| use_cases | slug[] | 1–6 values | Intent facets |
| source | object | Channel + sharer | Attribution |
| shared_on | date | YYYY-MM-DD | Chronology |

## Optional and generated fields

| **Field** | **Type** | **Behavior** |
| --- | --- | --- |
| caveat | string\|null | Current warning text; null when absent |
| interfaces | slug[] | web, api, cli, desktop, extension, mcp |
| technologies | slug[] | Named ecosystems from the registry |
| license | string\|null | Only when verified |
| open_source | bool\|null | Unknown stays null |
| display_period | string | Preserves current week label |
| legacy_categories | slug[] | Compatibility only |
| verification | object | Status, checked_at, final_url |
| search_text | string | Generated; not returned by default |

## Illustrative normalized record

| {<br>  "schema_version": "1.0",<br>  "id": "orca",<br>  "title": "Orca",<br>  "canonical_url": "https://www.onorca.dev/",<br>  "brief": "A free, open-source Agent Development Environment ...",<br>  "caveat": null,<br>  "resource_type": "tool",<br>  "topics": ["ai-agents", "developer-tools"],<br>  "use_cases": ["orchestrate-coding-agents", "parallel-development"],<br>  "interfaces": ["desktop"],<br>  "technologies": [],<br>  "source": {"channel": "share-tech", "sharer": "ROman"},<br>  "shared_on": "2026-09-26",<br>  "display_period": "24 Sep–1 Oct 2026",<br>  "legacy_categories": ["ai-tool", "web-app"],<br>  "verification": {<br>    "status": "reachable",<br>    "checked_at": "2026-09-29T00:00:00Z"<br>  }<br>} |
| --- |

*The example shows the target shape; classification values are reviewed metadata, not a request to edit the current Orca card.*

## Identity and deduplication

- Preserve all current IDs. New IDs are lowercase ASCII slugs, 3–96 characters, and never derived again after creation.

- Normalize URLs only for matching: lowercase host, remove default ports, strip known tracking parameters, normalize trailing slash, and compare selected project aliases.

- When a later URL resolves to the same project, add it only to the internal identity index and reject the new public record. Do not merge its copy into the earlier record.

- A distinct artifact from the same project may remain only when it has a separate function and is explicitly reviewed as an independent resource.

- Internal records may retain source message IDs and rejected aliases for audit. Public API responses must not expose them.

# 6. Taxonomy and organization

Classification is deliberately multi-dimensional. A resource should not need to choose between being a GitHub repository, an AI tool, and a developer tool; those facts belong in different fields.

## Facet model

| **Facet** | **Cardinality** | **Answers** |
| --- | --- | --- |
| resource_type | Exactly 1 | What kind of thing is it? |
| topics | 1–5 | What domain is it about? |
| use_cases | 1–6 | What can someone do with it? |
| interfaces | 0–5 | How is it used? |
| technologies | 0–8 | What ecosystem does it target? |
| source.channel | Exactly 1 | Where was it collected? |

## Initial resource types

tool; repository; library-framework; service-platform; provider; article-guide; documentation; directory-gallery; dataset; template-starter; other.

## Initial topic families

AI agents; app development; backend; cloud infrastructure; databases; design; developer experience; DevOps; frontend; inference; observability; productivity; security; self-hosting; testing; web development.

## Initial use-case families

Build interfaces; deploy applications; discover design references; generate code; host models; manage agents; monitor systems; run inference; search code; test software; automate workflows; provision infrastructure; operate databases; create media; learn a technique.

## Governance rules

1. Every slug lives in exactly one registry file with a display label, concise definition, status, and optional aliases.

1. Aliases improve search but are never returned as additional categories. For example, “repo” may resolve to “repository.”

1. A new tag needs at least two likely resources or a clear near-term need; one-off product names belong under technologies, not topics.

1. Renaming a slug is a breaking taxonomy change unless the old slug remains an alias for the full V1 lifecycle.

1. The build rejects unknown slugs, duplicate aliases, circular aliases, empty topic/use-case arrays, and deprecated slugs on new records.

| **BACKFILL PRINCIPLE**<br>Add metadata around the existing resource; do not rewrite its title, URL, brief, caveat, date, or attribution merely to make the taxonomy cleaner. |
| --- |

# 7. Search and ranking

V1 search is deterministic lexical retrieval over normalized fields, enriched by controlled synonyms and facets. It should answer descriptive queries well without introducing opaque semantic ranking or a separate database.

## Indexed fields and default weights

| **Field** | **Relative weight** | **Match behavior** |
| --- | --- | --- |
| id / exact URL | Highest | Exact or normalized exact |
| title | 8 | Token, phrase, prefix |
| use_cases | 6 | Slug, label, aliases |
| topics | 4 | Slug, label, aliases |
| technologies | 3 | Exact + aliases |
| interfaces / type | 3 | Exact facet labels |
| brief | 2 | Token + phrase |
| sharer / channel | 0.5 | Exact token |

Weights are implementation defaults, not response-contract guarantees. They may be tuned inside V1 as long as documented filters, exact-ID behavior, and deterministic tie-breaking remain stable.

## Normalization

- Apply Unicode NFKC normalization and case folding; collapse whitespace and punctuation.

- Preserve meaningful developer tokens such as C++, C#, node.js, .NET, and model names through explicit token rules.

- Expand only curated synonyms from taxonomy/synonyms.json; do not use unconstrained model-generated query expansion.

- Treat quoted text as a phrase. Treat remaining terms as AND-preferred with an OR fallback when strict matching returns nothing.

- If the exact query matches an ID or normalized URL, return that record first regardless of field score.

## Ranking order

1. Exact ID or normalized URL match.

1. Exact title and title phrase match.

1. Weighted token relevance using field boosts and inverse document frequency.

1. Phrase bonus when terms occur together in title, use case, or brief.

1. Deterministic tie-break: shared_on descending, then id ascending.

## Filter semantics

- Different facet families are ANDed: topic=frontend plus interface=cli requires both.

- Repeated values inside one family are ORed: topic=frontend,design accepts either.

- Date bounds are inclusive and use shared_on, not collection run time.

- Unknown facet values produce HTTP 400 with invalid_filter; silently ignoring a typo would make results misleading.

- The same query and cursor against the same catalog build returns the same ordering.

## Search index artifact

The build emits a compact index containing document lengths, term document frequencies, per-field postings, normalized exact-title keys, URL keys, and facet bitsets. The function loads this generated artifact; it never parses index.html or scans raw notes at request time.

| **WHY NO VECTOR SEARCH YET**<br>At 285 records, curated metadata and weighted lexical retrieval are easier to test, cache, explain, and operate. Semantic retrieval can be evaluated later against the same gold-query set and added only if it materially improves recall. |
| --- |

# 8. HTTP API contract

All endpoints are read-only, UTF-8 JSON, and versioned in the path. V1 is public by default and supports GET, HEAD, and OPTIONS. Write operations and authentication are outside scope.

## Endpoints

| **Method + path** | **Purpose** | **Cache** |
| --- | --- | --- |
| GET /api/v1/resources | List + filter resources | 5 min |
| GET /api/v1/resources/{id} | Fetch one stable record | 1 hour |
| GET /api/v1/search | Rank a text query | 1 min |
| GET /api/v1/facets | Values + result counts | 5 min |
| GET /api/v1/taxonomy | Definitions + aliases | 1 hour |
| GET /api/v1/meta | Build + freshness metadata | 1 min |
| GET /api/v1/catalog.json | Full static export | 5 min |
| GET /api/v1/openapi.json | OpenAPI 3.1 contract | 1 hour |

## List and search parameters

| **Parameter** | **Shape** | **Rule** |
| --- | --- | --- |
| q | string | Search only; 2–256 chars |
| type | CSV slugs | OR within facet |
| topic | CSV slugs | OR within facet |
| use_case | CSV slugs | OR within facet |
| interface | CSV slugs | OR within facet |
| technology | CSV slugs | OR within facet |
| channel | CSV slugs | share-tech or providers |
| from / to | YYYY-MM-DD | Inclusive bounds |
| sort | enum | relevance, newest, title |
| limit | integer | Default 20; max 100 |
| cursor | opaque | Do not parse client-side |
| fields | CSV | Optional sparse field set |

## Response envelope

| {<br>  "data": [ /* Resource objects */ ],<br>  "meta": {<br>    "api_version": "v1",<br>    "catalog_version": "2026-09-29T02:35:57Z",<br>    "query": "parallel coding agents",<br>    "total": 4,<br>    "limit": 20,<br>    "next_cursor": null<br>  }<br>} |
| --- |

## Single-resource response

| {<br>  "data": { /* one Resource object */ },<br>  "meta": {<br>    "api_version": "v1",<br>    "catalog_version": "2026-09-29T02:35:57Z"<br>  }<br>} |
| --- |

## Error model

| {<br>  "error": {<br>    "code": "invalid_filter",<br>    "message": "Unknown topic: front-end",<br>    "field": "topic"<br>  },<br>  "meta": {"api_version": "v1"}<br>} |
| --- |

| **Status** | **Code** | **When** |
| --- | --- | --- |
| 400 | invalid_query | Malformed q, date, sort, or cursor |
| 400 | invalid_filter | Unknown taxonomy value |
| 404 | not_found | No resource for ID |
| 405 | method_not_allowed | Non-read method |
| 429 | rate_limited | Edge protection triggered |
| 500 | internal_error | Unexpected function failure |
| 503 | catalog_unavailable | Index or catalog not loadable |

## HTTP behavior

- Return Content-Type: application/json; charset=utf-8, ETag, Last-Modified, and Cache-Control on successful responses.

- Honor If-None-Match and return 304 when the selected representation is unchanged.

- Set Access-Control-Allow-Origin: * for public GET access. Do not allow credentials.

- Return a Retry-After header on 429. The numeric threshold is an operational setting, not an API guarantee.

- Reject unsupported methods rather than accepting bodies that are ignored.

## Versioning

- The major version is in the path. Additive optional fields may ship within V1.

- Removing or renaming a field, changing its type, changing filter logic, or repurposing an enum requires V2.

- New taxonomy values are additive. Renaming a taxonomy slug requires an alias during V1.

- catalog_version identifies a concrete generated snapshot; it is not the API major version.

# 9. Build and compatibility

## Build sequence

1. Parse and validate every canonical record against JSON Schema 2020-12 [S1].

1. Validate taxonomy references, aliases, dates, URLs, and per-field limits.

1. Run exact-URL and project-identity duplicate checks; fail on any unreviewed collision.

1. Generate legacy data.json in its existing field order and semantics.

1. Generate index.html, weekly Markdown, RSS, and existing analytics exactly as today.

1. Generate catalog.json, taxonomy.json, facets.json, meta.json, per-resource JSON, OpenAPI, and the search index.

1. Run frozen-input compatibility diffs and API contract tests.

1. Produce a deployment manifest and handoff checklist. Cloudflare deployment and live smoke tests are external gates, not repository-side completion.

## Compatibility adapter

The current site expects title, week, url, sharer, date, categories, brief, id, and warning. The builder must derive that exact legacy shape from the canonical record. During migration, a frozen 285-record input must produce a byte-identical data.json and no interface-template diff.

| legacy.title      <- title<br>legacy.week       <- display_period (or "providers" collection label)<br>legacy.url        <- canonical_url<br>legacy.sharer     <- source.sharer<br>legacy.date       <- formatted shared_on, without year<br>legacy.categories <- legacy_categories<br>legacy.brief      <- brief<br>legacy.id         <- id<br>legacy.warning    <- caveat or "" |
| --- |

## Static-first delivery

- catalog.json, taxonomy.json, facets.json, meta.json, OpenAPI, and per-resource files are deployable as normal Pages assets.

- The resources and search functions read the generated catalog/index from the same deployment, preventing version skew.

- If the function is unavailable, the full static catalog remains usable; the site remains unaffected.

- No database is needed for V1. A durable store becomes useful only for high write volume, personalization, or event-level analytics.

## Privacy and exposure

- Return only public catalog fields. Never expose raw Discord text, message IDs, channel IDs, deleted candidates, internal research notes, or dedupe evidence.

- Sharer handles are included because they are already part of the public library. If that policy changes, omit them through a catalog-level visibility flag rather than editing source history.

- Do not accept user-supplied regular expressions or executable query syntax. Bound query length, result size, and cursor lifetime.

- OpenAPI descriptions must distinguish editorial summaries from independently verified metadata.

# 10. Evidence-gated implementation plan

The work below is deliberately split into repository-side phases that can be completed with the existing GitHub access and local test environment. No phase requires access to the Cloudflare dashboard. A phase is complete only when its stated evidence artifact exists and its exit gate passes.

| **WHAT CAN PROCEED NOW**<br>Schema, taxonomy, migration tooling, legacy-output compatibility, static API artifacts, a locally tested query engine, OpenAPI documentation, repository tests, and a reviewable pull request can all be prepared without Cloudflare access. |
| --- |

| **Phase** | **Repository deliverable** | **Exit evidence** |
| --- | --- | --- |
| 0 — Baseline | Manifest + hashes | Pinned commit; clean rebuild |
| 1 — Safety | Regression harness | Current outputs pass |
| 2 — Contract | Schemas + taxonomy | Fixtures validate |
| 3 — Migrate | 285 canonical records | IDs/text preserved |
| 4 — Generate | Legacy + API assets | Zero baseline drift |
| 5 — Search | Index + query core | Gold set measured |
| 6 — API | OpenAPI + adapter | Local contract tests |
| 7 — Handoff | PR + runbook | Owner review ready |

## Phase 0 — Freeze evidence before code changes

Observed baseline: commit 31773ab is the current main snapshot used for this plan. Its tree has no test directory, package manifest, GitHub Actions workflow, Wrangler configuration, functions directory, or canonical catalog directory. The documented source of truth is notes/, raw/ is append-only, and scripts/build.py generates the public outputs. [E1] [E2] [E3] [E4]

- Create a feature branch from the pinned commit; do not change main during the exploratory work.

- Record SHA-256 hashes for index.html, data.json, feed.xml, og-image.png, CHANGELOG.md, and weeks/*.md.

- Record the ordered list of IDs and every current public field for all 285 rows.

- Save a machine-readable inventory: 285 resources; 203 share-tech; 82 providers; 285 unique IDs; 285 unique exact URLs; 69 non-empty warnings; six current category labels. [E5]

Exit gate: a clean checkout rebuilds with no tracked-file diff, and the manifest is committed beside the tests. This was reproduced locally for the pinned baseline; the repository still needs the check encoded as a repeatable test. [E4]

## Phase 1 — Put a safety harness around the existing builder

The current builder is a single Python script that parses notes, derives IDs from titles, and rewrites data.json, weeks/, CHANGELOG.md, index.html, og-image.png, and feed.xml. The repository currently has no automated test suite or continuous-integration workflow. [E4] [E1]

- Add tests that run the existing builder against a frozen fixture and compare generated bytes or approved semantic snapshots.

- Add focused tests for week parsing, provider ordering, warning extraction, slug collision behavior, and the current nine-field data.json shape.

- Add invariant tests for ID uniqueness, exact-URL uniqueness, HTTPS URLs, known category values, and required fields.

- Keep test tooling dependency-light; record exact setup in the repository rather than assuming a hosted runner.

Exit gate: all tests pass against unmodified production inputs, and no generated site file changes. This gate converts the observed clean rebuild into durable regression protection.

## Phase 2 — Define contracts without changing public output

Add JSON Schema 2020-12 files for canonical resources, taxonomy registries, static exports, and API envelopes. JSON Schema is the machine-checkable contract; OpenAPI describes the HTTP surface. [S1] [S2]

- Represent unknown factual metadata as null or omit it according to the schema; never infer licenses, open-source status, technologies, or verification state from naming alone.

- Keep current categories in legacy_categories. Introduce resource_type, topics, use_cases, interfaces, and technologies as separate controlled facets.

- Give every taxonomy slug a label, definition, aliases, and status; reject unknown or duplicate aliases.

- Treat numeric limits in this draft as proposed policy. The current observed maxima are 52 title characters, 643 brief characters, 96 URL characters, 50 ID characters, and three categories per row. [E5]

Exit gate: schemas validate representative positive fixtures and reject invalid IDs, dates, URLs, unknown taxonomy slugs, extra fields, and leaked internal provenance.

## Phase 3 — Migrate 285 records with preservation proofs

Write a deterministic migration program that reads current generated data plus curated notes and writes one canonical record per current ID. The program must preserve title, URL, brief, warning, sharer, visible date, week label, ordering, and ID exactly unless a separately reviewed correction is approved.

- Do not call the current IDs immutable until this phase stores them explicitly: scripts/build.py presently regenerates slugs from titles on every build. [E4]

- For 203 dated-week records, derive the year from the parsed week and assert that the day/month falls within the week. [E5]

- For 82 provider records, do not infer a year from the builder’s RSS fallback. Resolve shared_on from the curated/raw source evidence or leave migration blocked for that row. [E3] [E4]

- Generate a preservation report with old/new field comparisons and an exceptions file that must be empty or explicitly approved.

Exit gate: 285 canonical files validate; 285 IDs remain unchanged; all protected legacy fields compare equal; every ISO date has traceable source evidence.

## Phase 4 — Generate new artifacts while preserving the site

Refactor generation behind a compatibility adapter rather than replacing the renderer. The canonical catalog may become the long-term source of truth only after it reproduces every current artifact required by the site.

- Generate legacy data.json with the same key order, values, record order, indentation, and final-newline behavior as the pinned baseline.

- Generate catalog.json, taxonomy.json, facets.json, meta.json, per-resource JSON, and the search index into versioned paths.

- Keep index.html markup, CSS, JavaScript, section order, badges, week numbering, and theme code outside the change set.

- Run the old and new paths on the frozen baseline and publish a diff report.

Exit gate: no diff in the frozen legacy outputs, except a change explicitly enumerated and approved before merge. This is the hard UI-protection gate.

## Phase 5 — Build and measure deterministic search locally

Implement a pure query module over the generated index. Normalize a search copy of text, not the stored editorial fields. Unicode NFKC is suitable only for search-time compatibility matching because it can discard distinctions; stored text remains untouched. [S4]

- Support exact ID and normalized exact-URL lookup, quoted phrases, weighted title/use-case/topic/brief matching, controlled aliases, filters, sorting, and cursor pagination.

- Create a versioned gold set of at least 40 reviewed queries before tuning weights. Include exact identity, natural-language intent, multi-facet filters, dates, channels, typos, and no-result cases.

- Report top-1, top-5, no-result precision, and per-query failures. The proposed 90% top-5 threshold is a launch target, not a current measurement.

- Benchmark locally and record corpus size, hardware context, warm/cold runs, and index bytes. Do not present local latency as Cloudflare edge latency.

Exit gate: exact-ID queries rank first; pagination is stable inside one catalog version; the measured gold-set result meets the approved threshold or the shortfall is documented.

## Phase 6 — Produce the API contract and local adapter

Write openapi.json and a framework-light request adapter for the documented GET, HEAD, and OPTIONS endpoints. OpenAPI is used because it provides a language-agnostic, machine-readable API description. [S2]

- Test every route, parameter, filter, status code, sparse-field option, cursor, and error envelope locally against the generated artifacts.

- Generate ETags from representation bytes and test If-None-Match/304 behavior according to HTTP semantics. [S3]

- Test public CORS headers without credentials and reject unsupported methods and overlong inputs.

- Keep the adapter isolated so removing it leaves all current static site outputs untouched.

Exit gate: OpenAPI validation and local contract tests pass; static catalog access works with the adapter disabled. This does not establish production edge behavior.

## Phase 7 — Prepare a reviewable handoff

Package the repository work as small, ordered commits or a pull request: baseline tests; schemas/taxonomy; migrator; generator; search; API contract/adapter; documentation. Each commit must pass the prior phase’s gates.

- Include exact commands for build, test, corpus audit, compatibility diff, and local API smoke tests.

- Include generated sizes, the gold-query report, unresolved classification decisions, and a rollback procedure.

- Do not merge, deploy, expose a public endpoint, or change the daily job until the owner approves those distinct steps.

Exit gate: the owner can review repository evidence without Cloudflare access, and the Cloudflare operator receives a separate deployment checklist.

# 11. Cloudflare handoff boundary

Cloudflare access is not available for this work. The repository currently contains no Wrangler configuration or checked-in Cloudflare project settings, so the deployment environment cannot be reconstructed or verified from the repository alone. [E1]

| **Can be completed** | **Requires Cloudflare access** |
| --- | --- |
| Schemas and migration | Project/build settings |
| Static API artifacts | Preview/production deploy |
| Local query + route tests | Pages routing confirmation |
| OpenAPI and runbook | Custom-domain activation |
| Compatibility diff | Edge cache/CORS verification |
| Local benchmarks | Production latency/logs |

## Cloudflare-dependent acceptance gates

- Deploy to a preview environment and verify every endpoint on the preview URL.

- Confirm Pages Function routing does not shadow index.html, static assets, or existing paths.

- Verify Cache-Control, ETag/304, CORS, HEAD, OPTIONS, and error responses at the edge.

- Measure production-like p50/p95 latency; the draft’s 200 ms p95 is a target until measured.

- Activate the custom-domain route only after preview evidence is accepted; then smoke-test both domains.

- Confirm logs, error visibility, abuse controls, and rollback permissions before publication.

| **CLAIM BOUNDARY**<br>Repository completion means code and evidence are ready for deployment. It does not mean the API is live, reachable, correctly cached at the edge, or operating within a latency target. Those claims require Cloudflare-side verification. |
| --- |

# 12. Validation and acceptance

## Build-blocking catalog checks

- Every resource validates against schema_version 1.0 and its filename matches id.

- IDs, canonical URLs, and normalized identity keys are unique unless a reviewed exception exists.

- All resource_type, topic, use_case, interface, and technology slugs exist in the taxonomy registry.

- shared_on is a valid calendar date; display_period is present for legacy rendering.

- No public record contains internal message IDs, Discord channel IDs, raw collection text, or unsupported private fields.

- The full catalog count equals the sum of source-channel facet counts.

## Compatibility checks

- Frozen input produces all 285 legacy rows in the same order with the same id, title, URL, brief, warning, sharer, date, week, and category values.

- The HTML template, CSS, JavaScript behavior, theme, layout, badges, week numbering, and section order have no diff.

- A normal new-resource run changes only data-driven output and approved metadata such as count and update time.

- Existing #r-<id> anchors still point to the same resource card.

## API contract checks

- Every documented endpoint and parameter is represented in openapi.json and validated in CI.

- Invalid filters, dates, cursor values, methods, and overlong queries return the documented status and error code.

- Pagination never duplicates or skips records within one catalog_version.

- ETag and If-None-Match produce correct 304 behavior.

- CORS permits public GET/HEAD/OPTIONS and does not permit credentials.

- The function and static assets report the same catalog_version.

## Search-quality checks

Create a versioned gold set of at least 40 queries spanning exact titles, IDs, technology names, natural-language use cases, category combinations, date filters, channel filters, and deliberate no-result cases. Before launch, at least 90% of positive queries must place an accepted target in the top five results, and all exact-ID queries must rank first.

| **Query family** | **Example** | **Expected behavior** |
| --- | --- | --- |
| Exact identity | orca | Exact ID first |
| Use case | parallel coding agents | Agent workspaces high |
| Facet intent | frontend component library | Facet + text match |
| Technology | Rust GUI | Technology/title relevance |
| Source/date | providers after 2026-09-01 | Filter correctness |
| No result | unsupported random term | Empty data, HTTP 200 |

## Operational checks

- Measure p50 and p95 search latency from the deployed edge; launch target is p95 under 200 ms for a warm request at current scale.

- Verify catalog.json can be fetched independently if the function is disabled.

- Do not advance the per-channel collection watermark until the catalog build, deploy, and live API/site smoke tests all pass.

- Log build failures and endpoint error counts without logging full user queries by default.

# 13. Decisions and assumptions

## Assumptions requiring approval

- V1 is public and read-only; no API key is required. This is a recommended product decision, not an observed deployment setting.

- Cloudflare Pages remains the deployment platform; this is inherited from the repository documentation, not verified against the Cloudflare account. [E2] [E3]

- The current 285 IDs, URLs, editorial copy, attribution, and visible chronology are preserved.

- Sharer handles remain in API responses because they are already visible on the site.

- Lexical ranking and facets ship before semantic retrieval.

- API publication requires a separate approval after preview/shadow validation by someone with Cloudflare access.

## Review decisions before implementation

| **Decision** | **Recommended default** | **Impact** |
| --- | --- | --- |
| Sharer attribution | Keep public | Matches current library |
| Full export | JSON array | Simplest client use |
| Deprecation window | Set before launch | External commitment |
| Search telemetry | Aggregate only | Lower privacy cost |
| Typos | Fallback only | Recall without noisy ranking |

## Deferred extensions

- Semantic or hybrid search, evaluated against the same gold set rather than adopted by default.

- Related-resource recommendations derived from reviewed topic/use-case overlap, not from rejected duplicate aliases.

- API keys and quotas if real usage creates an operational need.

- Delta feeds, webhooks, and change-history endpoints for synchronization clients.

- A GraphQL surface only if consumers demonstrate cross-resource query patterns that REST cannot serve cleanly.

- UI integration, if later approved, consuming the same search endpoint without changing the underlying catalog contract.

# 14. Evidence register

Evidence was captured against the pinned repository snapshot below. Repository observations are reproducible from the linked files; proposed architecture, thresholds, and schedules remain recommendations until implemented and measured.

**[E1] Pinned repository snapshot. ** — Tree and history baseline used for the audit; latest commit in scope dated 29 September 2026.

**[E2] Repository README. ** — Documents notes/ as source of truth, generated outputs, static hosting, and the no-build Cloudflare Pages model.

**[E3] Repository operating rules. ** — Documents read-only collection, append-only raw logs, fixed current categories, provider handling, and generated-file boundaries.

**[E4] Current build script. ** — Shows notes parsing, title-derived IDs, provider ordering, and generation of the present outputs.

**[E5] Current dataset. ** — Audited at 285 rows with a uniform nine-field shape, 285 unique IDs, 285 unique exact URLs, 203 share-tech rows, and 82 provider rows.

**[S1] JSON Schema 2020-12. ** — Official core specification for the proposed machine-validation dialect.

**[S2] OpenAPI Specification 3.1.1. ** — Defines the language-agnostic HTTP API description used for the proposed contract.

**[S3] HTTP Semantics (RFC 9110 reference). ** — Official HTTP semantics reference for GET/HEAD, status codes, ETag, If-None-Match, and 304 behavior.

**[S4] Unicode normalization forms. ** — Reference for NFKC compatibility normalization and its information-loss caveat.

## Audit method and limits

- The dataset audit parsed data.json directly and counted rows, source buckets, field presence, category assignments, warnings, exact IDs, exact URLs, URL schemes, and field lengths.

- The clean-build check ran python3 scripts/build.py in a fresh clone at E1 and compared tracked output hashes before and after; no tracked file changed.

- Exact URL uniqueness is not project-identity uniqueness. The existing editorial dedupe rule still requires reviewed alias evidence for same-project URLs.

- No Cloudflare dashboard, deployment logs, bindings, domains, cache behavior, or live function metrics were inspected. Cloudflare-side claims are therefore withheld.
