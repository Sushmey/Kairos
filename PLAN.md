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
│  → normalize → LLM enrichment → MongoDB + embeddings          │
│  HDBSCAN clustering → cluster summaries                     │
│  (fallback: X data export for bootstrap without OAuth)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      CONTEXT SENSOR                         │
│  Calendar (Google API) · Location toggle · Time             │
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
│                      DELIVERY LAYER                         │
│  Cluster digest (summary + ranked links) + "Why now"        │
│  macOS notification → feedback capture (tap/snooze/dismiss) │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
  BANDIT UPDATE (online)          GEPA PASS (nightly)
  after every notification        re-enrich · tune prompts
  updates timing policy           emits "what I learned" diff
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

Links within a digest are ranked by relevance to current context, not ingest order. Snooze applies to the whole cluster for this context window and re-queues it with the context snapshot stamped on it.

---

## Headspace: Two Dimensions

"Headspace" decomposes into two orthogonal components that drive different parts of the ranking:

**Topical affinity** — what are you mentally oriented toward?
- Upcoming calendar event titles (embedded as intent signal)
- Recent event titles (topic trail from what just ended)
- Location type: office → work mode, cafe → exploratory, gym → nothing technical
- Post-meeting window: 15–30 min after a multi-person event, topics are primed

**Attention capacity** — how much cognitive bandwidth is available?
- Calendar gap size (minutes until next event)
- Meeting density today (% of day in meetings)
- Minutes since last meeting (recovery window)
- Surfaces already consumed today (fatigue proxy)

Topical affinity determines **which cluster** to surface. Attention capacity determines **whether any cluster is feasible** (energy cost filter).

---

## Data Models

### MongoDB Collections

**`bookmarks`** — one document per bookmark, embedding stored inline

```python
{
  "_id": ObjectId(),
  "x_tweet_id": str,                  # unique upsert key from X API
  "url": str,                         # https://x.com/i/web/status/{x_tweet_id}
  "raw_text": str,                    # note_tweet.text if present, else tweet.text
  "author_id": str,
  "author_username": str,
  "tweet_created_at": datetime,       # when the post was published (NOT bookmark time)
  "context_annotations": list[dict], # X-inferred entities — seed for topic_tags
  "referenced_tweets": list[dict],    # quoted/replied-to context (from expansions)
  "embedding": list[float],           # 384-dim, sentence-transformers all-MiniLM-L6-v2
  "cluster_id": ObjectId,             # assigned at ingest, updated nightly
  "topic_tags": list[str],            # LLM-enriched
  "consumption_mode": str,            # read-deep | skim | watch | act-in-world | save-to-project
  "energy_cost": float,               # 0.0–1.0
  "geo_anchor": str | None,           # extracted place/product name
  "geo_coords": [float, float] | None,# [lat, lon]
  "perishability": str,               # evergreen | dated | time-sensitive
  "ingested_at": datetime,
  "last_synced_at": datetime,
  "last_surfaced_at": datetime | None,
  "surface_count": int,
}
```

**`clusters`** — one document per topic cluster

```python
{
  "_id": ObjectId(),
  "name": str,                        # LLM-generated label
  "summary": str,                     # 2-sentence LLM summary, GEPA-tuned
  "centroid_embedding": list[float],  # mean of member embeddings
  "member_count": int,
  "last_updated": datetime,
}
```

**`feedback_events`** — one document per notification interaction

```python
{
  "_id": ObjectId(),
  "notification_id": str,
  "cluster_id": ObjectId,
  "context_snapshot": dict,           # full headspace vector at fire time
  "notification_text": str,           # exact text shown (input to GEPA eval)
  "links_shown": list[str],           # bookmark URLs in the digest
  "events": [
    { "type": "shown",      "t": 0 },
    { "type": "expanded",   "t": 4 },
    { "type": "link_click", "t": 9,  "url": str },
    { "type": "dismissed",  "t": 61 },
  ],
  "derived_reward": float,            # computed from event sequence
  "snooze_context": dict | None,      # context snapshot if action was snooze
  "created_at": datetime,
}
```

