## Details

### arc-cua-arc-driver
- Details: arc-cua is a superfast action layer for computer-use agents on macOS, shipping two tools in one package. arc-driver is a standalone macOS driver that lets an agent (Claude Code, Codex, or any MCP client) observe an app's window and act on its controls in the background without moving the user's cursor or disturbing open windows. arc-cua itself is a decision-model loop that hands bounded desktop subtasks to a fast decision model so a frontier model isn't needed for every click. The author reports it beats cua-driver on most tasks (up to 8x on some); treat the benchmarks as vendor-reported. MIT licensed.

### gdp-ts
- Details: gdp-ts is a tiny TypeScript library, linter, and AI skill implementing Ghosts of Departed Proofs, a system for making API contracts safer at compile time. Sensitive functions are written to demand proof that the caller performed the required authorization check, so a missing or wrong check becomes a type error instead of a runtime bug, with negligible runtime overhead. It ships ESLint and Oxlint presets to catch proof-forging, plus an installable skill that guides coding agents through the pattern. MIT licensed; it gained roughly 700 stars within two days of its 4 Oct release.

### kourier
- Details: Kourier is an open-model inference provider aimed at coding agents, selling flat monthly plans instead of per-token billing: Starter at $20/month for one concurrent request, Pro at $50/month for three, with no request-volume or token quotas. It currently serves DeepSeek V4.1 Flash through an OpenAI-compatible API and says it owns its own GPU clusters. It is a small bootstrapped business with no contractual uptime SLA yet, so reliability is unproven; treat the page as a pricing snapshot.

### lithosai
- Details: LithosAI sells tiered inference for the Kimi K3 open-weights model across Base, Fast, and Ultra tiers billed per million tokens, all serving the same full-precision weights with the full context window and differing only in speed. The Ultra tier advertises 250 to 1000 tokens per second per user. Endpoints are OpenAI-compatible with streaming, tool calling, and prompt caching on by default; speed claims are vendor-reported and the page is a pricing snapshot, not live prices.

### artificial-analysis-deepseek-v4-1-flash-providers
- Details: Artificial Analysis' live comparison of API providers serving DeepSeek V4.1 Flash, currently tracking 21 providers across pricing, output speed, latency, and cache behaviour. LithosAI's Ultra Chat tier is presently the fastest by output speed while DeepInfra is the cheapest by blended price. Figures are benchmark snapshots that shift as Artificial Analysis re-tests providers; use the page for relative comparison rather than as a price quote.
