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
A: ❌ Not yet. `ranking.py` is a stub — heartbeat always returns `KAIROS_OK` with `score_threshold: false`.

**Q: Does the bandit learn?**  
A: 🚧 Designed (Thompson sampling, `bandit_params` α/β). `record_feedback` and ranking step 3 are stubs.

**Q: Can I see the web dashboard?**  
A: 🚧 EventBus exists; `kairos serve` is a stub.

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

## Demo script anchors

**Q: Minimum viable demo path?**  
A: (1) ✅ Show enriched bookmarks + clusters (`kairos bookmarks clusters`). (2) Heartbeat → gate → surface OR KAIROS_OK. (3) Feedback → bandit update → different outcome. Step 2–3 need P4 wiring.

**Q: Best "learning visible" moment?**  
A: `optimization_runs` prompt diff or bandit α/β shift after dismiss — whichever is wired first.

**Q: What to show if live heartbeat fails?**  
A: Pre-recorded terminal: `bookmarks clusters` + MongoDB cluster doc + one planned `feedback_events` α/β update.

---

## Stale / open

- [x] Update when embeddings land (P3 — 2025-06-27)
- [ ] Update when first live bandit update ships
- [ ] Update when first `SURFACE` heartbeat with real cluster ships
- [ ] Add rehearsal timestamps after first run-through
