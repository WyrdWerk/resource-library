## Details

### blessed-rs
- Details: Blessed.rs is a community-curated guide to the Rust ecosystem, maintained by Niko Burns and contributors, with about 1.6k stars on GitHub. Instead of a flat awesome-list, it organizes the ecosystem into categories with recommended crates and tooling, making it a practical starting map when choosing Rust dependencies. The guide is built as a small Rust site from data files, so the curation itself is version-controlled and reviewable. Treat its "blessed" picks as the maintainers' informed opinions rather than an official standard.

### one
- Details: One is a Mac app that acts as a mission-control Inbox for coding agents you already run — Claude Code, Codex, OpenCode, Pi, and Grok. Agents you start (in the bundled herdr terminal, on the Mac, or on connected Linux servers) surface their questions and finished work as cards in one toolbar, and you answer, redirect, or talk to them by voice. The free tier covers 25 requests a day; Pro ($12.99/month or $119.88/year) adds unlimited usage and premium routing, and a limited pay-once Lifetime tier ($229–$299) lets you bring your own API keys. One is not itself a coding agent — it orchestrates the ones you run, and requests route through One's servers. Pricing and privacy claims are vendor-reported.

### procedural-film
- Details: procedural-film is an agent skill (MIT, ~500 stars) that turns a topic into a short vertical film or even a playable NES-style pixel-art platformer. Every pixel is drawn in vanilla JavaScript on canvas and every sound is synthesized in Web Audio, so each film ships as one self-contained HTML player plus MP4 exports with zero media assets. The repo's reference film — a 32-second monarch-butterfly life cycle — and the playable Claude Quest game show the pipeline end to end. Expect a long, token-heavy run: the skill dispatches one agent per shot with critic-review waves over every shot.

### orbs
- Details: Orbs is an open-source, self-hosted multi-bot chat by Pedro Martins (MIT, very fresh — days old at collection). You create bots with names, instructions, and models; an LLM judge called Jev routes each turn to the right bot, and a daemon on your own machine runs every turn through Pi, reaching Codex, Claude, Grok, OpenRouter, and more. The stack is TanStack Start, oRPC, and Bun, with optional Cloudflare hosting (Workers, D1, R2). Warning: bots run Pi's tools (read, bash, edit, write) as your user in a work directory with no sandbox — treat it as experimental.

### shaders
- Details: Shaders is a library of 200+ real-WebGPU visual effects as components for React, Vue, Svelte, Solid, and vanilla JavaScript, open-sourced under MIT (~2.5k stars) by Shader Effects, Inc. The package ships typed, SSR-safe components plus a free visual design editor at shaders.com that exports the exact component tree for your framework, a CLI that syncs designed effects into your codebase, an agent skill, and an MCP server for Claude Code, Cursor, Codex, and others. Everything core is free; a paid Pro tier adds 1,000+ presets, website sections, and watermark-free HD rendering. Adoption claims are vendor-reported.

### opendesign
- Details: OpenDesign is a zero-config design agent sold as a subscription from $8 to $120/month, and its plans bundle model credits with an API key. The API can call both Design Plan models and a roster of hosted models — DeepSeek V4 and V4.1 Flash, Kimi K2.7 Code, GPT-6 Luna, MiMo V2.6 Pro and Flash, GLM-5.3 Flash — with a published per-model usage table and 162+ skill workflows plus 152+ design systems. Caveat: this is primarily a design product; the model API is one feature, and BYOK provider keys are supported on every plan. Pricing figures are vendor-reported.

### claude-monthly-api-credits-for-max-and-team-plans
- Details: Anthropic's help article documents the monthly Claude Platform API credits rolling out to Max and Team subscribers: $100/month on Max 5x, $200 on Max 20x, and up to $500 pooled across seats on Team plans, claimed into a linked Claude Console organization. The credits work with any Claude model on the platform, including the Agent SDK and self-run claude -p usage, but explicitly do not cover interactive Claude Code sessions or over-limit usage. Eligibility details may shift as the rollout completes — the article was updated the day it was collected.

### openrouter-claude-haiku-5-5
- Details: OpenRouter's model page for Claude Haiku 5.5, Anthropic's small fast model with a 1M-token context window, priced at $0.10/$0.50 per million input/output tokens with cheap cache reads. Five providers serve it (Vertex, AWS, Azure, Anthropic, Bedrock); OpenRouter routes across them with Balanced, Nitro, Floor, and Exacto modes and automatic failover. The page carries live pricing, throughput, latency, uptime, and benchmark figures plus the top apps sending traffic to the model — the same provider-comparison pattern as the published Artificial Analysis model pages. Figures are live and will shift.

### anthropic-claude-haiku-5-5
- Details: Anthropic's announcement page for Claude Haiku 5.5, positioned as its cheapest, fastest, and most capable small model — about 75% cheaper to run than Haiku 4.5, with a 1M context window, adjustable effort, and strong showings on knowledge work, computer use, and agentic coding benchmarks. The same announcement halves Sonnet 5.5 cache-read pricing (making most agentic work ~20% cheaper) and introduces the monthly API credits for Max and Team subscribers. Available on the Claude Platform, AWS, Google Cloud, and Azure. All benchmarks and pricing are vendor-reported.

### opendocrouter
- Details: OpenDocRouter is LlamaIndex's unified API for document parsing, launched 7 October 2026: one endpoint serves a lineup of frontier and open-weight OCR/parsing models — Claude Opus 5.5, GPT-6 Luna, MinerU, PaddleOCR-VL, and others — each versioned with a parsing recipe and benchmarked on ParseBench for quality and cost. Billing is purely per token with no markup over providers' prices; new accounts start with $5 of free credit. An optional layout engine adds grounded bounding boxes to any model's output. Very fresh — treat reliability as unproven.

### neuralwatt-mimo-v2-6-pro
- Details: Neuralwatt Cloud's model page for Xiaomi's MiMo-V2.6-Pro (sparse MoE, 1M-token context, native vision and tool calling), served at $0.87/$1.74 per million input/output tokens with a 35%-off Flex tier for non-urgent work. The page publishes live latency and throughput stats, per-request energy consumption figures, and OpenAI-compatible API examples. The model is in preview, so rate limits and stability are subject to change. Model-specific page under the already-published Neuralwatt provider entry.
