# Kairos — Plan

> **Status (2026-06):** P0–P2 simplification landed — see [docs/TECH_DEBT.md](docs/TECH_DEBT.md) for current state and P3 backlog. This doc retains the original product thesis and hackathon build order.

> *kairos* (Greek): the right or opportune moment. The agent that turns a passive bookmark graveyard into execution by learning *when* to surface information, not just *what*.

## What We're Building

A context-aware agent that learns the optimal moment to surface Twitter/X bookmarks based on calendar state, location, time patterns, and headspace signals — with zero friction feedback and a nightly self-improvement pass. Passive hoarding → timely execution.

**Hackathon theme:** Continual Learning (primary) + Self-Improvement Stack (secondary)

**The thesis in one sentence:** Everyone embeds the bookmark; nobody optimizes the interruption policy against measured attention outcomes and lets it rewrite itself.

---

## Core Insight: This Is Not a Search Problem

The median hackathon project embeds bookmarks, does cosine similarity, sends a push notification. That's a cron job with a vector index. It fails because:
- It fires at wrong moments and gets ignored
- It never learns from that ignoring
- Silence is never a feature

Kairos is a **contextual bandit**: at each candidate moment, score bookmark clusters for fit-to-this-moment, decide whether to interrupt at all, and update the policy on sparse implicit feedback. "Learns when depending on headspace" is the exact specification of a bandit policy improving over time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        INGEST LAYER                         │
│  X API GET /2/users/{id}/bookmarks (paginated sync)         │
│  → normalize → LLM enrichment (Gemini flash-lite)           │
│  → MongoDB + embeddings → HDBSCAN clustering                │
│  (fallback: X data export for bootstrap without OAuth)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      CONTEXT SENSOR                         │
│  Google Workspace MCP (list_events) · Location toggle       │
│  Headspace = topical affinity vector + attention capacity   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     RANKING PIPELINE                        │
│  1. Feasibility filter (energy cost, restraint budget)      │
│  2. Topical score ($vectorSearch: moment → cluster)         │
│  3. Bandit adjustment (Thompson sampling, learned weights)  │
│  4. Interrupt gate (threshold check → surface or silence)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              HeartbeatService (policy core)                 │
│  read_context → evaluate_surface → save_notification        │
│  → deliver (adapter fan-out) → HeartbeatResult              │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  WebDeliveryAdapter  OSDeliveryAdapter  HeartbeatResult
  (→ EventBus SSE)   (terminal-notifier) (MCP/Antigravity
                                          host transcript)
        │
        ▼
  EventBus (in-process pub/sub)
  → FastAPI SSE → web dashboard
        │
        └──────────────────────────────────────┐
                                               ▼
                                   ┌─────────────────────┐
                                   │  SELF-IMPROVEMENT   │
                                   │  BANDIT (online)    │
                                   │  GEPA PASS (nightly)│
                                   └─────────────────────┘
```

---

## Runtime Paths

There are two ways to invoke a heartbeat cycle. Both go through the same `HeartbeatService` policy core.

**Direct path** (`kairos heartbeat`): calls `heartbeat_service.run()` directly. Fastest — used by dashboard, demo, and Kairos MCP `run_heartbeat`.

**ADK agent path** (`kairos agent-cycle` or `heartbeat --via-agent`): Google ADK agent fetches Calendar/Gmail via Workspace MCP, fuses headspace, then calls `run_heartbeat`. Slower; use when MCP sensor payloads must be fetched by the agent loop.

```
CLI / Claude Code /loop / FastMCP
         │
         ├── direct: heartbeat_service.run()
         │
         └── agent: Antigravity Agent → Gemini → tool calls → heartbeat_service
                          │
                          └── hooks: post_tool_call, post_turn → EventBus