**`bandit_params`** — one document per cluster_class × context_class pair

```python
{
  "cluster_class": str,               # e.g. "distributed-systems"
  "context_class": str,               # e.g. "pre-meeting:infra"
  "alpha": float,                     # Thompson sampling beta distribution params
  "beta": float,
  "last_updated": datetime,
}
```

**`optimization_runs`** — GEPA pass history

```python
{
  "run_at": datetime,
  "prompt_before": str,
  "prompt_after": str,
  "engagement_before": float,
  "engagement_after": float,
  "diff_summary": str,                # "what I learned" — shown in dashboard
}
```

### Context Feature Vector (live at decision time)

```python
{
  # Topical affinity
  "upcoming_event_title": str,
  "upcoming_event_embedding": list[float],
  "recent_event_title": str | None,
  "post_meeting_minutes": int | None,  # time since last multi-person event ended
  "location_type": str,                # desk | commute | gym | cafe | near_anchor | unknown

  # Attention capacity
  "calendar_gap_minutes": int,
  "meeting_density_today": float,
  "minutes_since_last_meeting": int,
  "surfaces_today": int,
  "time_since_last_surface_minutes": int,

  # Time
  "hour": int,
  "day_of_week": int,
  "is_weekend": bool,
}
```

---

## Ranking Pipeline

### Step 1 — Feasibility Filter

```python
# MongoDB query before any vector search
{ "energy_cost": { "$lte": available_capacity },
  "cluster_id": { "$nin": snoozed_cluster_ids } }
```

### Step 2 — Topical Score (Atlas $vectorSearch)

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

Thompson sample from `bandit_params` for each candidate cluster × current context class. Adjusted score = `vector_score × bandit_weight`. The bandit reshapes pure similarity with learned history — it's how "infra threads before architecture meetings" gets amplified over time.

### Step 4 — Interrupt Gate

```
surfaces_today < daily_budget          ✓/✗
calendar_gap_minutes > energy_cost     ✓/✗
time_since_last_surface > min_gap      ✓/✗
adjusted_score > learned_threshold     ✓/✗

All pass → surface digest
Any fail → silence (re-evaluate at next context change)
```

**Silence is the feature.**

---

## Reward Function

| Action | Reward | Rationale |
|--------|--------|-----------|
| `acted` (went to place, added to todo) | +1.0 | Passive → execution achieved |
| `clicked ≥2 links` | +0.8 | Strong engagement |
| `clicked 1 link + dwelled >30s` | +0.6 | Solid engagement |
| `expanded digest` | +0.4 | Interest signal |
| `dwelled >15s, no click` | +0.2 | Weak positive |
| `snoozed` | 0.0 (re-queue) | Right thing, wrong time |
| `dismissed` | −0.4 | Wrong thing |
| `ignored` (expired without interaction) | −0.6 | Trained user to ignore |

**Dwell time alone is insufficient.** A positive label requires at minimum `expanded` or `link_click` — high dwell with zero clicks is ambiguous and treated as neutral. This guards against Goodhart: the agent cannot game its reward by writing longer summaries.

**Snooze is the most informative timing signal.** Re-queue with context snapshot stamped on it; the bandit learns "this cluster gets snoozed when meeting density > 0.7."

---

## Two Self-Improvement Loops

These are separate optimizers and must stay decoupled:

```
feedback_event.derived_reward
        │
        ├──► BANDIT UPDATE (online, after every event)
        │    Updates: bandit_params alpha/beta for cluster × context pair
        │    Effect: better timing — when to surface which cluster
        │
        └──► GEPA OPTIMIZATION (offline, nightly)
             Input: (cluster_content, context, notification_text) → reward
             Updates: summary/rationale generation prompt
             Effect: better framing — how the digest is written
             Artifact: optimization_runs diff (the demo closing slide)
```

---

## "Why Now" Rationale

Every digest includes one line exposing the policy decision, generated by the GEPA-tuned prompt:

> *"Dense read · 90-min gap · you usually absorb these Sunday morning at a coffee shop"*

