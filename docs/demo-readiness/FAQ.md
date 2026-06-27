# Kairos Demo FAQ

Living wiki for judges, rehearsal, and adversarial phase reviews.  
**Update after every phase review** (see `.cursor/skills/kairos-adversarial-judge/`).

Legend: ✅ built · 🚧 stub/partial · ❌ not yet

---

## Elevator pitch

**Q: What is Kairos?**  
A: A contextual bandit that learns **when** to surface bookmark *clusters*, not a search tool. Silence (`KAIROS_OK`) is the default; interrupt only when calendar, location, and learned engagement align.

**Q: One-sentence thesis?**  
A: Everyone embeds bookmarks; nobody optimizes the **interruption policy** against measured attention and lets it rewrite itself.

---

## Why contextual bandits?

**Q: Why contextual bandits — why not just ask an LLM to decide when to surface?**  
A: An LLM deciding in real time has no memory of what it got wrong. Every heartbeat starts cold unless you inject past feedback into the prompt — at which point you're building an ad-hoc bandit with worse statistics. The α/β parameters on each cluster×context pair *are* the accumulated learning. They update in microseconds and explain themselves: `p(engage) = 0.84, sampled from Beta(12.4, 4.1)`. A judge can watch that change after a dismiss. An LLM making the same decision is a black box with no update path.

**Q: Why not fine-tune Gemini on engagement data?**  
A: Sparse feedback regime — tens of interactions per day per user, not thousands. Thompson sampling converges from 20–100 observations. Fine-tuning needs orders of magnitude more labeled pairs and resets on every model update. Bandits are specifically designed for this signal density.

**Q: Why not just cosine similarity + a threshold?**  
A: Cosine answers "which cluster is topically closest." It doesn't answer "given that I surfaced this cluster at 2pm on a dense-meeting day and the user dismissed it, should I surface it at 2pm tomorrow?" The bandit learns that negative signal. Cosine has no memory.

**Q: Why not a memory system like Letta/MemGPT?**  
A: Different problem. Letta optimizes what's *stored* — sleep-time memory consolidation. Kairos optimizes the *retrieval policy* against measured downstream behavioral outcomes. Letta makes memory cleaner; Kairos makes the interruption smarter. We use Gemini where language matters (enrichment, digest) and the bandit where statistics matter (when to interrupt).

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

**Q: Snooze vs dismiss?**  
A: Snooze = right cluster, wrong time — no β penalty; cluster excluded from ranking for 120min in same context class. Dismiss = wrong cluster — β increases, surface weight drops.

**Q: Can I see the web dashboard?**  
A: ✅ `uv run kairos serve` → inbox at `http://127.0.0.1:8420`. Snooze/dismiss POST to `/api/feedback`. Admin mode shows SSE activity feed + bandit α/β. 🚧 Sidebar context/clusters/sparkline still mock data.

**Q: GEPA / nightly self-improvement?**  
A: ❌ Planned second loop; digest prompt optimization not wired.

**Q: Incremental sync / re-embed on change?**  
A: 🚧 Fingerprints + `bookmarks/pipeline.py` exist; `kairos ingest update` and incremental X pagination not wired to CLI yet.

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
A: ✅ `feedback_events` + `bandit_params` + notifications in MongoDB; EventBus → SSE `/api/stream` + admin activity feed. 🚧 Eval harness + GEPA + engagement chart still P7. ⚠️ GEPA panel in HTML is mock — do not claim shipped.

**Q: Is this Recursive Intelligence / weight RSI?**  
A: Honest scope: prompt-level self-improvement via GEPA (P7), not model weight training. Bandit is policy RSI at the application layer.

**Q: Where is theme status tracked?**  
A: `docs/demo-readiness/THEME_LOG.md` — updated each phase via `.cursor/skills/kairos-hackathon-themes/`.

---

## Demo script anchors

**Q: Minimum viable demo path?**  
A: **Browser:** (1) `uv run kairos serve`. (2) `uv run kairos heartbeat` or `POST /api/heartbeat`. (3) Dismiss in inbox. (4) Admin mode → SSE + bandit panel. **CLI fallback:** `bookmarks clusters` → heartbeat → feedback → second heartbeat.

**Q: Best "learning visible" moment?**  
A: Admin mode after dismiss — bandit β ticks up (`GET /api/bandit`) and SSE `feedback` event. CLI: `kairos feedback` JSON. GEPA prompt diff is P7.

**Q: What to show if live heartbeat fails?**  
A: Pre-recorded terminal: `bookmarks clusters` + MongoDB cluster doc + one planned `feedback_events` α/β update.

---

## Stale / open

- [x] Update when embeddings land (P3)
- [x] Update when first SURFACE heartbeat ships (P4)
- [x] Update when first bandit update ships (P5)
- [x] Update when `kairos serve` ships (P6)
- [ ] Add rehearsal timestamps after first run-through
- [ ] Update when GEPA / optimization_runs lands (P7)
- [ ] Wire or hide mock sidebar widgets (context, clusters, GEPA panel)
