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

---

## Phase P4 — Rank + Bandit — 2025-06-27

**Shipped:** Async `evaluate_surface` — moment embed → centroid cosine → Thompson sampling → interrupt gate; live `SURFACE` with `generate_cluster_digest` + bookmark URLs; MongoDB notification persistence; `get_cluster_summary` tool; `--context-override` on heartbeat.

**Thesis alignment:** strong — policy core now picks **when** and **which cluster**; silence vs surface is gate-driven, not hardcoded.

**Demo-ready:** yes (CLI) — `kairos heartbeat --delivery return_only` → `SURFACE` with digest markdown in ~10–25s (longer with Google Search grounding).

### Rubric (0–2)

| Dimension | Score | Note |
|-----------|-------|------|
| Thesis fidelity | 2 | Contextual bandit surface path proven |
| Demo provability | 2 | Live SURFACE + digest in terminal |
| Learning loop | 0 | P5 not wired yet at review time |
| Silence as feature | 2 | Real gate reasons; KAIROS_OK when threshold fails |
| Feedback quality | 0 | Still stub |
| Code cost | 2 | Focused modules; no Atlas required for demo |
| Honest gaps | 2 | Context still stub |
| Consumer value | 2 | Digest + why_now + links — interrupt story lands |

**Total: 12/16** — P4 milestone met; thesis demo unlocked.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🟡 gap | `read_context()` hardcoded (cafe, 90min gap) — not calendar/location | Narrate as demo persona; wire Google Calendar in P6 or pre-brief |
| 🟡 gap | `get_relevant_bookmarks` still stub — judge may ask "why not search?" | Thesis answer: search ≠ interrupt policy; defer or cut from agent tools on stage |
| 🟡 gap | Digest latency ~10s+ (LLM); ~25s with `DIGEST_USE_GOOGLE_SEARCH` | Rehearse with `DIGEST_USE_GOOGLE_SEARCH=false` or pre-warm |
| 🟢 nit | In-app numpy cosine vs Atlas `$vectorSearch` | Fine for hackathon scale (~2 clusters) |
| 🟢 nit | P4 changes not yet committed | Commit before rehearsal |

### Code cost audit

- **Keep:** `core/ranking.py`, `core/moment.py`, `core/bandit.py`, `db/bandit.py`, `db/notifications.py`
- **Cut or defer:** Atlas vector index until scale demands it
- **Missing for demo:** feedback loop (P5) for "learning" beat

### FAQ additions

- Q: Can heartbeat surface a cluster? → A: ✅ `kairos heartbeat` → `SURFACE` with cluster digest + delivery hints.
- Q: How is a cluster chosen? → A: Moment embedding × Thompson sample on `bandit_params` × interrupt gate.

**Verdict:** **SHIP**

**Next (max 3):**

1. Wire `record_feedback` → `feedback_events` + online α/β (P5)  
2. Rehearse 60s: heartbeat → SURFACE → show digest  
3. Commit P4 ranking work  

---

## Phase P5 — Feedback Loop — 2025-06-27

**Shipped:** `kairos feedback` CLI; `feedback_events` MongoDB collection; online bandit α/β update on dismiss/click/ignore; snooze excludes cluster from ranking (context-scoped TTL); notifications persisted across CLI invocations.

**Thesis alignment:** strong — implicit feedback now updates policy; snooze vs dismiss semantics distinct.

**Demo-ready:** partial — can show `bandit` object after dismiss (`beta: 1.8` observed); second heartbeat may still `SURFACE` (different cluster or same with lower weight) — **show MongoDB `bandit_params` doc** as learning proof.

### Rubric (0–2)

| Dimension | Score | Note |
|-----------|-------|------|
| Thesis fidelity | 2 | Online learning from dismiss |
| Demo provability | 1 | Bandit update visible in JSON; outcome change not guaranteed live |
| Learning loop | 2 | feedback_events + bandit_params wired |
| Silence as feature | 2 | Dismiss can push below threshold → KAIROS_OK (observed in dev) |
| Feedback quality | 2 | Snooze=no penalty+exclude; dismiss=−0.4→β |
| Code cost | 2 | Small focused modules |
| Honest gaps | 2 | No dashboard for α/β curve yet |
| Consumer value | 2 | Wrong-time dismiss trains quieter policy |