This doubles as UX (transparency) and proof of learning (the rationale changes between sessions as the prompt evolves).

---

## Calendar Pull Mode

When an upcoming event title semantically matches a bookmark cluster (cosine similarity > 0.7), proactively assemble a dossier without waiting for the bandit to fire.

Example: "Infra Architecture Review" → surfaces distributed-systems cluster 30 min before the event.

This is a separate trigger path that bypasses the interrupt gate — calendar intent is high-confidence enough to always surface.

---

## Geo-Anchoring

At ingest: extract place/product mentions (LLM), resolve to coordinates (geopy). Geofence radius: 300m.

Trigger: location enters geofence + calendar gap exists + energy budget available → surface geo-anchored cluster.

Demo: manual "I am here" toggle. Continuous background GPS is an OS permissions swamp — skip it.

---

## Interfaces

### Web Dashboard (single page, two panes)

No split between user view and admin view — the observability IS the demo.

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

Real-time updates via **Server-Sent Events** (SSE) — one-directional, 20 lines of FastAPI, no WebSocket setup.

### Notification Delivery

macOS system notification (`terminal-notifier`). Fires from the scheduler, taps the OS. The web dashboard shows it in the activity log simultaneously. Clean separation: delivery vs. observability.

### MCP Server (FastMCP)

Makes the bookmark brain available as context in any AI-assisted workflow. The killer use case: coding in Claude Code and asking it to review an architecture decision — it calls `get_relevant_bookmarks` and pulls your hoarded threads directly into the conversation.

```python
@mcp.tool()
def get_relevant_bookmarks(query: str, limit: int = 5) -> list[Bookmark]:
    """Semantic search over bookmark index."""

@mcp.tool()
def get_cluster_summary(topic: str) -> ClusterDigest:
    """Return the cluster closest to topic with generated summary."""

@mcp.tool()
def surface_now(context: str | None = None) -> Notification | None:
    """Run full ranking pipeline against current context, return top candidate."""

@mcp.tool()
def add_bookmark(url: str, notes: str = "") -> Bookmark:
    """Ingest a new bookmark into the pipeline."""
```

---

## Scheduling

Custom scheduler eliminated. Three Claude Code mechanisms replace it:

| Job | Mechanism | Interval |
|-----|-----------|----------|
| Context polling + bandit decision (demo) | `/loop` in Claude Code session | 5 min |
| Context polling + bandit decision (prod) | Desktop Scheduled Task | 5 min |
| Nightly GEPA sleep-time pass | Cloud Routine → `POST /optimize` | Daily 2am |

During the demo: Claude Code session stays open with Kairos MCP connected. The `/loop` runs every 5 min, calls MCP tools, makes decisions. **The session transcript is the agent observability.** No custom logging UI needed.

---

## Stack

| Component | Tool |
|-----------|------|
| Persistence | MongoDB Atlas (all collections) |
| Vector search | Atlas `$vectorSearch` (inline with bookmark docs) |
| Embeddings | `sentence-transformers` all-MiniLM-L6-v2 |
| Clustering | HDBSCAN (natural topic boundaries, no fixed k) |
| Bandit | Thompson sampling over logistic model (`scikit-learn`, ~50 lines custom) |
| Prompt optimization | DSPy + GEPA |
| API backend | FastAPI + SSE |
| Scheduling | Claude Code `/loop` (demo) + Desktop Task (prod) + Cloud Routine (GEPA) |
| Notification delivery | `terminal-notifier` (macOS) |
| MCP server | FastMCP |
| Calendar | Google Calendar API (OAuth2) |
| Geo | `geopy` for geocoding, manual toggle for demo |
| Bookmark ingest | X API v2 `GET /2/users/{id}/bookmarks` (OAuth2 user token) |
| Bookmark bootstrap | X data export (fallback if OAuth/quota blocked) |
| LLM | Gemini via Interactions API (`google-genai`) + Antigravity SDK harness |

---

## X Bookmark Ingest

