# Kairos — Plan

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

**Direct path** (`kairos heartbeat`): calls `heartbeat_service.run()` directly. Fastest, used by Desktop scheduled task and Claude Code `/loop` MCP tool calls.

**Agent path** (`kairos agent-cycle`): wraps the heartbeat in the Antigravity SDK agent harness. The Gemini model reasons over `run_heartbeat` tool call, then Antigravity hooks emit each tool call and turn to the EventBus. Used when natural-language reasoning over context is needed.

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
        ├──► BANDIT UPDATE (online, after every feedback event)
        │    Updates: bandit_params alpha/beta for cluster × context pair
        │    Wire point: heartbeat_service.record_feedback() → TODO
        │
        └──► GEPA OPTIMIZATION (offline, nightly via Cloud Routine → POST /optimize)
             Input: (notification_text, context_snapshot) → derived_reward
             Updates: summary/rationale generation prompt in generation.py
             Artifact: optimization_runs doc → dashboard diff view
```

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

`kairos serve` is a CLI stub — needs FastAPI app implementation.

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
