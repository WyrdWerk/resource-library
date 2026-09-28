# Providers — curated from CheapInfra #providers (2026-07-20 → 2026-09-25)

Methodology: every link-bearing message in #providers across the channel's full lifetime was collected read-only (~673 messages). Candidates were deduped within the channel and against the 184 URLs already published (earliest occurrence wins; normalized-URL dedupe). Each kept entry was independently verified against the public web — pricing, models/API and privacy/retention claims come from the provider's own pages or corroborating sources, never from Discord chatter alone. Discord claims that could not be corroborated are marked as such and never stated as fact. Entries are newest-first by first #providers mention.

## Providers

### Prism Inference
- URL: https://prisminference.com/pricing
- Posted by: thelaggingway, 25 Sep
- Category: providers
- Brief: Pay-as-you-go inference with no minimums across serverless, elastic, private and dedicated endpoints, plus batch. Lists per-model rates (GLM-5.3 $1.40/$4.40, Kimi K3 $3/$15 per 1M tokens) and states strict zero data retention — inputs and outputs are never used for training.

### InferHub
- URL: https://inferhub.dev/pricing
- Posted by: one_phantomic, 21 Sep
- Category: providers
- Brief: Proxy service that pools AI subscriptions into one API. Shared as "a rly interesting proxy" with per-plan pricing on its site.

### AIHubMix
- URL: https://aihubmix.com/
- Posted by: one_phantomic, 20 Sep
- Category: providers
- Brief: Multi-model API with per-model pricing, including a GLM 5.3 coding endpoint. Shared via its GLM 5.3 API pricing page.

### Surplus Intelligence
- URL: https://www.surplusintelligence.ai/
- Posted by: Felix, 17 Sep
- Category: providers
- Brief: OpenAI-compatible inference marketplace that routes each request to the cheapest current offer. Vendor claims ~38% savings via routing; pricing and retention terms weren't independently verified.

### Kitani
- URL: https://kitani.ai/
- Posted by: rah, 15 Sep
- Category: providers
- Brief: Open inference on independent hardware with a prepaid USD balance — the max request cost is reserved, then settled on completion. API is OpenAI-compatible at api.kitani.ai/v1.

### Pareto Inference
- URL: https://paretoinference.com/
- Posted by: Rykuuun, 14 Sep
- Category: providers
- Brief: Pay-per-token inference running on Pareto's own GPUs, including GLM 5.3 Flash. Shared via its pricing page.

### BytePlus ModelArk
- URL: https://www.byteplus.com/en/activity/codingplan
- Posted by: Rykuuun, 14 Sep
- Category: providers
- Brief: BytePlus's Coding Plan for Claude Code, Cursor, Cline, Kilo Code, Roo Code and OpenCode, covering models like Dola-Seed-2.0-pro, GLM-5.1 and DeepSeek V4. Exact plan prices weren't visible on the promo page.

### Parasail
- URL: https://parasail.io/
- Posted by: tom (App), 13 Sep
- Category: providers
- Brief: Inference provider whose homepage FAQ states explicit zero data retention alongside SLA terms. Surfaced in #providers via a comparisons board post.

### Inceptron
- URL: https://inceptron.io/
- Posted by: tom (App), 13 Sep
- Category: providers
- Brief: Inference provider with ISO 27001 certification, GDPR compliance and EU residency. No zero-retention statement was found on its site.

### Subconscious
- URL: https://www.subconscious.dev/pricing
- Posted by: Tom, 13 Sep
- Category: providers
- Brief: An inference platform built for long-running coding agents, using runtime context compression to cut token bills on extended agentic traces; it drops into Claude Code, Codex, OpenCode, or any OpenAI-compatible harness, and can also be deployed inside your own cloud. Plans sell as daily token allocations with no per-seat pricing — Base at $100/month for 60M tokens/day, Pro at $500/month for 300M/day, Heavy at $2,000/month for 1.2B/day — plus per-token overflow billing. Its savings and performance claims (2× faster task completion, up to 80% cost reduction) are vendor-reported and not independently verified.

