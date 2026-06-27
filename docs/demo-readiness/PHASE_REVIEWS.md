# Phase Reviews — Adversarial Judge Log

Append-only. Each entry from `kairos-adversarial-judge` skill after a development phase.

---

## Phase P1+P2 — Ingest + Enrich — 2026-06-27

**Shipped:** X OAuth (PKCE, refresh), bookmark sync → MongoDB, parallel Gemini enrichment, `kairos bookmarks` CLI.

**Thesis alignment:** partial — strong data plane; **policy plane still stub** (no clusters, bandit, or surface loop).

**Demo-ready:** partial — can show bookmarks + enrichment JSON; **cannot** show interrupt learning yet.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🔴 blocker | No embeddings/clusters → nothing to surface as "topic digest" | P3 before demo story claims "clusters" |
| 🔴 blocker | `evaluate_surface` / bandit / `record_feedback` stubs | P4 is thesis — prioritize over serve polish |
| 🟡 gap | Many CLI subcommands (`x auth-check`, etc.) — judge may ask "where's the product?" | Demo script leads with heartbeat + one adaptation, not CLI tour |
| 🟡 gap | FAQ/wiki didn't exist until now | Run adversarial judge after each phase |
| 🟢 nit | Enrichment was slow → parallelized | Good code-cost tradeoff |

### Code cost audit

- **Keep:** ingest, enrich, MongoDB repo, OAuth — necessary substrate
- **Cut or defer:** agent-chosen embedding models; extra CLI before P4; FastMCP before heartbeat works
- **Missing for demo:** cluster label, one surface decision, one feedback update

### FAQ additions

- See `FAQ.md` — initial seed from this review

**Verdict:** FIX-BEFORE-NEXT (for thesis demo) — data plane SHIP, policy plane blocked

**Next (max 3):**

1. Embeddings + HDBSCAN → named clusters  
2. Wire Thompson sampling + gate in `ranking.py`  
3. `record_feedback` → `feedback_events` + α/β update  

---

## Phase P3 — Embed + Cluster — 2025-06-27

**Shipped:** Gemini embedding backend (99/99 vectors, ~7s full backfill), HDBSCAN clustering → `clusters` collection, fingerprint-based stale detection, `kairos bookmarks embed|cluster|clusters`.

**Thesis alignment:** partial — **data plane for clusters exists**; policy plane still cannot pick or surface one. Heartbeat returns `KAIROS_OK` with `score_threshold: false` every time (`ranking.py` stub).

**Demo-ready:** partial — can show `kairos bookmarks clusters` (2 clusters, 58/99 assigned, 41 noise) in 60s; **cannot** show interrupt decision or digest yet.

### Rubric (0–2)

| Dimension | Score | Note |
|-----------|-------|------|
| Thesis fidelity | 1 | Substrate only — no "when" |
| Demo provability | 1 | CLI clusters yes; heartbeat surface no |
| Learning loop | 0 | No feedback → policy path |
| Silence as feature | 1 | `KAIROS_OK` works; gate reasons hardcoded |
| Feedback quality | 0 | `record_feedback` stub |
| Code cost | 2 | Gemini API swap justified vs HF cold start; dual backend clean |
| Honest gaps | 2 | FAQ updated below |
| Consumer value | 1 | 2 clusters / 41 noise — weak "topic digest" story |

**Total: 8/16** — P3 milestone met; do not claim demo-ready.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🔴 blocker | `evaluate_surface` never reads clusters or embeddings | P4: vector match + bandit + gate → `should_surface=True` path |
| 🔴 blocker | Agent tools still stub clusters/`$vectorSearch` (`agent/tools.py`) | Wire to same repo layer as CLI or defer agent demo |
| 🟡 gap | Only **2 clusters** (51 + 7 members); **41 bookmarks = HDBSCAN noise** | Tune `HDBSCAN_MIN_CLUSTER_SIZE` for demo or narrate noise as "unclustered long tail" |
| 🟡 gap | `bookmarks/pipeline.py` + fingerprints exist; **no `kairos ingest update`**, sync lacks incremental page stop | Wire orchestrator CLI before calling incremental "done" |
| 🟡 gap | Cluster names from tag heuristics, not Gemini digest | OK for P3; use `generate_cluster_digest` at surface time in P4 |
| 🟢 nit | Switched default embed to Gemini API — good latency trade | Keep `EMBEDDING_BACKEND=local` for offline dev; don't pitch model choice on stage |
| 🟢 nit | `sentence-transformers` still in deps though default is API | Acceptable; optional local path |

### Code cost audit

- **Keep:** `embeddings/encoder.py` dispatch, `gemini_encoder.py`, `index.py`, `db/clusters.py`, fingerprints
- **Cut or defer:** incremental pipeline CLI until P4 lands; don't add Batch Embeddings API for ~100 bookmarks
- **Missing for demo:** one live `SURFACE` heartbeat with cluster digest + context `why_now`

### FAQ additions

- Q: What embedding model? → A: Default `gemini-embedding-001@768` via API; local `bge-small-en-v1.5` optional. One vector space, config-driven.
- Q: How many clusters? → A: 2 persisted clusters on 99 bookmarks (58 assigned, 41 HDBSCAN noise as of P3 review).
- Q: Can heartbeat surface a cluster yet? → A: No — ranking step 3 is still a stub.

**Verdict:** **SHIP** (P3 data-plane goal met) · **FIX-BEFORE-NEXT** for hackathon demo (P4 thesis)

**Next (max 3):**

1. Wire `ranking.py`: moment embedding → cluster centroids → Thompson sample → interrupt gate  
2. Prove one `kairos heartbeat` → `SURFACE` with real `cluster_id` + digest  
3. Tune clustering or script the demo around the 51-member "software-engineering · education" cluster  
