# Kairos Demo FAQ

Judge deep-dive (bandit vs RAG, Letta, etc.). Pitch and runbook: [DEMO.md](./DEMO.md).

Legend: ✅ built · 🚧 partial · ❌ not yet

---

## Onboarding (engineers)

**Q: I'm new — how does the dashboard connect to the backend?**  
A: Open **http://127.0.0.1:8420/walkthrough** after `just demo-serve` — animated prep → heartbeat flow with an API map. Full reference: [DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md). Optional Manim video: `manimgl scripts/manim/kairos_flow.py KairosFlow` ([3b1b/manim](https://github.com/3b1b/manim)).

---

## Why contextual bandits?

**Q: Why contextual bandits — why not just ask an LLM to decide when to surface?**  
A: An LLM deciding in real time has no memory of what it got wrong. Every heartbeat starts cold unless you inject past feedback into the prompt — at which point you're building an ad-hoc bandit with worse statistics. The α/β parameters on each cluster×context pair *are* the accumulated learning. They update in microseconds and explain themselves: `p(engage) = 0.84, sampled from Beta(12.4, 4.1)`. A judge can watch that change after a dismiss. An LLM making the same decision is a black box with no update path.

**Q: Why not fine-tune an LLM on engagement data?**  
A: Sparse feedback regime — tens of interactions per day per user, not thousands. Thompson sampling converges from 20–100 observations. Fine-tuning needs orders of magnitude more labeled pairs and resets on every model update. Bandits are specifically designed for this signal density.

**Q: Why not just cosine similarity + a threshold?**  
A: Cosine answers "which cluster is topically closest." It doesn't answer "given that I surfaced this cluster at 2pm on a dense-meeting day and the user dismissed it, should I surface it at 2pm tomorrow?" The bandit learns that negative signal. Cosine has no memory.

**Q: Why not a memory system like Letta/MemGPT?**  
A: Different problem. Letta optimizes what's *stored* — sleep-time memory consolidation. Kairos optimizes the *retrieval policy* against measured downstream behavioral outcomes. Letta makes memory cleaner; Kairos makes the interruption smarter. We use LLMs where language matters (enrichment, digest) and the bandit where statistics matter (when to interrupt).

**One-liner:** "Bandits are the only class of algorithm that converges on sparse, delayed feedback without requiring a dataset we don't have."

---

## vs alternatives

**Q: Why not just search my bookmarks?**  
A: Search answers *what matches a query*. Kairos answers *is this the right moment* — and learns from dismiss, snooze, and clicks. Search doesn't train on ignored notifications.

**Q: Why not a daily digest email?**  
A: That's a cron + similarity. Wrong time → trained ignore. Kairos gates on gap, energy budget, and bandit history.

**Q: Why not ChatGPT + my bookmarks?**  
A: ChatGPT answers when you ask. Kairos decides when to interrupt — and updates that policy from dismiss/snooze/click signals.

---

## What's built today

**Q: Can you ingest X bookmarks?**  
A: ✅ OAuth PKCE, sync to MongoDB, 99 bookmarks ingested in dev.

**Q: Is enrichment working?**  
A: ✅ Gemini flash-lite via Interactions API; `kairos bookmarks enrich` with parallel requests.

**Q: Clustering / embeddings?**  
A: ✅ **99/99 embedded**, **2 clusters** persisted (58 bookmarks assigned, 41 HDBSCAN noise). Default embed: `gemini-embedding-001@768` via API; local `bge-small-en-v1.5` optional (`EMBEDDING_BACKEND=local`).

**Q: Can heartbeat surface a cluster?**  
A: ✅ `kairos heartbeat --delivery return_only` → `SURFACE` with cluster digest, `why_now`, bookmark links, and optional Google Search grounding.

**Q: Does the bandit learn?**  
A: ✅ `kairos feedback --action dismissed` writes `feedback_events` and updates `bandit_params` α/β (e.g. β += 0.4 on dismiss). Thompson sampling reads updated weights on next heartbeat.

**Q: Is the bandit per-user?**  
A: ✅ As of Phase A.5, `bandit_params`/`feedback_events`/`notifications` are keyed `user_id × cluster × context_class`. Gym personas (`sim:alex`…) and the live demo (`__default__`) are **separate namespaces** — the gym does not pre-train the live single-user bandit.

**Q: Can I run the gym to pre-train / show a convergence curve?**  
A: ✅ `kairos sim run --days 14 --personas alex,maya,jordan` runs the real ranking + bandit loop against synthetic lifestyles; `/api/metrics` returns the engagement curve from `feedback_events`. `kairos sim reset` clears it.