```

---

## Notification Format: Cluster Digest, Not Single Bookmark

The unit surfaced is a **topic cluster digest**, not an individual bookmark:

```
┌──────────────────────────────────────────────────┐
│  Distributed Systems (8 bookmarks)               │
│                                                  │
│  You're heading into an infra architecture       │
│  meeting in 40 min. These might be useful:       │
│                                                  │
│  · [CAP theorem + modern tradeoffs] — dense read │
│  · [Kafka vs Redpanda thread] — 3 min skim       │
│  · [Jepsen test results for Postgres] — reference│
│                                                  │
│  [Open all]  [Snooze 2h]  [Not relevant]         │
└──────────────────────────────────────────────────┘
```

Links within a digest are ranked by relevance to current context. Snooze applies to the whole cluster for this context window and re-queues it with the context snapshot stamped on it.

---

## Headspace: Two Dimensions

**Topical affinity** — what are you mentally oriented toward?
- Upcoming calendar event titles (embedded as intent signal) — via Google Workspace MCP `list_events`
- Recent event titles (topic trail from what just ended)
- Location type: desk → work mode, cafe → exploratory, gym → nothing technical
- Post-meeting window: 15–30 min after a multi-person event, topics are primed

**Attention capacity** — how much cognitive bandwidth is available?
- Calendar gap size (minutes until next event)
- Meeting density today (% of day in meetings)
- Minutes since last meeting (recovery window)
- Surfaces already consumed today (fatigue proxy)

Topical affinity → which cluster to surface. Attention capacity → whether any cluster is feasible.

---

## Data Models

All models in `src/kairos/models/schemas.py`. MongoDB collections:

### `bookmarks`

```python
{
  "_id": ObjectId(),
  "x_tweet_id": str,                  # unique upsert key from X API
  "url": str,
  "raw_text": str,
  "author_id": str,
  "author_username": str,
  "tweet_created_at": datetime,
  "context_annotations": list[dict],  # X-inferred entities — seed for topic_tags
  "referenced_tweets": list[dict],    # quoted/replied-to context
  "embedding": list[float],           # 384-dim, sentence-transformers all-MiniLM-L6-v2
  "cluster_id": ObjectId,
  "topic_tags": list[str],            # from BookmarkEnrichment (Gemini flash-lite)
  "consumption_mode": str,            # read-deep | skim | watch | act-in-world | save-to-project
  "energy_cost": float,               # 0.0–1.0
  "geo_anchor": str | None,
  "geo_coords": [float, float] | None,
  "perishability": str,               # evergreen | dated | time-sensitive
  "ingested_at": datetime,
  "last_synced_at": datetime,
  "last_surfaced_at": datetime | None,
  "surface_count": int,
}
```

### `clusters`

```python
{
  "_id": ObjectId(),
  "name": str,                        # LLM-generated label
  "summary": str,                     # 2-sentence summary, GEPA-tuned
  "centroid_embedding": list[float],
  "member_count": int,
  "last_updated": datetime,
}
```

### `notifications`

```python
{
  "_id": ObjectId(),
  "notification_id": str,             # uuid, matches NotificationRecord
  "cluster_id": ObjectId,
  "digest": dict,                     # ClusterDigest payload
  "context_snapshot": dict,
  "status": str,                      # pending | snoozed | dismissed | acted | expired
  "created_at": datetime,
  "expires_at": datetime | None,
}
```

### `feedback_events`

```python
{
  "_id": ObjectId(),
  "notification_id": str,
  "cluster_id": ObjectId,
  "context_snapshot": dict,
  "notification_text": str,           # exact rendered markdown (GEPA eval input)
  "events": [                         # raw interaction sequence
    { "type": "shown",      "t": 0 },
    { "type": "expanded",   "t": 4 },
    { "type": "link_click", "t": 9,  "url": str },
    { "type": "dismissed",  "t": 61 },
  ],
  "derived_reward": float,
  "snooze_context": dict | None,
  "created_at": datetime,
}
```

### `bandit_params`

```python
{
  "cluster_class": str,
  "context_class": str,
  "alpha": float,                     # Thompson sampling beta distribution
  "beta": float,
  "last_updated": datetime,
}
```

### `optimization_runs`

```python
{
  "run_at": datetime,
  "prompt_before": str,
  "prompt_after": str,
  "engagement_before": float,
  "engagement_after": float,
  "diff_summary": str,                # "what I learned" — closing demo slide
}
```

---

## Ranking Pipeline (`core/ranking.py`)

### Step 1 — Feasibility Filter

MongoDB pre-filter before vector search:
```python
{ "energy_cost": { "$lte": available_capacity },
  "cluster_id": { "$nin": snoozed_cluster_ids } }
```

### Step 2 — Topical Score (Atlas `$vectorSearch`)

```python
pipeline = [
  { "$vectorSearch": {
      "index": "bookmark_embedding_index",
      "path": "embedding",
      "queryVector": moment_vector,     # embedded headspace context
      "numCandidates": 50,
      "limit": 10,
  }},
  { "$match": { "energy_cost": { "$lte": available_capacity } } },
  { "$addFields": { "vector_score": { "$meta": "vectorSearchScore" } } },
  { "$sort": { "vector_score": -1 } }
]
```

### Step 3 — Bandit Adjustment

Thompson sample from `bandit_params` per cluster × context class. `adjusted_score = vector_score × bandit_weight`. Learned history reshapes pure similarity over time.

### Step 4 — Interrupt Gate

```
surfaces_today < daily_budget          ✓/✗
calendar_gap_minutes > energy_cost     ✓/✗
time_since_last_surface > min_gap      ✓/✗
adjusted_score > learned_threshold     ✓/✗

