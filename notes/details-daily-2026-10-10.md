## Details

### mac-orbs
- Details: Mac Orbs is Amp's native macOS app, currently in beta ("It's Morbin' Time — Amp just got a Mac. Join the Beta"). The landing page presents an orb-style agent interface and references a SwiftUI codebase with TestFlight builds (version 2.4 shown), positioning it as the Mac client for Amp's coding agents. Pricing, system requirements, and the beta timeline are not stated on the page, so treat availability and feature claims as vendor-reported.

### maritime
- Details: Maritime sells per-agent VM hosting for AI agents: every agent gets 1 vCPU, 2 GB RAM, and 5 GB SSD, sleeps when idle, and wakes in about a second with all state preserved. Pricing is flat and works out to about $1 per agent per month: Free covers 3 agents forever, Starter is $20/month for 20 machines, Growth $100/month for 100, Scale $500/month for 500, Dedicated $5,000/month for 5,000 — with add-ons for extra RAM, SSD, and always-on machines, and sleeping machines free. Support is via Discord on lower tiers and private Slack on higher ones; all figures are vendor-reported and subject to change.

### deno-is-joining-cloudflare
- Details: On October 9, 2026, Ryan Dahl announced that the entire Deno team is joining Cloudflare to take Deno's runtime work further, citing a shared ambition around compute, storage, and communication without every application assembling its own infrastructure. The post frames the move as a continuation of Deno Deploy and celld, a distributed-application model built on the Cloudflare Workers programming model with scaling built into the programming model. This is an announcement of a team move, not a product launch — concrete product implications are unstated.

### plexus
- Details: Plexus is a unified API gateway for multiple AI providers (OpenAI, Anthropic, Gemini, and others) that lets client code switch models and providers without changes, exposing OpenAI-compatible endpoints. It features OAuth authentication (the sharer reports OAuth support for Claude Pro or Max accounts — unverified), plus quota tracking, embeddings, and transcriptions. The repo has around 235 stars and 53 forks; maturity and production-readiness are unevaluated beyond the README claims.

### pi-anthropic-auth
- Details: pi-anthropic-auth is a Pi extension package that adds Anthropic OAuth compatibility, letting the Pi coding agent run on Anthropic OAuth credentials. The repo carries an MIT license with about 354 stars and 31 forks. The sharer describes it as "very safe", but that is one user's opinion, not a security audit — routing OAuth tokens through community extensions is subject to Anthropic's usage policy, so verify the current terms before use.

### augure-ai
- Details: Augure is a Canadian "sovereign AI" provider aimed at regulated industries, offering chat, knowledge base, legal review, and code products on Canadian-owned infrastructure. Pricing is in Canadian dollars: a free tier (about 25 messages a day), Pro at C$20/month (no message limits, roughly 1,100 messages a week, 100 documents a month), Max at C$80/month (four times the Pro allowance, deep research agents, priority support), and custom Enterprise with SSO and compliance documentation. All plans and compliance claims are vendor-reported.

### openrouter-step-5-preview
- Details: Step 5 Preview is StepFun's flagship model for agentic work, a sparse mixture-of-experts design (27B active out of 600B total parameters) with a 1M-token context window and 64K maximum output, released October 8, 2026. OpenRouter lists it at $1 per million input tokens and $2.70 per million output tokens, served by a single provider with live throughput, latency, and uptime statistics on the page. It is positioned for extended agentic tasks spanning large codebases and documents, with particular strength claimed in finance and software engineering — vendor-reported benchmarks.