**Total: 15/16** — P5 milestone met; Continual Learning demo-ready with MongoDB proof.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🟡 gap | Dismiss → next heartbeat may still SURFACE same cluster (Thompson variance) | Demo: show `bandit_params` doc + explain β increase; or dismiss twice |
| 🟡 gap | Web inbox feedback buttons still TODO (`web/static/index.html`) | P6: `POST /feedback` or demo via CLI only |
| 🟡 gap | No eval harness / engagement curve yet | P7 or synthetic persona for Self-Improvement Stack |
| 🟢 nit | `get_relevant_bookmarks` still stub | Defer |
| 🟢 nit | P5 uncommitted alongside P4 | Single `feat(core):` commit |

### Code cost audit

- **Keep:** `core/feedback.py`, `core/rewards.py`, `db/feedback.py`
- **Cut or defer:** GEPA until feedback corpus exists
- **Missing for demo:** visible metrics chart (nice-to-have)

### FAQ additions

- Q: Does the bandit learn? → A: ✅ `kairos feedback --action dismissed` → `bandit_params` α/β update + `feedback_events` row.
- Q: Snooze vs dismiss? → A: Snooze = re-queue, no β penalty, cluster excluded for 120min in same context class. Dismiss = wrong cluster, β += 0.4.

**Verdict:** **SHIP**

**Next (max 3):**

1. P6: `kairos serve` + inbox feedback POST  
2. Rehearse dismiss → show MongoDB `bandit_params` → second heartbeat  
3. Run theme auditor; commit P4+P5  

---

## Phase P6 — Surface UX — 2026-06-27

**Shipped:** `kairos serve` (FastAPI + uvicorn); `GET /api/stream` SSE from `event_bus`; `GET /api/notifications`, `GET /api/bandit`; `POST /api/feedback`, `POST /api/heartbeat`; inbox snooze/dismiss wired in `web/static/index.html`.

**Thesis alignment:** strong — the interrupt loop now has a **product face**: surface → dismiss/snooze → bandit update → next tick visible in admin feed. No longer CLI-only.

**Demo-ready:** yes (browser + CLI) — open `http://127.0.0.1:8420`, trigger heartbeat (CLI or `POST /api/heartbeat`), dismiss in UI, flip to admin mode for SSE activity + bandit α/β.

### Rubric (0–2)

| Dimension | Score | Note |
|-----------|-------|------|
| Thesis fidelity | 2 | Feedback UI closes the "when to interrupt" loop |
| Demo provability | 2 | Live serve + SSE + feedback POST proven |
| Learning loop | 2 | Dismiss in UI → `bandit_params` β increase (observed) |
| Silence as feature | 2 | `KAIROS_OK` events stream to admin activity log |
| Feedback quality | 1 | Snooze/dismiss wired; link-click → `engaged` not in UI |
| Code cost | 2 | ~100 lines app + minimal HTML wiring; no Chart.js bloat |
| Honest gaps | 1 | Sidebar context/clusters/sparkline still mock HTML |
| Consumer value | 2 | Inbox card + why_now + links — hoarder feels the difference |

**Total: 14/16** — P6 milestone met; hackathon demo can run in browser.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🟡 gap | User sidebar (`context.gap`, `clusters`, `sparkline`, `gepa`) still **hardcoded mock** — mismatches live API (90min gap vs "42 min") | Wire `/api/notifications` context snapshot or hide mock widgets for demo |
| 🟡 gap | Admin GEPA panel shows fake v3→v4 diff — judge may think RSI is shipped | Narrate "P7" or replace with "not yet" placeholder before stage |
| 🟡 gap | P4+P5+P6 **uncommitted** (18 files since `a739698`) | Single thematic commit before rehearsal |
| 🟡 gap | No FastMCP / MCP inbox path yet | Defer — browser demo sufficient for hackathon |
| 🟢 nit | `close_mongo()` after every GET — works but reconnects each request | Acceptable at demo scale |
| 🟢 nit | `Open all` button not wired | Cut or wire `window.open` on link URLs |