All pass → SurfaceDecision(should_surface=True)
Any fail → SurfaceDecision(should_surface=False)  ← silence is the feature
```

Gate reasons are included in `SurfaceDecision.gate_reasons` and emitted to the EventBus for the dashboard.

---

## Reward Function

| Action | Reward | Notes |
|--------|--------|-------|
| `acted` | +1.0 | Passive → execution achieved |
| `link_click` ×2+ | +0.8 | Strong engagement |
| `link_click` + dwell >30s | +0.6 | Solid engagement |
| `expanded` | +0.4 | Interest signal |
| `expanded` only, no click | +0.2 | Weak positive |
| `snoozed` | 0.0 (re-queue) | Right thing, wrong time — re-queue with context stamp |
| `dismissed` | −0.4 | Wrong cluster |
| `ignored` (expired) | −0.6 | Trained user to ignore |

Dwell alone is not a positive label — requires `expanded` or `link_click`. Guards against Goodhart: the agent cannot win by writing longer summaries.

---

## Two Self-Improvement Loops

```
feedback_event.derived_reward
        │
        ├──► BANDIT UPDATE (online, after every feedback event)   ✅ SHIPPED
        │    Updates: bandit_params alpha/beta for user × cluster × context
        │    Also updates bandit_treatments for digest_style (GAMBITTS-lite)
        │    Wired: core/feedback.py → db/bandit.apply_*_reward()
        │
        └──► GEPA OPTIMIZATION (offline, manual or nightly)        ✅ SHIPPED
             Trigger: kairos optimize run | kairos optimize nightly | POST /api/optimize
             Input: rendered notification_text + derived_reward
             Updates: digest generation prompt in llm/generation.py
             Artifact: optimization_runs doc → admin GEPA diff panel
