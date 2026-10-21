## Details

### tsrs-typescript-ported-to-rust
- Details: tsrs is a Rust port of the TypeScript compiler, built by Cloudflare with VoidZero and Max Schwenk and incubated inside the Oxc toolchain in close collaboration with the TypeScript team. Early benchmarks claim up to 8x faster type-checking and ~70% less memory than TypeScript 7.0, with an experimental release installable via npm (npx tsrs). Rust was chosen for its WebAssembly story — no garbage collector to bundle — so full dev toolchains could eventually run sandboxed on Cloudflare Workers, in the browser, or on embedded devices. The project plans to merge with Theo Browne's tsc-rs and contribute performance wins back to the official TypeScript Go codebase; the speedup and memory figures are vendor-published and unverified.

### bettersearch
- Details: bettersearch gives any AI agent a deep-research capability on top of DeepSeek's Search API: it spawns subagents, fact-checks what it finds, and produces a clean HTML report. Tagged for agent skills, Claude Code, and Codex, it works as a drop-in research primitive for agents that need web-grounded answers. MIT licensed. Young repo (created October 2026) with a small star count — evaluate before depending on it.

### bb-plugin-millivolt
- Details: A bb agent-framework plugin that installs, adopts, repairs, updates, and rolls back the millivolt inference proxy, surfacing its dashboard in the bb sidebar. The author marks it experimental, so expect rough edges. It pairs with the millivolt proxy repo shared the same day — the plugin manages the proxy; it is not the proxy itself. MIT licensed.

### millivolt
- Details: millivolt is a self-hosted, OpenAI-compatible inference proxy written in Go, with a live dashboard, SQLite request history, routing controls, and operator tooling. It lets you see every AI request while keeping your own API keys and routing. MIT licensed, with docs at llm-4-people.github.io/millivolt. It was shared for reference with minimal context in the original message.

### bb-plugin-deepseek-harness
- Details: A bb agent-framework plugin that provisions DeepSeek Harness (dsh) with one command, offering Standard, Creator, and Minimal modes plus harness slash commands. The author marks it experimental, so expect rough edges. It is distinct from the published DeepSeek Harness entries (the official harness page and its announcement) — this plugin installs and manages the harness from bb rather than being the harness itself. MIT licensed.

### deepinfer
- Details: DeepInfer is the high-performance inference framework DeepSeek says powers its own large-scale production services, open-sourced under Apache 2.0. It ships custom kernels (FlashMLA, DeepGEMM, DeepEP, TileKernels), speculative decoding, asynchronous batch scheduling, and structured outputs, targeting Nvidia SM100 GPUs and Huawei Ascend 950 NPUs with DeepSeek-V4.1-Flash as the first supported model. DeepSeek reports 155 trillion tokens per day per cluster with a 96% input cache hit rate — vendor figures, unverified. It was originally built primarily on vLLM, with inspiration from SGLang and TensorRT-LLM.

### oss-scanner
- Details: OSS Scanner is Anthropic's free, opt-in vulnerability-scanning service for open-source projects: enrolled projects receive periodic scans from Anthropic's strongest models, with findings and candidate patches emailed to maintainers. Enrollment happens by pull request to the anthropics/oss-scanner registry repo; the scanner itself runs service-side and is not open source. Reports are fully model-generated without human review, so maintainers must validate findings — false positives are possible, though Anthropic cites an ~88% bar-meeting rate on critical/high findings in its validation. Anthropic covers the scanning cost.