### FEIHOA
- URL: https://feihoa.com/
- Posted by: Tom, 13 Sep
- Category: providers
- Brief: Unlimited AI plans from €6. States prompts and outputs are not used for training, though it may retain data briefly for security, abuse prevention and legal reasons.

### Crof
- URL: https://crof.ai/
- Posted by: tom (App), 13 Sep
- Category: providers
- Brief: Inference provider at crof.ai; public evidence is thin (snippet-based). Third-party substitution allegations seen during research are unverified and not repeated here.

### Real API Pricing
- URL: https://github.com/FeiZhuLulu/real-api-pricing
- Posted by: JohnDotOwl, 11 Sep
- Category: providers
- Brief: GitHub repo behind the real-api-pricing comparison of actual inference API prices. Its web app is already in this library's web-apps section; this is the distinct source repo.

### OpenCode Go
- URL: https://opencode.ai/go
- Posted by: UT, 10 Sep
- Category: providers
- Brief: OpenCode's own $10/month subscription bringing its agentic coding experience to OpenCode or any agent, with generous per-model request limits on a curated open-source lineup (Kimi K2.7 Code, MiniMax M3, GLM-5.3-Flash, DeepSeek V4.1 Flash, and others) — limits shown as estimated requests per 5-hour window, with optional top-up credits. Free rotating models appear on a limited-time basis; cancel any time. Usage limits are vendor-stated estimates, and the free rotating models are time-limited.

### SingularityAPI
- URL: https://singularityapi.dev/
- Posted by: uur, 10 Sep
- Category: providers
- Brief: A unified AI gateway routing to DeepSeek, Kimi, GLM, and 300+ models through one endpoint, with smart routing by cost, speed, quality, or availability, built-in failover, and usage analytics; it also sells reserved GPU-lane capacity from $0.20/hr for dedicated inference and is currently offering 100% bonus credits on recharges up to $1,000. A forwarded announcement noted DeepSeek-V4.1-Flash going live on the platform. The homepage publishes no per-token price list, and the bonus-credit promo terms are vendor-published.

### DeepSeek clock
- URL: https://deepakness.com/deepseek/
- Posted by: Alp, 10 Sep
- Category: providers
- Brief: Personal utility page showing DeepSeek's live peak/off-peak status in local time with both models' prices either way. Rates match the official docs.

### Token Harbor
- URL: https://tokenharbor.ai/pricing
- Posted by: thelaggingway, 8 Sep
- Category: providers
- Brief: A pass-based inference API: a free tier with a rotating model allowance, an Agent Pass at $1.99/month ($10 included usage, for always-on agent scripts), an Office Pass at $9.99/month ($35 usage), and a Frontier Pass at $99/month ($180 usage) — each tier unlocking progressively heavier models, with boosted models billing at reduced rates. 'Included usage' is measured at the site's own published per-token prices rather than as a cash wallet balance, so the effective deal is vendor-reported and not independently verified.

### StreamLake
- URL: https://www.streamlake.ai/
- Posted by: tom (App), 7 Sep
- Category: providers
- Brief: Kuaishou's AI cloud / model-as-a-service platform with API and SDK integration for online inference. Holds ISO 27001/27017/42001 and MLPS Level 3; no explicit zero-retention statement found.

### CoreWeave
- URL: https://www.coreweave.com/
- Posted by: tom (App), 7 Sep
- Category: providers
- Brief: GPU cloud infrastructure company offering serverless inference APIs, dedicated endpoints and GPU clusters. Infrastructure rather than a retail model API.

### GMI Cloud
- URL: https://gmicloud.ai/
- Posted by: tom (App), 7 Sep
- Category: providers
- Brief: GPU cloud with serverless inference APIs and dedicated endpoints; lists H100 at $2/GPU-hour and H200 at $2.60/GPU-hour.