```

The two loops optimize different things: the **bandit** learns *when* to surface (timing policy, online); **GEPA** learns *how* the digest is phrased (language, offline). Neither touches model weights — honest scope is policy RSI + prompt RSI at the application layer.

**The gym is the shared evaluation infrastructure.** `sim/` runs the *real* `evaluate_surface(generate_digest=False)` path against synthetic personas and writes sim-tagged `feedback_events`, so the bandit genuinely converges and the dashboard curve is real — not injected. GEPA consumes the same feedback table plus fixed digest fixtures; it does not yet use a full per-decision LLM trace join.

---

## Observability: Two Telemetry Planes

| Plane | Signal | Standardizable? | Where it lives |
|-------|--------|-----------------|----------------|
| **Policy** | `should_surface`, `gate_reasons`, `adjusted_score`, bandit `α/β`, `context_class`, `derived_reward` | No OTEL vocab exists | `feedback_events`, `bandit_params`, `bandit_treatments`, EventBus |
| **LLM / agent** | enrichment, digest gen, harness tool calls — prompt labels, inputs/outputs when `GEMINI_LOG_IO` is enabled | Yes (OpenInference / OTEL GenAI) | `pipeline_events`, optional Gemini I/O log |

Current build uses **EventBus + persisted `pipeline_events`** for the demo trace, and `feedback_events.notification_text` as the GEPA training artifact. A future `decision_id` / OpenInference trace plane remains useful if we want per-token cost, prompt versioning, and exact prompt→output→reward joins, but it is no longer required for the hackathon demo.

---

## Persona Gym (`sim/`)

Simulated software-engineer lifestyles drive the real policy loop — Act 3 of the demo and the convergence data the dashboard shows.

| Module | Role |
|--------|------|
| `sim/persona.py` | `Persona(name, calendar_pattern, engagement_style, topic_weights, active_hours)`. Cast: **Alex** (SWE, regular cal, snoozes in meetings), **Maya** (ML eng, sparse, morning-engaged), **Jordan** (founder, dense, mostly dismissive) |
| `sim/context_sampler.py` | `sample_context(persona, day, tick)` → valid `ContextSnapshot` (varies gap, location, meeting density per pattern) |
| `sim/feedback_model.py` | `simulate_feedback(persona, cluster, context)` → `FeedbackAction` (topic fit × attention capacity × style noise) |
| `sim/gym.py` | `run_gym(personas, days, ticks)` → calls real `evaluate_surface(generate_digest=False)` and applies bandit reward; records engagement/day. Events tagged `run_id` for `sim reset` |

CLI: `kairos sim run --days 14 --personas alex,maya,jordan` · `kairos sim reset`. The gym calls `evaluate_surface(..., generate_digest=False)` so it skips the ~10–25s Gemini digest call across thousands of ticks (personas react to cluster topic + context, not prose). Gym writes sim-tagged events to live collections, so `/api/metrics` shows real convergence; `sim reset` clears sim docs for a clean live Act 2.

**Demo arc:** Act 1 graveyard (corpus) → Act 2 live single-user feedback (dismiss → β update) → Act 3 gym. Full runbook: `docs/demo-readiness/DEMO.md`.

---

## Current Demo Build State

| Theme proof | Status | Artifact |
|-------------|--------|----------|
| Continual learning | ✅ Proven | `feedback_events` → `bandit_params`; dismiss increments β live |
| Treatment learning | ✅ Partial/proven | `bandit_treatments` keyed by digest style |
| Self-improvement stack | ✅ Proven | EventBus/SSE, persisted `pipeline_events`, `/api/metrics`, sim gym |
| Prompt self-improvement | ✅ Partial/proven | `kairos optimize run`, `kairos optimize nightly`, `/api/optimize`, `optimization_runs` |
| Exact LLM trace join | 🚧 Future | `decision_id` / OpenInference-style trace plane |

The active runbook is [docs/demo-readiness/DEMO.md](docs/demo-readiness/DEMO.md). Historical phase reviews live under [docs/archive/hackathon/](docs/archive/hackathon/).

---

## Research-Driven Roadmap (R1–R4)

Force-multiplier upgrades distilled from two independent research passes (this repo's reasoning + the Exa-sourced survey in `docs/archive/research/CURSOR.md`). Ordered for **force-multiplier × demonstrability × theme coverage**, not pure engineering quality. Where the two passes converged, confidence is high; the ordering below deliberately re-weights toward *demonstrable capability* over invisible internal quality.

| # | Upgrade | Research basis | What it fixes | Primary files | Effort |
|---|---------|----------------|---------------|---------------|--------|
| **R1** | GAMBITTS-lite — action vs. treatment | Generator-Mediated Bandits (2025); Action-Centered TS (Greenewald–Murphy, NeurIPS 2017) | Bandit only learns from `cluster_id`; the LLM **digest** (the actual treatment) is unlearned | `db/bandit.py`, `core/feedback.py`, `core/ranking.py` | Med |
| **R2** | Linear Thompson Sampling | LinUCB (Li 2010 — news timing); Linear TS (Agrawal–Goyal 2013) | Discrete `context_class` buckets fragment sparse feedback; similar moments share zero signal | `core/bandit.py`, `db/bandit.py`, `core/moment.py`, `core/ranking.py` | Med |
| **R3** | Sleep-time-lite | Sleep-time Compute (Lin 2025); Letta dual-agent | Live SURFACE path is 20–40s (moment-fit + grounding + digest) | `core/sleep_cache.py`, `core/context.py`, `core/ranking.py` | Low–Med |
| **R4** | GEPA + `llm_traces` | GEPA (Agrawal 2026); Letta Context Repositories | Recursive Intelligence theme = NONE; admin GEPA panel still mock | `core/optimize.py`, `db/llm_traces.py`, `db/optimization_runs.py`, `POST /api/optimize` | Med–High |

### R1 — GAMBITTS-lite (the standout — both passes converged here)

The thesis split made learnable: an interrupt is **action** (which cluster) × **treatment** (the digest the user actually saw). Today the bandit updates only on `cluster_id`, so a good cluster with a weak digest and a good cluster with a strong digest are indistinguishable.

- Embed the generated digest (or bucket by a `digest_style` tag from `generate_cluster_digest`) and extend the bandit key from `(user × cluster × context_class)` to `(… × treatment_bucket)`, or maintain a small treatment-effect term added to the cluster posterior.
- Update the posterior on `feedback_events` using both the cluster *and* the observed digest treatment.
- **Why it's #1:** most thesis-pure (separates *when/what to interrupt* from *how it reads*), and it is the bridge between the bandit loop and the GEPA loop — R4's prompt rewrites become *measurable* as a treatment effect here.

### R2 — Linear Thompson Sampling (the bandit-quality upgrade both surveys under-weighted)

Replace per-bucket `Beta(α,β)` with a reward model **linear in a continuous context feature vector** `x` (gap, density, post-meeting, `topical_affinity`, hour), optionally crossed with the cluster embedding. Maintain a Gaussian posterior over weights; Thompson-sample from it. A click in `desk_long_gap_work` now informs `cafe_long_gap_work` because features overlap — the right-sized fix for sparse feedback (linear, **not** neural; defer NeuralUCB/VITS until thousands of events).

- Ship feature-flagged alongside the Beta bandit so the **gym can A/B the two** (`sim/gym.py` already replays the real policy).
- Retire `context_class` discretization (`core/moment.py`) as the bandit key once linear is validated; keep it for snooze TTL lookup.

### R3 — Sleep-time-lite (the cheap latency win)

Pre-materialize the expensive intelligence while idle so heartbeats stay fast. **Cheap version only** — not the full dual-agent system:

- `core/sleep_cache.py::build_surface_cache(user_id, context)` → top clusters + digest drafts + moment-fit hints, fingerprinted + `expires_at`.
- Trigger on headspace sync / `POST /api/context/fuse` / cron — **not** every heartbeat. Invalidate on calendar change, fatigue/snooze delta, or fingerprint mismatch.
- Pair with defaulting `INTELLIGENCE_MOMENT_FIT_CHECK=false` for the demo (removes the 2nd sequential Gemini call). `moment_narrative`+TTL is already a partial implementation to build on.

### R4 — GEPA + `llm_traces` (the only Recursive-Intelligence coverage)

The offline prompt-RSI loop (see [Two Self-Improvement Loops](#two-self-improvement-loops)). `core/optimize.py` runs a reflective pass over the `generate_cluster_digest` prompt, scored on `feedback_events` (gym-generated), emitting a real `v1→v2` diff with measured engagement delta into `optimization_runs` → un-hides the admin GEPA panel. The `decision_id`-keyed `llm_traces` plane supplies the `(prompt → output → reward)` tuples; with R1 in place, GEPA's rewrites register as a measurable treatment effect. Hand-rolled reflect loop (Gemini) keeps it zero-dep; DSPy's `GEPA` is the alternative.

**Build order R1 → R2 → R3 → R4.** R1 is the highest force-multiplier and is the substrate R4 measures against; R2 is independent and gym-A/B-able; R3 de-risks demo latency; R4 closes the second loop and the last theme gap. Deferred (post-traction): delayed-feedback bandit updates (Bootstrap TS, UAI 2024), latent-receptivity POMDP / restless-bandit LTV, TIM intra-day scheduling, recharging bandits for habituation, doubly-robust off-policy evaluation. Full survey + citations: `docs/archive/research/CURSOR.md`.

---

## Delivery Layer (`delivery/`)

`HeartbeatService` calls `deliver(result, notification, mode)` which fans out to configured adapters.

| Adapter | What it does | Config |
|---------|-------------|--------|
| `WebDeliveryAdapter` | Emits `notification` event to `EventBus` → SSE → dashboard inbox | `delivery_targets=web` |
| `OSDeliveryAdapter` | `terminal-notifier` (macOS) or `notify-send` (Linux), best-effort | `os_delivery_enabled=true` |
| `return_only` mode | No side effects — HeartbeatResult only (FastMCP callers) | `delivery=return_only` |

`DeliveryHints` on the result tells MCP/Antigravity host agents:
- `rendered_markdown`: pre-rendered digest for host transcript
- `dashboard_url`: deep link to `GET /n/{notification_id}`
- `suggested_host_actions`: e.g. "show rendered_markdown to user", "call record_feedback"
- `suppress_ok_in_chat`: KAIROS_OK is silent — no chat spam when gate stays closed

---

## Interfaces

### Web Dashboard (FastAPI + SSE)

Single page, two panes. `EventBus` is already wired — FastAPI SSE endpoint streams it to the browser.

```
┌─────────────────────────┬──────────────────────────────────┐
│   UPCOMING / HISTORY    │   AGENT ACTIVITY (live via SSE)  │
│                         │                                  │
│  ● 2:30pm               │  14:22 scored 8 clusters         │
│    Distributed Systems  │  14:22 infra-arch → 0.84 ✓       │
│    [before your mtg]    │  14:22 gate: gap=42m ✓ budget ✓  │
│                         │  14:22 → surfaced digest         │
│  ✓ 11am — engaged       │                                  │
│  ✗ 9am — dismissed      │  LAST SLEEP-TIME PASS            │
│                         │  prompt diff (summary v3→v4):    │
│  Engagement rate        │  - "Here are relevant threads"   │
│  ████████░░ 74% (+12%)  │  + "Before {event}, these {n}…"  │
│                         │  engagement: 61% → 74% ✓         │
│  [Manage clusters]      │                                  │
│  [Restraint budget: 3]  │                                  │
└─────────────────────────┴──────────────────────────────────┘
```

**Admin trace inspector (`TRACE · LEARNING` tabs).** The activity feed is the spine; clicking any event opens that `decision_id`'s full trace in the right pane as a **vertical descent rail** — policy nodes and the LLM-call node interleaved in execution order on one line, which is the visual form of the two-plane join. One amber node (the `◆ generate` LLM call) among dim policy nodes; per-node latency makes the agent's cost legible at a glance (`2,310ms` LLM vs sub-20ms policy). `KAIROS_OK` decisions trace to the failing gate node (why it stayed silent is first-class). The `◇ outcome` node is hollow until feedback lands, then fills in and back-propagates the `β` delta — the learning loop is something you watch on the rail.

```
│ ● context   desk·gap42m·dens0.3      2ms
│ ● match     →distributed-sys 0.84   18ms
│ ● sample    Beta(12.4,4.1)→0.75      0ms
│ ● gate      4/4 PASS                 1ms
│ ◆ generate  flash·prompt v2     2,310ms   ← amber; ⌄ prompt/output
│ ● deliver   web · notif 7f3a         4ms
│ ◇ outcome   dismissed −0.4     +6m later
│            bandit β 4.1 → 4.5
```

`TRACE` = inspect one decision (above). `LEARNING` = aggregate self-improvement (GEPA diff + engagement curve + bandit posteriors). The rail renders live only with the Phase A.5 `llm_traces` data — built together so it's real, not a mock. Layout/data contract: `docs/demo-readiness/` design notes.

`kairos serve` ✅ ships the FastAPI app (`web/app.py`): SSE, inbox, `/api/feedback`, `/api/bandit`. Remaining: `/api/metrics`, `/api/trace/{decision_id}`, `/api/optimize`.

### MCP Server (FastMCP)

Tools in `agent/tools.py` are already written as plain Python functions — dual-use for Antigravity harness and FastMCP. The MCP server is a thin wrapper exposing `ALL_TOOLS`.

```python
# tools already exist:
get_current_context()
get_relevant_bookmarks(query, limit)
get_cluster_summary(topic)
run_heartbeat(delivery, context_override)
record_feedback(notification_id, action, url)
add_bookmark(url, notes)
```

Claude Code `/loop` calls `run_heartbeat` via MCP every 5 min during the demo. The session transcript IS the observability.

### Google Workspace MCP — Calendar Context (replaces manual Calendar API)

The Google Workspace MCP server provides `list_events`, `get_event`, `suggest_time` and 5 more calendar tools over OAuth2. This replaces implementing `google-api-python-client` + credential flow manually in `context.py`.

Wire into the Antigravity agent config as an MCP connector, then the agent calls `list_events` as a tool directly. The context sensor becomes: call `list_events` for today → parse gap, density, upcoming title → build `ContextSnapshot`.

Auth: Google Cloud project → OAuth2 client ID + secret → authorized redirect URI. One-time setup, much lighter than implementing the Calendar API from scratch.

---

## Scheduling

Custom scheduler eliminated. Three Claude Code mechanisms replace it:

| Job | Mechanism | Interval |
|-----|-----------|----------|
| Context poll + heartbeat (demo) | Claude Code `/loop 5m` → MCP `run_heartbeat` | 5 min |
| Context poll + heartbeat (prod) | Desktop Scheduled Task → `kairos heartbeat` | 5 min |
| Nightly GEPA sleep-time pass | Cloud Routine → `POST /optimize` | Daily 2am |

---

## Stack

| Component | Tool | Status |
|-----------|------|--------|
| Persistence | MongoDB Atlas | config wired, collections TODO |
| Vector search | Atlas `$vectorSearch` | TODO |
| Embeddings | `sentence-transformers` all-MiniLM-L6-v2 | TODO |
| Clustering | HDBSCAN | TODO |
| Bandit | Thompson sampling (scikit-learn, ~50 lines) | TODO |
| Prompt optimization | DSPy + GEPA | TODO |
| LLM — enrichment | Gemini flash-lite via `google-genai` Interactions API | done (stub input) |
| LLM — digest generation | Gemini flash via `google-genai` Interactions API | done (stub input) |
| Agent harness | Antigravity SDK (`google-antigravity`) | done |
| Observability | EventBus in-process pub/sub → SSE | done |
| Delivery — web | WebDeliveryAdapter → EventBus | done |
| Delivery — OS | OSDeliveryAdapter (terminal-notifier / notify-send) | done |
| Calendar | Google Workspace MCP (`list_events`) | TODO |
| Geo | `geopy` for geocoding, manual toggle for demo | TODO |
| Ingest | X API `GET /2/users/{id}/bookmarks` | TODO |
| API backend | FastAPI + SSE (`kairos serve`) | stub |
| MCP server | FastMCP wrapping `ALL_TOOLS` | TODO |
| Scheduling | Claude Code `/loop` + Desktop Task + Cloud Routine | TODO |

---

## X Bookmark Access — De-risk in Hour 1

X API bookmark endpoint: OAuth2 user-context, rate-limited, pricing volatile. Strategy:
- Primary: live sync via `GET /2/users/{id}/bookmarks` with expansions (author, referenced tweets)
- Bootstrap / fallback: X data export (Settings → Download an archive)
- Demo: export is sufficient if API setup burns time

**Verify API access before architecting around it.**

---

## Demo Strategy — No Real Feedback in 48h

1. Seed **synthetic persona** with scripted preferences
2. Simulate 2 weeks of `feedback_events` to populate MongoDB
3. Show engagement-rate curve climbing (MongoDB aggregation → Chart.js)
4. **One live adaptation on stage**: wrong-context surface → dismiss → bandit update → better surface

Be explicit: real learning takes weeks; the simulator compresses it to 3 minutes.

---

## What's Done vs. TODO

### Done
- `models/schemas.py` — all Pydantic models (ContextSnapshot, ClusterDigest, HeartbeatResult, etc.)
- `observability/bus.py` — EventBus: async pub/sub, history, SSE stream
- `core/heartbeat.py` — HeartbeatService orchestration, record_feedback stub
- `core/ranking.py` — SurfaceDecision structure, gate logic stub
- `core/context.py` — ContextSnapshot builder stub
- `core/notifications.py` — in-memory notification store (MongoDB TODO)
- `delivery/base.py` — DeliveryAdapter protocol
- `delivery/registry.py` — adapter registry, resolve_adapters
- `delivery/web.py` — WebDeliveryAdapter → EventBus
- `delivery/os.py` — OSDeliveryAdapter (terminal-notifier + notify-send)
- `delivery/render.py` — digest_to_markdown, build_delivery_hints, ok_reason
- `llm/client.py` — shared genai.Client singleton
- `llm/generation.py` — enrich_bookmark + generate_cluster_digest (Interactions API, structured output)
- `agent/prompts.py` — SYSTEM_INSTRUCTIONS, DECISION_TURN_PROMPT
- `agent/hooks.py` — post_tool_call + post_turn → EventBus
- `agent/config.py` — LocalAgentConfig factory (tools, hooks, response_schema=HeartbeatResult)
- `agent/tools.py` — ALL_TOOLS: 6 dual-use functions (Antigravity + FastMCP)
- `agent/harness.py` — run_decision_cycle (direct) + run_decision_cycle_via_agent (Antigravity)
- `cli.py` — heartbeat / cycle / agent-cycle / chat / serve commands
- `config.py` — pydantic-settings: Gemini, MongoDB, delivery, budget, intervals

### TODO (build order)
1. **MongoDB wiring** — motor async client, upsert to all collections, swap in-memory store
2. **X API ingest** — `GET /2/users/{id}/bookmarks`, normalize, call `enrich_bookmark`, upsert
3. **Embeddings + clustering** — sentence-transformers on ingest, HDBSCAN nightly, update clusters collection
4. **Atlas `$vectorSearch`** — wire ranking.py steps 1–2
5. **Thompson sampling bandit** — wire ranking.py step 3, bandit_params online update in record_feedback
6. **Google Workspace MCP** — calendar connector in agent config, parse into ContextSnapshot in context.py
7. **FastAPI web server** — `kairos serve`: SSE endpoint streaming EventBus, notification inbox, metrics
8. **FastMCP server** — thin wrapper over ALL_TOOLS, wire into Claude Code MCP
9. **GEPA optimization loop** — POST /optimize endpoint, DSPy + GEPA over feedback_events eval set
10. **Synthetic persona + simulator** — seed feedback_events for demo curve
11. **Claude Code `/loop` wiring** — MCP connected, loop prompt tested

---

## Build Order (Hackathon Sequencing)

### Hour 0–2: MongoDB + Ingest
- [ ] Motor async client, connection from `MONGODB_URI`
- [ ] Swap `core/notifications.py` in-memory store → MongoDB upsert
- [ ] X API ingest: paginated `GET /2/users/{id}/bookmarks`, normalize to bookmark schema
- [ ] Call `enrich_bookmark` per bookmark, upsert to `bookmarks` collection
- [ ] **Eval harness**: fixed context×cluster pairs with synthetic ground truth

### Hour 2–5: Embeddings + Ranking
- [ ] sentence-transformers embed at ingest, store on bookmark doc
- [ ] HDBSCAN cluster, upsert `clusters` collection + centroid embeddings
- [ ] Atlas `$vectorSearch` index on `bookmarks.embedding`
- [ ] Wire ranking.py steps 1–2 (feasibility filter + vector search)
- [ ] Thompson sampling bandit in ranking.py step 3, gate step 4

### Hour 5–8: Calendar + Context
- [ ] Google Workspace MCP connector in `agent/config.py`
- [ ] `context.py`: call `list_events` tool → parse gap, density, upcoming title → ContextSnapshot
- [ ] Location toggle (manual enum, geofence stretch)
- [ ] Wire `record_feedback` → write `feedback_events` + bandit online update

### Hour 8–12: Delivery + FastAPI
- [ ] FastAPI app: `GET /events` SSE from EventBus, `GET /notifications`, `POST /feedback`
- [ ] `GET /n/{notification_id}` — notification deep-link for DeliveryHints dashboard_url
- [ ] Two-pane dashboard HTML (SSE stream → activity log, notification history)
- [ ] Chart.js engagement rate chart from MongoDB aggregation

### Hour 12–18: MCP + GEPA
- [ ] FastMCP server wrapping ALL_TOOLS, add to Claude Code MCP config
- [ ] Claude Code `/loop 5m` prompt wired to MCP `run_heartbeat`
- [ ] `POST /optimize` endpoint: DSPy + GEPA over feedback_events eval set
- [ ] Cloud Routine calling `/optimize` nightly
- [ ] `optimization_runs` write + diff view in dashboard

### Hour 18–24: Demo Prep
- [ ] Synthetic persona + feedback simulator (2 weeks of events)
- [ ] MongoDB aggregation for engagement chart
- [ ] Demo script + stage choreography
- [ ] "What I learned" diff as closing slide

### Hour 24–36: Polish
- [ ] Restraint budget learning from feedback history
- [ ] Calendar pull mode (event title → cluster dossier, bypasses gate)
- [ ] Geo-anchor extraction at ingest + geofence trigger

### Hour 36–48: Stretch
- [ ] Live X API sync (paginated polling)
- [ ] Real geofence (GPS toggle)
- [ ] Additional sources (Pocket, Readwise export)

---

## Three Things Before Anyone Else Starts

1. **Eval harness before the bandit.** No yardstick = no demo. Build the fixed test set from the synthetic persona in hour 1.
2. **Snooze capture before hour 3.** Right-thing-wrong-time is the most informative timing label. Every other team will miss it.
3. **Make learning visible.** The optimization_runs prompt diff — rendered in the dashboard — is worth more on stage than any accuracy number. Show the machine editing itself.

---

## Pitch Frame

> Most second brains are write-only graveyards. You bookmark 500 things and read 12. Kairos doesn't make you a better searcher — it becomes a better interrupter. It learns that you never read long ML threads on back-to-back days but devour them Sunday morning at a coffee shop. It learns that "not now" on a ramen rec means "remind me when I'm near Chinatown with an hour free." Every night it rewrites the prompt it uses to describe your bookmarks, based on what you actually engaged with. The policy improves without you lifting a finger. Passive hoarding becomes execution.

---

## References

- GEPA (Agrawal et al., ICLR 2026 oral): https://arxiv.org/abs/2507.19457
- GEPA in DSPy: https://dspy.ai/api/optimizers/GEPA/overview/
- GEPA library: https://github.com/gepa-ai/gepa
- Contextual bandits / LinUCB (Li et al., WWW 2010): https://arxiv.org/abs/1003.0146
- Letta sleep-time compute (prior art): https://www.letta.com/blog/sleep-time-compute/
- MongoDB Atlas Vector Search: https://www.mongodb.com/docs/atlas/atlas-vector-search/
- Google Workspace MCP: https://developers.google.com/workspace/guides/configure-mcp-servers
- Claude Code scheduled tasks: https://code.claude.com/docs/en/scheduled-tasks