Primary source: **[X API Get Bookmarks](https://docs.x.com/x-api/users/get-bookmarks)** — returns Posts bookmarked by the authenticated user.

### Endpoint

```
GET https://api.x.com/2/users/{id}/bookmarks
```

| Parameter | Value |
|-----------|-------|
| `id` (path) | Authenticated user's numeric ID — **must match the OAuth token holder** |
| `max_results` | 1–100 per page (paginate until `meta.next_token` absent) |
| `pagination_token` | Base36 token from prior response `meta.next_token` |

**Required OAuth2 scopes:** `bookmark.read`, `tweet.read`, `users.read`

Auth flow: OAuth 2.0 authorization code via `https://api.x.com/2/oauth2/authorize` → token at `https://api.x.com/2/oauth2/token`. Store refresh token with `offline.access` scope for background sync.

### Recommended field/expansion set

Request these to maximize ingest quality without extra round-trips:

```
tweet.fields=created_at,entities,note_tweet,context_annotations,referenced_tweets,lang,attachments
expansions=author_id,referenced_tweets.id,attachments.media_keys
user.fields=username,name
```

**Text extraction rules:**
- Long posts: prefer `note_tweet.text` over truncated `text`
- Thread/quote context: merge expanded `includes.tweets` for referenced posts into enrichment input
- URLs: extract from `entities.urls[].expanded_url` (prefer over t.co shortlinks)
- Topic hints: pass `context_annotations` to LLM enrichment as weak priors for `topic_tags`

**Known API limitation:** the endpoint returns Tweet objects, not bookmark timestamps. We store `tweet_created_at` (post publish time) and `ingested_at` / `last_synced_at` (our sync time). Do not infer "when user bookmarked this."

### Sync strategy

```
Initial sync (Hour 0–1):
  paginate all pages → upsert by x_tweet_id → enrich + embed new docs only

Incremental sync (scheduled, e.g. daily or pre-demo):
  paginate from page 1 → upsert by x_tweet_id
  skip enrichment if doc exists and raw_text unchanged
  re-cluster nightly if member set changed

Error handling:
  UsageCapExceededProblem → fall back to export bootstrap, log clearly
  ClientForbiddenProblem    → check app enrollment / tier
  ResourceUnavailableProblem → tweet deleted/suspended; mark doc unavailable
```

Unique index: `{ x_tweet_id: 1 }` on `bookmarks`.

### Fallback: data export

If OAuth setup or quota blocks live sync during the hackathon window:

- Settings → Your Account → Download an archive → parse `bookmark.js` / tweet objects
- Same normalization → enrichment → embed pipeline; map export tweet IDs to `x_tweet_id`
- Demo still works; live sync is the production path

**Hour 1 checklist:**
1. Register X developer app, enable OAuth 2.0 user context
2. Confirm `bookmark.read` scope on token
3. One authenticated call returns paginated bookmarks
4. Log rate-limit headers; note tier cap before building sync loop

---

## Demo Strategy — No Real Feedback in 48h

Real continual learning takes weeks. A 48h demo with no feedback curve is a dead demo.

1. Seed a **synthetic persona** with scripted preferences ("never reads long ML papers on back-to-back days, devours them Sunday at a cafe")
2. Simulate 2 weeks of feedback events against that persona to populate `feedback_events`
3. Show engagement-rate curve climbing, dismissal/snooze rate falling (MongoDB aggregation → Chart.js)
4. **One live adaptation on stage**: surface a digest in the wrong context, hit dismiss, watch bandit update, surface a better one

Be explicit that real learning takes weeks; the simulator compresses it to 3 minutes. Judges respect this.

---

## Build Order

### Hour 0–2: Foundation
- [ ] MongoDB Atlas setup, collections + vector search index (`x_tweet_id` unique)
- [ ] X OAuth2 user-context flow + `GET /2/users/{id}/bookmarks` paginated sync client
- [ ] Normalize tweets → upsert `bookmarks` (note_tweet text, expansions, context_annotations)
- [ ] Export-parser fallback if API quota/OAuth blocked
- [ ] LLM enrichment (batch, async): topic_tags, consumption_mode, energy_cost, geo_anchor, perishability
- [ ] HDBSCAN clustering → populate `clusters` collection
- [ ] **Eval harness first**: fixed context×cluster pairs with ground-truth from synthetic persona

### Hour 2–5: Context + Ranking
- [ ] Context sensor: Google Calendar poller, time features, post-meeting window detection
- [ ] `$vectorSearch` ranking pipeline (steps 1–2)
- [ ] Thompson sampling bandit (steps 3–4)
- [ ] Interrupt gate + restraint budget

### Hour 5–8: Delivery + Feedback
- [ ] macOS notification via `terminal-notifier` with cluster digest
- [ ] Feedback capture: `feedback_events` write on tap/snooze/dismiss
- [ ] `derived_reward` computation from event sequence
- [ ] Snooze re-queue with context snapshot
- [ ] Geo-anchor extraction + geofence trigger
- [ ] Calendar pull mode (event title → cluster dossier)

### Hour 8–12: Self-Improvement Loops
- [ ] Bandit online update (alpha/beta on `bandit_params` after each event)
- [ ] GEPA loop on summary/rationale prompt against feedback-labeled eval set
- [ ] `optimization_runs` write with prompt diff
- [ ] `POST /optimize` endpoint for Cloud Routine trigger

### Hour 12–18: Interfaces
- [ ] FastAPI backend with SSE endpoint for live activity stream
- [ ] Web dashboard: two-pane layout, Chart.js engagement chart, prompt diff view
- [ ] FastMCP server with 4 tools
- [ ] Claude Code `/loop` prompt wired to MCP tools

### Hour 18–24: Simulator + Demo Prep
- [ ] Synthetic persona + feedback event simulator
- [ ] MongoDB aggregation for metrics (engagement rate, dismissal rate, session-over-session)
- [ ] Demo script + stage choreography
- [ ] "What I learned" diff as closing slide

### Hour 24–36: Polish
- [ ] Restraint budget learning from feedback
- [ ] "Why now" rationale tuned by GEPA
- [ ] Desktop Scheduled Task setup for production path

### Hour 36–48: Buffer / Stretch
- [ ] Incremental X bookmark sync on schedule (refresh token, skip unchanged)
- [ ] Additional sources (Pocket, Readwise export)

---

## Three Things Before Anyone Else Starts

1. **Eval harness before the bandit.** No yardstick = no demo. Self-generated evals are also a self-improvement-stack flex in the pitch.
2. **Snooze capture in hour 3, not hour 30.** Right-thing-wrong-time is the most informative timing signal and the one every other team misses.
3. **Make learning visible.** The session-to-session prompt diff is worth more on stage than any accuracy number. Show the machine editing itself.

---

## Pitch Frame

> Most second brains are write-only graveyards. You bookmark 500 things and read 12. Kairos doesn't make you a better searcher — it becomes a better interrupter. It learns that you never read long ML threads on back-to-back days but devour them Sunday morning at a coffee shop. It learns that "not now" on a ramen rec means "remind me when I'm near Chinatown with an hour free." Every night it rewrites the prompt it uses to describe your bookmarks, based on what you actually engaged with. The policy improves without you lifting a finger. Passive hoarding becomes execution.

---

## References

- GEPA (Agrawal et al., ICLR 2026 oral): https://arxiv.org/abs/2507.19457
- GEPA in DSPy: https://dspy.ai/api/optimizers/GEPA/overview/
- GEPA library: https://github.com/gepa-ai/gepa
- Contextual bandits / LinUCB (Li et al., WWW 2010): https://arxiv.org/abs/1003.0146
- Letta sleep-time compute (prior art to differentiate from): https://www.letta.com/blog/sleep-time-compute/
- MongoDB Atlas Vector Search: https://www.mongodb.com/docs/atlas/atlas-vector-search/
- FastMCP: https://github.com/jlowin/fastmcp
- Claude Code scheduled tasks: https://code.claude.com/docs/en/scheduled-tasks
- X API Get Bookmarks: https://docs.x.com/x-api/users/get-bookmarks