### Venice
- URL: https://venice.ai/
- Posted by: tom (App), 7 Sep
- Category: providers
- Brief: Private AI chat and API with free entry and paid tiers (Pro $18/mo). Its API carries a zero-data-retention promise.

### Relace
- URL: https://www.relace.ai/
- Posted by: tom (App), 7 Sep
- Category: providers
- Brief: Coding-focused API (Instant Apply model, code retrieval, embeddings, reranking) rather than general LLM inference. Available via Continue.dev, with a self-host/VPC option.

### AntSeed
- URL: https://antseed.com/
- Posted by: Tom, 6 Sep
- Category: providers
- Brief: Open market for AI inference with no account or email required and optional TEE-backed providers. That design is not the same as a universal zero-retention promise.

### Inco
- URL: https://inco.ai/
- Posted by: Tom, 4 Sep
- Category: providers
- Brief: Inference company from the Inco (confidential-computing) team, branding itself 'inference, reimagined for the agentic era.' It open-sourced Splash, a local inference engine claiming 144 tokens/s on an M5 Max with Qwen3.8-27B (integrated into LM Studio), and its earlier DFlash speculative-decoding tech was adopted by SGLang, vLLM, TensorRT-LLM, llama.cpp, plus Meta, NVIDIA, and Xiaomi. The 144 tokens/s figure is a peak vendor-demonstration value, not an independently verified benchmark; the public site is still sparse with no visible pricing or hosted-API details.

### Kenari
- URL: https://kenari.id/
- Posted by: ROman, 3 Sep
- Category: providers
- Brief: An Indonesian AI cloud and gateway: one API key and one Rupiah wallet behind an OpenAI-compatible endpoint, with per-token prices quoted in Rupiah (e.g. DeepSeek V4 Flash at Rp 2,750 input / Rp 5,500 output per 1M tokens, GLM-5.3-Flash at Rp 2,000/Rp 6,000), top-ups from Rp 1,000, free models, and free BYOK routing through its dashboard. Also bundles one-click app hosting ('Pods' — n8n, OpenClaw, a WhatsApp gateway) and monthly plans from Rp 49rb.

### InferenceSaver
- URL: https://www.inferencesaver.com/en
- Posted by: Rykuuun, 3 Sep
- Category: providers
- Brief: Unified API and SDK routing requests across 1,000+ models from many providers with automatic fallbacks, best-price optimization, and a real-time observability dashboard. Markets itself as one API for every AI model, advertising per-model 'up to 70% off' rates and 40–80% savings on inference spend. The savings and discount figures are vendor marketing, not independently verified.

### Nube
- URL: https://nube.sh/
- Posted by: baanish, 30 Aug
- Category: providers
- Brief: Inference API with published per-token pricing. States explicit zero data retention with an upstream no-training clause.

### Cline Pass
- URL: https://cline.bot/
- Posted by: linker, 30 Aug
- Category: providers
- Brief: Subscription for Cline's coding agent at $9.99/mo, positioned as 2–5x the quota versus direct API spend. The "5x cheaper than API" phrasing seen in chatter is not verified.

### Nebius Token Factory
- URL: https://tokenfactory.nebius.com/
- Posted by: ajthemacboy, 30 Aug
- Category: providers
- Brief: Nebius's pay-per-token hosted inference for open text/vision models (~23 models incl. DeepSeek, Llama, Qwen). New accounts get trial credit; uses separate v1 API credentials.

### Coral Bricks
- URL: https://www.coralbricks.ai/
- Posted by: scarywood75, 29 Aug
- Category: providers
- Brief: High-throughput inference aimed at agents. A forwarded promo code (SUPERINT) covered GLM 5.2 and Kimi K3.

### Fast Inference
- URL: https://fast.inference.net/pricing
- Posted by: baanish, 27 Aug
- Category: providers
- Brief: Gateway for AI models and coding agents with provider failover. $9/mo gives $10 gateway credit, $49/mo gives $60, then pay-as-you-go at direct rates.