### Code cost audit

- **Keep:** `web/app.py`, `web/server.py`, SSE stream, feedback POST, index.html EventSource wiring
- **Cut or defer:** Chart.js engagement curve; full calendar sidebar; FastMCP until P8
- **Missing for demo:** 30s pitch script; hide or wire mock sidebar widgets

### FAQ additions

- Q: Can I see the web dashboard? → A: ✅ `uv run kairos serve` → inbox + admin SSE; snooze/dismiss POST to `/api/feedback`.
- Q: Does learning show in the UI? → A: Partial — admin mode shows SSE activity + bandit α/β via `/api/bandit`; no engagement chart yet.

**Verdict:** **SHIP**

**Next (max 3):**

1. Rehearse browser path: serve → heartbeat → dismiss → admin SSE + bandit panel  
2. Hide or wire mock sidebar (context/clusters/GEPA) before judge demo  
3. Commit P4+P5+P6 core  

---

## Phase MCP — FastMCP Server — 2026-06-27

**Shipped:** `kairos mcp` CLI (stdio + SSE); `src/kairos/mcp/server.py` FastMCP wrapper over `ALL_TOOLS` (6 tools); `docs/MCP_SETUP.md` + example JSON for Claude Code / Cursor.

**Thesis alignment:** strong — host agents can now drive the policy loop without shelling to CLI. Instructions encode silence-as-feature and `return_only` delivery for chat hosts.

**Demo-ready:** partial — tools list verified (`run_heartbeat`, `record_feedback`, …); live Claude Code `/loop` not rehearsed on stage yet. Pair with Google Workspace Calendar MCP (separate server) for live schedule context.

### Rubric (0–2)

| Dimension | Score | Note |
|-----------|-------|------|
| Thesis fidelity | 2 | MCP exposes interrupt policy, not search |
| Demo provability | 1 | 6 tools registered; end-to-end in Claude Code unproven live |
| Learning loop | 2 | `record_feedback` exposed with full action enum |
| Silence as feature | 2 | Server instructions: KAIROS_OK is valid |
| Feedback quality | 2 | All FeedbackAction values reachable via MCP |
| Code cost | 2 | ~40 lines + CLI; reuses ALL_TOOLS |
| Honest gaps | 2 | Docs mark stub tools; Calendar MCP documented as external |
| Consumer value | 1 | Value realized only when host agent completes loop |

**Total: 14/16** — MCP milestone met; agent-native demo path unlocked.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🟡 gap | **Google Calendar MCP not configured** — `get_current_context` still returns demo stub | Configure `calendarmcp.googleapis.com` in host; agent calls `list_events` before heartbeat |
| 🟡 gap | Stub tools exposed (`get_relevant_bookmarks`, `add_bookmark`) | Hide from MCP or implement before agent demo |
| 🟡 gap | Mock web UI unchanged (sidebar, GEPA panel) | P0 hide/wire before browser demo |
| 🟡 gap | No live Claude Code `/loop` rehearsal recorded | Run once with `delivery=return_only` before stage |
| 🟢 nit | `mcp` added as direct dep (was transitive via antigravity) | Good — explicit for server |
| 🟢 nit | SSE transport on port 8421 for debug | Optional; stdio is primary |

### Code cost audit

- **Keep:** `mcp/server.py`, thin wrapper pattern, MCP_SETUP docs
- **Cut or defer:** HTTP MCP until needed; don't duplicate tools in MCP layer
- **Missing for demo:** Calendar MCP OAuth setup + agent prompt protocol

### FAQ additions

- Q: Is there a Kairos MCP server? → A: ✅ `uv run kairos mcp` — stdio FastMCP over policy tools.
- Q: How does Claude Code run heartbeats? → A: Add kairos to MCP config; `/loop` calls `run_heartbeat(delivery='return_only')`.

**Verdict:** **SHIP**

**Next (max 3):**

1. Google Workspace Calendar MCP setup + agent prompt (list_events → heartbeat)  
2. Hide mock web UI widgets before judge demo  
3. Rehearse Claude Code `/loop` with Kairos MCP  