**Q: Does the live heartbeat work right now?**  
A: ✅ Fixed (2026-06-27). Two blockers resolved: (1) the nested `asyncio.run` in `read_context` — `heartbeat.run` now `await get_context_async`; (2) a stale unique `cluster_id_1_context_class_1` index that crashed `ensure_bandit_indexes` and broke multi-user — now dropped on startup. Verified end-to-end: SURFACE → dismiss → bandit `β 1.0→1.4`.

**Q: Why might a heartbeat stay KAIROS_OK even with a good cluster match?**  
A: The `intelligence_moment_fit_check` LLM gate (on by default) can veto a surface (`gate failed: moment_fit`). It also adds a 2nd Gemini call per surface (latency). For demos, set `INTELLIGENCE_MOMENT_FIT_CHECK=false`.

**Q: Snooze vs dismiss?**  
A: Snooze = right cluster, wrong time — no β penalty; cluster excluded from ranking for 120min in same context class. Dismiss = wrong cluster — β increases, surface weight drops.

**Q: Can I see the web dashboard?**  
A: ✅ `just demo` → inbox at `http://127.0.0.1:8420`. Snooze/dismiss → `/api/feedback`. Admin: pipeline log, bandit α/β, engagement sparkline, GEPA runs (when present).

**Q: Is there a Kairos MCP server for Claude Code / Cursor?**  
A: ✅ `uv run kairos mcp` — see `docs/MCP_SETUP.md` and [DEMO.md](./DEMO.md) § MCP. Calendar via Kairos `sync_google_headspace`.

**Q: GEPA / nightly self-improvement?**  
A: ✅ Eval harness + `kairos optimize run|readiness|eval` + `POST /api/optimize` + admin panel. Needs ≥ `GEPA_MIN_SAMPLES` feedback events. Nightly automation not wired yet.

**Q: Incremental sync / re-embed on change?**  
A: 🚧 Fingerprints + `kairos bookmarks prep` exist; X sync paginates full corpus unless `max_pages` set; bookmark cursor incremental sync not on CLI yet.

---

## Technical gotchas

**Q: Why one embedding model, not agent-picked?**  
A: Vector search requires one consistent space. Model changes = re-embed migration (stored as `gemini-embedding-001@768` or `BAAI/bge-small-en-v1.5`), not per-request choice.

**Q: Why Gemini embeddings instead of local?**  
A: Speed — full corpus embed in ~7s vs minutes (HF model download + CPU). Same API key as enrichment. Not a demo talking point.

**Q: X OAuth "Something went wrong"?**  
A: Usually callback URL mismatch (`127.0.0.1` vs `localhost`). Run `kairos x auth-check`.

**Q: Do bookmarks need paid X API tier?**  
A: Yes — `bookmark.read` requires Basic+; ingest won't work on free tier.

**Q: Why only 2 clusters on 99 bookmarks?**  
A: HDBSCAN with `min_cluster_size=3`; dense topics merge (51-member "software-engineering · education" cluster). 41 bookmarks labeled noise — may tune params or narrate as long tail.

---

## Hackathon themes

**Q: How is this Continual Learning without fine-tuning the LLM?**  
A: ✅ Online contextual bandit — dismiss/snooze/click update α/β in `bandit_params`; Thompson sampling on next heartbeat. No gradient steps on Gemini.

**Q: What's the Self-Improvement Stack?**  
A: ✅ `feedback_events` + bandit online updates + EventBus → SSE admin feed + engagement sparkline from gym + GEPA eval harness. 🚧 Automated nightly GEPA cron.

**Q: Is this Recursive Intelligence / weight RSI?**  
A: Honest scope: prompt-level self-improvement via GEPA, not model weight training. Bandit is policy RSI at the application layer.

**Q: Where is theme / phase audit history?**  
A: [docs/archive/hackathon/](../archive/hackathon/) — `THEME_LOG.md`, `PHASE_REVIEWS.md`.

---

## Demo script anchors

**Q: Minimum viable demo path?**  
A: `just demo-serve` → dismiss → Admin bandit panel. See `docs/demo-readiness/DEMO.md`.

**Q: Best "learning visible" moment?**  
A: Admin mode after dismiss — bandit β ticks up (`GET /api/bandit`) and SSE `feedback` event. CLI: `kairos feedback`. GEPA prompt diff when `optimization_runs` has rows.

**Q: What to show if live heartbeat fails?**  
A: Pre-recorded terminal: `bookmarks clusters` + MongoDB cluster doc + one planned `feedback_events` α/β update.

---

## What's next (post-hackathon)

**Q: "What comes after the demo?"**  
A: See [TECH_DEBT.md](../TECH_DEBT.md) P3 — typed MCP payloads, multi-user metrics, incremental X sync, GEPA cron, multi-source ingest. Vision notes: [archive/hackathon/VISION.md](../archive/hackathon/VISION.md).

**One-liner:** "The hackathon proves the loop works. At scale, the question is whether a million users' attention data makes day one for user one million as good as session 100 for user one."