### Entrim
- URL: https://entrim.ai/
- Posted by: Tom, 25 Aug
- Category: providers
- Brief: $10 in credits plus pay-as-you-go inference. Processes prompts and outputs in RAM only and does not train on them.

### Merge Gateway
- URL: https://merge.dev/
- Posted by: 0xSaiya, 24 Aug
- Category: providers
- Brief: Multi-provider gateway. A Discord-shared "75% off DeepSeek V4 Flash through September 30" promo was not corroborated on its site.

### sference
- URL: https://sference.com/
- Posted by: scarywood75, 21 Aug
- Category: providers
- Brief: Managed inference for open models on European GPUs. Public evidence is snippet-based; details unverified.

### Unifically
- URL: https://unifically.com/
- Posted by: scarywood75, 21 Aug
- Category: providers
- Brief: Pay-per-use multi-model API (no subscription) with a $0.20 free balance and per-generation pricing, e.g. $0.03 per image. The sharer called it "sus" — treat vendor claims cautiously.

### Reflex
- URL: https://spark.reflex.inc/
- Posted by: Alp, 21 Aug
- Category: providers
- Brief: Post-trained Kimi K3 served with 6x context at a claimed 490 tokens/sec. Performance claims come from the provider's own page.

### OpenModels
- URL: https://openmodels.market/plans
- Posted by: Rykuuun, 20 Aug
- Category: providers
- Brief: Credit-subscription marketplace spanning 333 models, 100+ live routes, and 24+ providers: plans from $5/mo ($6 credits) to $99/mo ($110 credits), with credits that never expire and roll over. Every plan unlocks every model route; usage is billed per token based on the selected provider route, and one-time top-ups accept USDC.

### OpenRouter
- URL: https://openrouter.ai/
- Posted by: scarywood75, 19 Aug
- Category: providers
- Brief: Multi-provider model gateway charging a 5.5% fee, with 50 free requests/day. Shared via its GLM 5.3 provider/pricing page.

### TensorX
- URL: https://tensorx.ai/pricing/
- Posted by: Alp, 19 Aug
- Category: providers
- Brief: EU-hosted pay-as-you-go inference whose pricing page states verbatim: "all inference is zero data retention."

### AI Router
- URL: https://airouter.ch/
- Posted by: thelaggingway, 18 Aug
- Category: providers
- Brief: Swiss-hosted inference API ("All of AI. One API. Made in Switzerland") with GDPR compliance and data hosted in Switzerland. Flat CHF 39/mo unlimited under a fair-use policy; OpenAI-compatible at api.airouter.ch/v1.

### B.AI
- URL: https://b.ai/
- Posted by: Tom, 18 Aug
- Category: providers
- Brief: Unified LLM API at api.b.ai/v1 where one key speaks three protocols — OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages — with docs at docs.b.ai. It gained traction for generous free models (DeepSeek-V4-Flash, Tencent HY3, MiMo-V2.5, GLM-5.3-Flash), though its promotions page moved free offers to limited-time 10%-of-reference discounts on 16 Sep 2026, leaving only a 300,000-credit (~$0.30, 30-day) referral gift; login is via Web3 wallet or Google. Homepage details are unverified beyond third-party reviews from mid-Sep 2026, so confirm current pricing on the site itself.

### OrcaRouter
- URL: https://www.orcarouter.ai/
- Posted by: simply soy, 18 Aug
- Category: providers
- Brief: Zero-markup BYOK router with an open-source self-hostable Lite (MIT); the hosted plan includes free credits. Pass-through per-token pricing, e.g. DeepSeek V4 Flash $0.15/$0.29 per 1M in/out.

### OpenFerence
- URL: https://openference.ai/
- Posted by: Tom, 17 Aug
- Category: providers
- Brief: Inference API at openference.ai; public evidence is snippet-based only. A Discord claim that its GLM 5.2 "is not even real" is unverified.

### wafer
- URL: https://wafer.ai/
- Posted by: baanish, 16 Aug
- Category: providers
- Brief: Inference provider, with DeepSeek V4 Flash mentioned on it in later chatter. Surfaced via an X post from @wafer_ai.