---

## Phase A.5 — Headspace sensors + multi-user + vector search (Cursor expansion) — 2026-06-27

**Shipped:** Real headspace fusion (`core/headspace.py` from Calendar/Gmail/geo → `topical_affinity` + `attention_capacity`), `context_cache` persistence, Google Workspace OAuth package (`google/*`, `google connect/verify/auth-check`), ADK agent migration (`agent/config.py`+`hooks.py` deleted → `agent/agent.py`), Atlas `$vectorSearch` with in-memory fallback (`db/vector_search.py`), **multi-user bandit** (user_id-scoped `bandit_params`/`feedback_events`/`notifications`), LLM moment-fit gate (`llm/compose.py`), fatigue accounting (`core/fatigue.py`), Cloud Run Dockerfile. Plus the persona **gym** (`sim/*`, `kairos sim run/reset`) and real `/api/metrics`.

**Thesis alignment:** strong — multi-user + gym + richer context all serve "learn when to interrupt." But scope ballooned (12 new modules, 3 new subsystems) well past P6 in one uncommitted batch.

**Demo-ready:** **NO — regression.** A nested-event-loop bug breaks every live heartbeat.

### Findings

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| 🔴 blocker | `read_context()` (`core/context.py:57`) calls `asyncio.run()`; `heartbeat.run()` (async) calls it sync at `heartbeat.py:28` → `RuntimeError: asyncio.run() cannot be called from a running event loop`. **Confirmed empirically.** Breaks `kairos heartbeat`, `POST /api/heartbeat`, agent-cycle. Gym path unaffected (bypasses `read_context`). | One-line fix: `heartbeat.run` should `await get_context_async(user_id)` not `read_context(user_id)`. |
| 🟡 gap | Gym ↔ live bandit are disconnected on two axes: (a) user_id scope (gym=`sim:alex`, live=`__default__`); (b) `context_class` mismatch — gym keys lack the `topical_affinity` suffix (`desk_short_gap` vs live `desk_long_gap_work`). Gym never pre-trains the live bandit. | Gym `sample_context` should call `fuse_headspace`; demo as a sim persona, or document the separation. Act 3 metrics curve is unaffected (reads `feedback_events`). |
| 🟡 gap | `intelligence_moment_fit_check=True` adds a 2nd sequential Gemini call per SURFACE (moment-fit, then digest) → 20–40s latency live. | Disable for demo (`INTELLIGENCE_MOMENT_FIT_CHECK=false`) or run the fit-check concurrently. |
| 🟡 gap | Agent tools (`get_current_context`/`set_context`/`fuse_headspace_context`/`run_heartbeat`) repeat the `asyncio.run` pattern — safe only if ADK invokes tools in worker threads. | Verify ADK threading or convert to async tools. |
| 🟢 nit | `metrics.py` counts engagement via exact float match `derived_reward in [0.4,0.8,1.0]`. | Use `derived_reward > 0`. |

### Code cost audit

- **Keep:** vector_search (real $vectorSearch + fallback), gym, metrics, multi-user bandit, headspace fusion.
- **Cut or defer:** moment-fit LLM gate (latency, not demo-critical); Google Workspace OAuth is a lot of surface for one demo — verify `google verify` actually fires before relying on it.
- **Missing for demo:** the blocker fix; one committed checkpoint (18 modified + 25 untracked files uncommitted).

### FAQ additions

- Q: Is the bandit per-user? → A: ✅ `bandit_params` keyed `user_id × cluster × context_class`; gym personas and live demo are separate namespaces.
- Q: Does heartbeat work right now? → A: ❌ Blocked by a nested-asyncio bug in `read_context`; one-line fix pending.

**Verdict:** **FIX-BEFORE-NEXT** — 🔴 on Demo provability (rubric dim 2). Do not add features until the heartbeat runs.

**Next (max 3):**

1. Fix the `read_context` nested-loop blocker; smoke `kairos heartbeat` end-to-end  
2. Disable moment-fit gate for demo; re-measure surface latency  
3. Commit this batch as thematic checkpoints before more scope  