### Fireworks AI
- URL: https://fireworks.ai/
- Posted by: baanish, 16 Aug
- Category: providers
- Brief: Serverless inference from $0.10/1M tokens (under 4B params), $1 free starter credit, 50% off batch. 100–400+ open models with an OpenAI-compatible API, FireAttention engine, LoRA/RFT fine-tuning and dedicated GPUs.

### RunInfra
- URL: https://runinfra.ai/
- Posted by: Aditya Borkar, 16 Aug
- Category: providers
- Brief: Inference provider; its DeepSeek V4 Flash $0.13/M input price was corroborated. A "1.8¢/M blended" figure seen in chatter is not a list price.

### Freebuff
- URL: https://freebuff.com/
- Posted by: Rykuuun, 14 Aug
- Category: providers
- Brief: Free, ad-supported coding agent (CLI, desktop, web, cloud, chat) powered by open models like DeepSeek V4 Pro/Flash and MiniMax M3. Explicit no-training stance — it doesn't share data with third parties that would train on it.

### GripHubRouter
- URL: https://griphubrouter.com/
- Posted by: Febryan, 14 Aug
- Category: providers
- Brief: A pay-as-you-go multi-model router aimed at Indonesian developers: 47 models from 12 vendors behind one OpenAI-compatible endpoint, with credits at Rp 300 each, top-ups from Rp 15,000 via QRIS, and no subscription or foreign card required. A one-click installer wires it into VS Code, Claude Code, OpenCode, GitHub Copilot, and Hermes Agent, and a live status widget shows gateway response times.

### Melious
- URL: https://melious.ai/
- Posted by: Sewer56, 14 Aug
- Category: providers
- Brief: EU-hosted pay-as-you-go inference; the sharer cited ~240 tok/s on DeepSeek V4 Flash. States it does not train on user data.

### SiliconFlow
- URL: https://www.siliconflow.com/
- Posted by: thelaggingway, 14 Aug
- Category: providers
- Brief: One OpenAI-compatible API for open and commercial LLMs with serverless pay-as-you-go and dedicated endpoints. Homepage claim: "No data stored, ever."

### CheaperInference
- URL: https://cheaperinference.com/
- Posted by: 0xSaiya, 14 Aug
- Category: providers
- Brief: Pay-as-you-go inference with published example rates. Prompt and response bodies are not logged, with zero data retention on supported routes.

### Novita
- URL: https://novita.ai/
- Posted by: kenn, 13 Aug
- Category: providers
- Brief: AI-native cloud combining serverless model APIs (200+ models through one API, billed per token) with dedicated private endpoints, secure isolated agent sandboxes, and GPU cloud (on-demand instances, serverless GPU, bare metal). One platform for the full AI stack — model APIs, GPUs, and agent runtimes — backed by testimonials from Hugging Face, Kilo Code, and Fish Audio. Its 'up to 50% less than major cloud providers' claim is vendor-reported and not independently verified.

### Command Code
- URL: https://commandcode.ai/docs/plans/goat
- Posted by: Alp, 13 Aug
- Category: providers
- Brief: GOAT plan — $10/mo for $70 in credits (limits $14/5h, $35/week, $70/month) across 30+ open and closed models. No zero-retention statement found.

### DeepSeek
- URL: https://api-docs.deepseek.com/quick_start/pricing
- Posted by: Sewer56, 13 Aug
- Category: providers
- Brief: DeepSeek's official API pricing: pay-as-you-go with 50% off-peak discounts (Flash $0.15/$0.60, Pro $0.66/$1.98 per 1M in/out on cache miss; peak is 2x). The $0.13/$0.30 figures seen in Discord are stale.

### YOLO Auto
- URL: https://yolo-auto.com/
- Posted by: Rykuuun, 12 Aug
- Category: providers
- Brief: Unlimited-token API plans, currently $19/$39 — the Discord-era $6/mo claim is superseded. Shared as an unlimited Qwen3.6-35B API.

### Claudin.io
- URL: https://claudin.io/
- Posted by: Rykuuun, 12 Aug
- Category: providers
- Brief: Credit-based subscription for coding agents: plans run $19/mo (3,000 credits) to $399/mo (72,000 credits), a typical request on their tuned Claudinio model costs about one credit, and there is no hourly cap — a hot month is fixed with a top-up instead of waiting for a clock. Catalogue models (DeepSeek V4.1 Flash, GLM-5.3, Kimi K3, Claude Opus, GPT-6, Gemini, Grok) cost a fixed 2×–36× multiple of a credit, and one API key plugs into Claude Code, Cursor, Cline, and other OpenAI/Anthropic-compatible clients.

### regolo.ai
- URL: https://regolo.ai/pricing/
- Posted by: Rykuuun, 12 Aug
- Category: providers
- Brief: European inference platform with EUR per-token pay-as-you-go (e.g. Llama-3.3-70B €0.60/€2.70 per 1M in/out) and 70% off the first 3 months. Marketing claim: "Zero data retention on European green infrastructure."

### Arli AI
- URL: https://arliai.com/
- Posted by: Rykuuun, 12 Aug
- Category: providers
- Brief: Inference API with unlimited-request plans and an explicit zero-logging statement. The sharer noted it seemed new and unstable.

### Hetzner
- URL: https://inference.hetzner.com/api/v1
- Posted by: baanish, 11 Aug
- Category: providers
- Brief: Hetzner's free experimental open-weight LLM inference API (announced July 2026), EU-hosted. Roughly 4M input / 100k output tokens per 60s per key, no SLA — not for production.

### Synthetic
- URL: https://synthetic.new/
- Posted by: baanish, 8 Aug
- Category: providers
- Brief: $30/month subscription (or usage-based billing) for running LLMs privately, usable in its own app or any OpenAI-compatible tool (Roo, Cline, Octofriend). It also built Synbad, an open-source evaluation suite sourced from real coding-agent bugs, and positions itself as coding-agent-optimized inference. Synbad's '100% vs as low as 66%' pass-rate comparison is vendor marketing, not independently verified.

### Aster
- URL: https://asterlab.ai/
- Posted by: scarywood75, 7 Aug
- Category: providers
- Brief: OpenAI-compatible inference with free, Pro and Max tiers. States zero data retention on the free tier; Pro around $20 for $30 in tokens.

### Featherless
- URL: https://featherless.ai/
- Posted by: whaaaat, 7 Aug
- Category: providers
- Brief: A serverless inference platform for open-weight models with a catalog of 40,000+ models on a single OpenAI-compatible API — headlined by a flat-rate Chat plan at $25/month with unlimited tokens. Also offers a usage-based Developer tier ($50/month in credits, per-token, with rollover) and custom dedicated-GPU Business plans; the company raised a $20M Series A in December 2025. The flat-rate Chat plan is for interactive human-driven use only — not for automation, reselling, app/API traffic, or benchmarking, and the site says misuse may lead to cancellation without refund.

### Meituan LongCat
- URL: https://longcat.ai/
- Posted by: asx, 3 Aug
- Category: providers
- Brief: Meituan's LongCat with Token Packs — 50M tokens for $4.90 (promotion corroborated). Surfaced via an X post.

### DeepInfra
- URL: https://deepinfra.com/
- Posted by: Alp, 2 Aug
- Category: providers
- Brief: Pay-as-you-go inference across 100+ models with explicit zero data retention. Example: GLM-5.3 Flash $0.075/$0.25 per 1M.

### CheapestInference
- URL: https://cheapestinference.com/
- Posted by: tushii, 31 Jul
- Category: providers
- Brief: Flat-rate unlimited time-block subscriptions — Core pool from $22/mo per 8-hour daily block, Frontier $71/mo, Flagship $199/mo. Prompts and completions are processed in memory and discarded, never used for training.

### PrivacyWatch
- URL: https://privacywatch.wyrdwerk.com/
- Posted by: thelaggingway, 31 Jul
- Category: providers
- Brief: Open-source comparison of 86+ provider families (97 surfaces) on training, retention, zero-retention and data location, quoting each provider's own ToS and privacy docs. Maintained by the same crew as this library.

### OpenAI API pricing
- URL: https://platform.openai.com/docs/pricing
- Posted by: simply soy, 31 Jul
- Category: providers
- Brief: OpenAI's official per-1M-token pricing page (e.g. gpt-6-luna $0.10 in / $0.50 out short-context). Useful as the first-party reference behind third-party price comparisons.

### Zro
- URL: https://zro.moonmath.ai/pricing
- Posted by: Tom, 30 Jul
- Category: providers
- Brief: $20/mo including $60 of inference spend, OpenAI/Anthropic-compatible. Explicit zero request retention — prompts and completions are never used for training, evaluation or analytics.

### InferX
- URL: https://inferx.net/models
- Posted by: thelaggingway, 30 Jul
- Category: providers
- Brief: Pay-as-you-go inference across 200+ production-ready models you can deploy with one click from its console. 'Ready now' endpoints publish per-token input/output/cached-input pricing, with promotional models showing the original rate crossed out beside the active InferX price — the catalog explicitly marks unpublished fields as missing rather than estimating them.

### xKiro
- URL: https://xkiro.com/
- Posted by: thelaggingway, 30 Jul
- Category: providers
- Brief: Unified gateway — free tier with 40+ free models and 5M tokens/day (no card), pay-as-you-go about 35% below official prices on select models. 90+ models across 16 providers on one API key.

### StepFun
- URL: https://platform.stepfun.ai/
- Posted by: thelaggingway, 29 Jul
- Category: providers
- Brief: StepFun's open platform with a usage-billed API (api.stepfun.ai/v1) and a 15-day trial needing no card. Serves Step 5 Preview and StepAudio 3.

### Phoenix Grove
- URL: https://pgsgrove.com/
- Posted by: thelaggingway, 29 Jul
- Category: providers
- Brief: A privacy-first AI company selling a Coding Plan with 'near-endless messaging' for agents and coding tools on one API key, running open models including GLM 5.2, MiniMax M3, and Kimi K2.6, with per-token access from $5 and the first month free. It frames itself around data sovereignty and an 'altruistic AI' charter, and also sells a $3.95/month memory-migration tool (Memory Forge) and an AI workspace subscription. 'Near-endless messaging' is marketing language with no published allowance numbers — actual limits are unverified.

### Neuralwatt
- URL: https://portal.neuralwatt.com/
- Posted by: Blessed Piss Enjoyer, 28 Jul
- Category: providers
- Brief: $10/kWh pay-as-you-go (or per-token), $1 free credit after adding a payment method; monthly plans $20–$200. Hosted multi-model OpenAI-compatible API plus on-prem deployment; 14 models.

### Chutes
- URL: https://chutes.ai/
- Posted by: thelaggingway, 28 Jul
- Category: providers
- Brief: Decentralized, open-source serverless compute platform in the Bittensor ecosystem, aiming to serve new SOTA open-source models 'minutes after release' across text, image, video, speech, and music. Pay-as-you-go billed per token consumed with a live cost estimator, plus TEE/secure compute and a Chutes Chat consumer app. Throughput claims are vendor-reported and not independently verified.

### Telnyx
- URL: https://telnyx.com/pricing/inference-api
- Posted by: thelaggingway, 28 Jul
- Category: providers
- Brief: Inference API with published per-token pricing — Kimi K3 at $2.70/M input, $0.27/M cached input, $13.50/M output. The sharer noted they're open to negotiating volume pricing.

### Charm Hyper
- URL: https://hyper.charm.land/
- Posted by: Alp, 27 Jul
- Category: providers
- Brief: Charm's coding-optimized inference for its Crush agent community: a free tier with 100 Hypercredits per month, a $20/month subscription with 250 Hypercredits refreshing daily, and prepaid bundles ($5–$20) that never expire — one Hypercredit currently maps to 5¢ of token spend. It ships with team governance features (master/sub keys, per-model and per-user usage reports) and advertises zero data retention with GDPR compliance. The zero-data-retention and GDPR claims are vendor-stated and not independently audited or verified.

### TokenWatch
- URL: https://tokenwatch.wyrdwerk.com/
- Posted by: thelaggingway, 27 Jul
- Category: providers
- Brief: Live price comparison across inference providers, maintained by the same crew as this library. The sharer noted a Hyper subscription yields $12.50 of inference a day.

### Zyloo
- URL: https://zyloo.io/subscription
- Posted by: thelaggingway, 27 Jul
- Category: providers
- Brief: Tiered subscriptions selling 'unlimited' access to named models: LITE at $4.22/week and LITE+ at $12.89/month (Gemini 3/2.5 previews, GPT-4.1, GPT-4o), up to ULTIMATE at $899/month (Claude Opus 4.7/4.8, GPT-5.5/5.6, Claude Sonnet 5, GPT-5.6-Sol). Card payments auto-renew via Stripe with a cancel-anytime portal; crypto, WeChat Pay, Alipay and UPI buy a single non-renewing period. The PRO+ ($199/mo) and ULTRA ($599/mo) tiers were sold out at research time, and the site publishes no fair-use or rate-limit policy behind the 'Unlimited' label.

### Moonshot platform docs
- URL: https://platform.kimi.ai/docs
- Posted by: Manar, 27 Jul
- Category: providers
- Brief: Moonshot AI's platform documentation for the Kimi model family. Shared originally via a Kimi-K3 Hugging Face link.

### Verboo Code
- URL: https://verboo.ai/
- Posted by: thelaggingway, 25 Jul
- Category: providers
- Brief: Free trial, then unlimited-token subscriptions from Junior $24/mo to Ultra $269/mo, plus a usage API from $0.12/1M input tokens. Coding agent plus OpenAI-compatible API on Brazilian servers; states it does not train on or review code and calls.

### Makora
- URL: https://www.makora.com/
- Posted by: 0xSaiya, 25 Jul
- Category: providers
- Brief: Inference provider and optimization service — Starter $20/mo and Developer $200/mo (both shown sold out), with private model serving and on-prem options. Starter covers unlimited models under 40B parameters.

## Dropped during curation

- Darkbloom — exact duplicate of an already-published URL.
- HeRD homepage (herdr.dev) — real site, but an agent-CLI runtime, not an inference provider; the published article about HeRD stands.
- Consensus Protocol — no URL ever identified in #providers.
- Nano-GPT — URL never identified in #providers.
- baselam — zero mentions found in #providers.
- Merius — site unreachable and no corroborating search trace.
- Clusy — site dead and no corroborating search trace.
- ModelWatcher — no corroborating evidence found.
- LLMSpeed — no corroborating evidence found.
- Lilac — GPU fleet operator, not a public inference API.
- Grok Bot — agent product, not an inference API.
- Poteto, relay.fast, Router9, Apertis — no reachable or corroborated provider evidence.
- llama.garden — model torrent tracker, not an inference provider.
- Hyper (hyper.io) — tool suite, not model hosting.
- Kimi (kimi.com) — consumer chat product, not a provider listing.
- Hoplite — agent workspace, not a pure inference provider.
- Notion provider infodump — existence and content not independently confirmed.
- Kourier — name collision (Knative ingress / network-inspector SDK); no inference service found.
- CheapCompute — no public evidence of the domain.
- gpuperhour — no public evidence of the domain.
- OpenDesign Go — design-tool subscription plan; the $5/mo claim unverified.
- routera.one — only a third-party registry row, no official site.
- dot chat — AI chat product, not an inference API.
- Cursor — IDE subscription, not an inference provider.
