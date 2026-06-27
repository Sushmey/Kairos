# Kairos Architecture

Kairos is a **contextual bandit** that learns **when** to surface bookmark *clusters* — not a search engine, not a cron digest. Silence (`KAIROS_OK`) is the default; interrupt only when calendar capacity, topical fit, and learned engagement align.

This document maps the running system in `src/kairos/`. For product thesis and build order, see [PLAN.md](../PLAN.md).

---

## System overview

```mermaid
flowchart TB
    subgraph Entry["Entry points"]
        CLI["CLI<br/><code>kairos</code>"]
        WebUI["Web dashboard<br/><code>kairos serve</code>"]
        Agent["Agent harness<br/><code>agent-cycle</code>"]
    end

    subgraph Policy["Policy plane"]
        HS["HeartbeatService"]
        Rank["Ranking pipeline"]
        Ctx["Context sensor"]
    end

    subgraph Data["Data plane"]
        Ingest["Ingest + enrich"]
        Embed["Embed + cluster"]
        Mongo[(MongoDB)]
    end

    subgraph External["External services"]
        XAPI["X API v2"]
        Gemini["Gemini API"]
    end

    subgraph Output["Delivery + observability"]
        Del["Delivery adapters"]
        Bus["EventBus"]
        SSE["SSE /api/stream"]
    end

    CLI --> HS
    WebUI --> HS
    Agent --> HS

    HS --> Ctx
    HS --> Rank
    HS --> Del
    HS --> Mongo

    Rank --> Embed
    Rank --> Gemini
    Ctx -.->|"planned"| Calendar["Google Calendar MCP"]

    Ingest --> XAPI
    Ingest --> Gemini
    Ingest --> Mongo
    Embed --> Gemini
    Embed --> Mongo

    Del --> Bus
    Bus --> SSE
    SSE --> WebUI

    WebUI -->|"POST /api/feedback"| HS
```

---

## Layer model

| Layer | Responsibility | Key modules |
|-------|----------------|-------------|
| **Ingest** | Pull X bookmarks, normalize, enrich | `ingest/`, `bookmarks/enrich.py` |
| **Index** | Embed, cluster, fingerprint stale rows | `embeddings/`, `bookmarks/index.py` |
| **Context** | Headspace vector at decision time | `core/context.py`, `core/moment.py` |
| **Policy** | Rank, gate, surface or silence | `core/ranking.py`, `core/bandit.py` |
| **Delivery** | Fan-out to web, OS, host transcript | `delivery/` |
| **Feedback** | Implicit signals → online bandit | `core/feedback.py`, `db/feedback.py` |
| **Observability** | Live activity stream | `observability/bus.py`, `web/app.py` |

---

## 1. Ingest layer

Pulls bookmarks from X, normalizes API payloads, enriches with Gemini metadata, and upserts into MongoDB.

```mermaid
flowchart LR
    subgraph X["X API v2"]
        OAuth["OAuth 2.0 PKCE<br/><code>ingest/x/oauth.py</code>"]
        Client["XApiClient<br/><code>ingest/x/client.py</code>"]
        Norm["normalize_bookmark<br/><code>ingest/x/normalize.py</code>"]
    end

    subgraph Sync["Sync orchestration"]
        SyncFn["sync_bookmarks_from_x<br/><code>ingest/sync.py</code>"]
        EnrichInline["enrich_bookmark_documents<br/><code>ingest/enrich.py</code>"]
    end

    subgraph LLM["Gemini"]
        EnrichAPI["enrich_bookmark<br/><code>llm/generation.py</code>"]
    end

    subgraph Store["MongoDB"]
        BM[("bookmarks")]
    end

    OAuth --> Client
    Client -->|"paginated GET /bookmarks"| Norm
    Norm --> SyncFn
    SyncFn --> EnrichInline
    EnrichInline --> EnrichAPI
    EnrichAPI -->|"topic_tags, energy_cost,<br/>consumption_mode"| SyncFn
    SyncFn -->|"upsert by x_tweet_id"| BM
```

**Enrichment output** (`BookmarkEnrichment`): topic tags, consumption mode, energy cost, geo anchor, perishability.

**CLI:** `kairos x auth`, `kairos x sync`, `kairos bookmarks enrich`

---

## 2. Embed + cluster (index layer)

One fixed vector space (config-driven). Fingerprints skip unchanged rows. HDBSCAN groups bookmarks into topic clusters.

```mermaid
flowchart TB
    subgraph Input
        Docs[("bookmarks<br/>without embedding")]
    end

    subgraph Encoder["Embedding encoder<br/><code>embeddings/encoder.py</code>"]
        Dispatch{backend?}
        Local["local_encoder<br/>BAAI/bge-small-en-v1.5"]
        GeminiEmb["gemini_encoder<br/>gemini-embedding-001@768"]
    end

    subgraph Cluster["Clustering<br/><code>bookmarks/index.py</code>"]
        FP["embed_fingerprint<br/><code>bookmarks/fingerprints.py</code>"]
        HDB["HDBSCAN"]
        Centroid["centroid_embedding"]
        Label["tag-heuristic name + summary"]
    end

    subgraph Output
        BM2[("bookmarks<br/>+ embedding + cluster_id")]
        CL[("clusters")]
    end

    Docs --> FP
    FP -->|"stale?"| Dispatch
    Dispatch -->|local| Local
    Dispatch -->|gemini default| GeminiEmb
    Local --> BM2
    GeminiEmb --> BM2
    BM2 --> HDB
    HDB --> Centroid
    Centroid --> Label
    Label --> CL
    CL -->|"member_count, centroid"| BM2
```

**Incremental pipeline** (`bookmarks/pipeline.py`): sync → enrich → embed → cluster (skips re-cluster when fingerprints unchanged).

**CLI:** `kairos bookmarks embed`, `kairos bookmarks cluster`, `kairos bookmarks clusters`

---

## 3. Context sensor

Two dimensions drive the policy: **topical affinity** (what you're oriented toward) and **attention capacity** (whether interrupt is feasible).

```mermaid
flowchart TB
    subgraph Sources["Signal sources"]
        Cal["Google Calendar<br/>🚧 planned"]
        Loc["Location toggle<br/>🚧 planned"]
        Demo["Demo persona stub<br/><code>core/context.py</code>"]
    end

    subgraph Snapshot["ContextSnapshot<br/><code>models/schemas.py</code>"]
        Topical["Topical affinity<br/>upcoming/recent events<br/>location_type"]
        Capacity["Attention capacity<br/>calendar_gap_minutes<br/>meeting_density_today<br/>surfaces_today"]
    end

    subgraph Bucket["Context bucketing<br/><code>core/moment.py</code>"]
        Class["context_class<br/>e.g. cafe_long_gap"]
        Moment["moment_text<br/>→ query embedding"]
    end

    Cal -.-> Snapshot
    Loc -.-> Snapshot
    Demo --> Snapshot
    Snapshot --> Class
    Snapshot --> Moment
```

| Field | Role |
|-------|------|
| `calendar_gap_minutes` | Gate: min gap before interrupt |
| `location_type` | Topical mode (desk, cafe, gym, …) |
| `surfaces_today` | Daily budget / fatigue |
| `time_since_last_surface_minutes` | Min gap between surfaces |

---

## 4. Ranking pipeline

The thesis lives here: moment → cluster fit × learned bandit weight → interrupt gate → digest or silence.

```mermaid
flowchart TB
    Start([evaluate_surface]) --> Snooze["Filter snoozed clusters<br/><code>db/feedback.py</code>"]
    Snooze --> EmbedQ["encode_query(moment_text)<br/><code>embeddings/encoder.py</code>"]

    EmbedQ --> Loop{{"For each cluster"}}
    Loop --> Cosine["cosine(moment_vec, centroid)"]
    Cosine --> TS["Thompson sample α,β<br/><code>core/bandit.py</code>"]
    TS --> Adj["adjusted = vector × bandit_weight"]
    Adj --> Best["Pick best cluster"]

    Best --> Gate{"Interrupt gate"}
    Gate --> G1["daily_budget"]
    Gate --> G2["calendar_gap"]
    Gate --> G3["min_gap since last surface"]
    Gate --> G4["score_threshold"]

    G1 & G2 & G3 & G4 --> Decision{all pass?}
    Decision -->|no| OK["KAIROS_OK<br/>SurfaceDecision.should_surface=false"]
    Decision -->|yes| Digest["generate_cluster_digest<br/><code>llm/generation.py</code>"]
    Digest --> Links["Merge real bookmark URLs"]
    Links --> Surface["SURFACE<br/>+ ClusterDigest"]

    OK --> Emit["EventBus: activity"]
    Surface --> Emit
```

```mermaid
sequenceDiagram
    participant HS as HeartbeatService
    participant Ctx as read_context
    participant Rank as evaluate_surface
    participant Emb as encode_query
    participant Band as bandit_params
    participant LLM as generate_cluster_digest

    HS->>Ctx: ContextSnapshot
    Ctx-->>HS: cafe, 90min gap, …
    HS->>Rank: context, override?
    Rank->>Emb: moment_text(context)
    Emb-->>Rank: moment vector
    loop each cluster
        Rank->>Band: get_bandit_params(cluster, context_class)
        Band-->>Rank: α, β
        Rank->>Rank: adjusted = cosine × Thompson(α,β)
    end
    alt gates pass
        Rank->>LLM: snippets + context
        LLM-->>Rank: ClusterDigest (+ optional Google Search)
        Rank-->>HS: should_surface=true
    else gates fail
        Rank-->>HS: should_surface=false
    end
```

**Module map:** `core/ranking.py` · `core/bandit.py` · `core/moment.py` · `db/bandit.py` · `db/clusters.py`

---

## 5. HeartbeatService (policy core)

Single orchestrator for every runtime path — CLI, web, agent, MCP.

```mermaid
stateDiagram-v2
    [*] --> ReadContext: run()
    ReadContext --> Evaluate: evaluate_surface()
    Evaluate --> KairosOK: not should_surface
    Evaluate --> Persist: should_surface
    Persist --> Deliver: save_notification()
    Deliver --> Surface: deliver(adapters)
    KairosOK --> [*]: HeartbeatResult KAIROS_OK
    Surface --> [*]: HeartbeatResult SURFACE

    note right of KairosOK
        event_bus: indicator KAIROS_OK
        reason from gate_reasons
    end note

    note right of Surface
        event_bus: indicator SURFACE
        notification UUID persisted
    end note
```

```mermaid
flowchart LR
    subgraph HeartbeatService["core/heartbeat.py"]
        Run["run()"]
        FB["record_feedback()"]
    end

    subgraph Deps
        Ctx["read_context"]
        Rank["evaluate_surface"]
        Save["save_notification"]
        Del["deliver"]
        Proc["process_feedback"]
    end

    Run --> Ctx --> Rank
    Rank -->|SURFACE| Save --> Del
    FB --> Proc
```

**Contract:** `HeartbeatResult` — same shape for HTTP, CLI JSON, and future MCP.

---

## 6. Delivery layer

Adapters fan out surfaced digests without changing policy logic.

```mermaid
flowchart TB
    HS["HeartbeatService"]
    Reg["delivery/registry.py"]

    subgraph Adapters
        Web["WebDeliveryAdapter<br/><code>delivery/web.py</code>"]
        OS["OSDeliveryAdapter<br/><code>delivery/os.py</code>"]
        Ret["return_only<br/>(no adapter)"]
    end

    subgraph Consumers
        Bus["EventBus"]
        SSE["FastAPI SSE"]
        Inbox["index.html inbox"]
        Term["terminal-notifier<br/>🚧 optional"]
        Host["MCP host transcript"]
    end

    HS --> Reg
    Reg --> Web
    Reg --> OS
    Reg --> Ret

    Web -->|"emit notification"| Bus
    Bus --> SSE --> Inbox
    OS -.-> Term
    Ret --> Host
```

**Render:** `delivery/render.py` — markdown digest + delivery hints for host agents.

---

## 7. Feedback loop + contextual bandit

Online learning without LLM fine-tuning. Snooze ≠ dismiss.

```mermaid
flowchart TB
    subgraph UI["User actions"]
        Snooze["Snooze 2h"]
        Dismiss["Not relevant"]
        Click["Link click"]
    end

    subgraph API
        POST["POST /api/feedback<br/>kairos feedback"]
    end

    subgraph Process["process_feedback<br/><code>core/feedback.py</code>"]
        Lookup["get_notification"]
        Reward["reward_for_action<br/><code>core/rewards.py</code>"]
        Insert["insert_feedback_event"]
        Update["apply_bandit_reward"]
        Status["update_notification_status"]
    end

    subgraph Mongo[(MongoDB)]
        FE[("feedback_events")]
        BP[("bandit_params")]
        NT[("notifications")]
    end

    Snooze --> POST
    Dismiss --> POST
    Click --> POST

    POST --> Lookup --> Reward
    Reward --> Insert --> FE
    Reward -->|"reward ≠ null"| Update --> BP
    Reward -->|"snooze: null reward"| Status
    Update --> Status --> NT
```

**Reward table**

| Action | Reward | Bandit update |
|--------|--------|---------------|
| `acted` | +1.0 | α += 1.0 |
| `link_click` | +0.8 | α += 0.8 |
| `expanded` | +0.4 | α += 0.4 |
| `snoozed` | — | Exclude cluster from ranking (TTL) |
| `dismissed` | −0.4 | β += 0.4 |
| `ignored` | −0.6 | β += 0.6 |

```mermaid
flowchart LR
    subgraph Bandit["Thompson sampling<br/>per cluster × context_class"]
        Alpha["α successes"]
        Beta["β failures"]
        Sample["weight ~ Beta(α,β)"]
    end

    Alpha --> Sample
    Beta --> Sample
    Sample --> Rank["adjusted score"]
    Rank --> Next["next heartbeat"]
    Feedback["feedback_events"] --> Alpha
    Feedback --> Beta
```

---

## 8. Observability + web gateway

In-process pub/sub streams agent activity to the dashboard admin panel.

```mermaid
flowchart TB
    subgraph Producers["EventBus emitters"]
        HS["HeartbeatService"]
        Rank["ranking.py"]
        Ctx["context.py"]
        Del["WebDeliveryAdapter"]
        FB["record_feedback"]
        Agent["agent/hooks.py"]
    end

    subgraph Bus["EventBus<br/><code>observability/bus.py</code>"]
        Hist["history buffer (500)"]
        Sub["asyncio.Queue subscribers"]
    end

    subgraph Web["FastAPI<br/><code>web/app.py</code>"]
        Stream["GET /api/stream SSE"]
        Notif["GET /api/notifications"]
        BanditAPI["GET /api/bandit"]
        HeartbeatAPI["POST /api/heartbeat"]
        FeedbackAPI["POST /api/feedback"]
    end

    subgraph UI["static/index.html"]
        User["User inbox"]
        Admin["Admin activity feed"]
    end

    Producers --> Bus
    Bus --> Stream
    Stream --> Admin
    Notif --> User
    BanditAPI --> Admin
    HeartbeatAPI --> HS
    FeedbackAPI --> FB
```

**Event kinds:** `session`, `context`, `activity`, `indicator`, `notification`, `feedback`, `turn`, `cluster`, `search`

---

## 9. Agent harness

Two runtime paths share `HeartbeatService`.

```mermaid
flowchart TB
    subgraph Direct["Direct path (default)"]
        CLI1["kairos heartbeat"]
        API["POST /api/heartbeat"]
        Harness["run_decision_cycle<br/><code>agent/harness.py</code>"]
    end

    subgraph AgentPath["Agent path"]
        CLI2["kairos agent-cycle"]
        AG["Antigravity Agent"]
        Gemini["Gemini model"]
        Tools["agent/tools.py"]
        Hooks["agent/hooks.py → EventBus"]
    end

    HS["HeartbeatService"]

    CLI1 --> Harness --> HS
    API --> Harness
    CLI2 --> AG --> Gemini
    Gemini --> Tools
    Tools --> HS
    AG --> Hooks
```

| Tool | Status | Purpose |
|------|--------|---------|
| `run_heartbeat` | ✅ | Policy cycle |
| `get_current_context` | ✅ | Headspace vector |
| `get_cluster_summary` | ✅ | Topic → cluster lookup |
| `record_feedback` | ✅ | Bandit update |
| `get_relevant_bookmarks` | 🚧 stub | Search (not thesis) |
| `ingest_bookmark` | ✅ | Manual URL ingest |

---

## 10. CLI surface

```mermaid
mindmap
  root((kairos))
    Policy
      heartbeat
      feedback
      agent-cycle
      chat
    Web
      serve
    Bookmarks
      list
      enrich
      embed
      cluster
      clusters
    Ingest
      x auth
      x sync
      x refresh
    Dev
      x whoami
      x auth-check
```

---

## 11. MongoDB collections

```mermaid
erDiagram
    bookmarks ||--o| clusters : "cluster_id"
    notifications }o--|| clusters : "cluster_id"
    feedback_events }o--|| notifications : "notification_id"
    feedback_events }o--|| clusters : "cluster_id"
    bandit_params }o--|| clusters : "cluster_id"

    bookmarks {
        string x_tweet_id UK
        string url
        string raw_text
        float[] embedding
        string cluster_id
        list topic_tags
        string consumption_mode
        float energy_cost
        string embed_fingerprint
    }

    clusters {
        string cluster_id UK
        string name
        string summary
        float[] centroid_embedding
        int member_count
    }

    notifications {
        string notification_id UK
        string cluster_id
        object digest
        object context_snapshot
        string status
        datetime created_at
    }

    feedback_events {
        string event_id UK
        string notification_id
        string cluster_id
        string context_class
        string action
        float derived_reward
        object context_snapshot
    }

    bandit_params {
        string cluster_id
        string context_class
        float alpha
        float beta
        datetime last_updated
    }
```

**Planned (P7):** `optimization_runs` — GEPA prompt diffs from nightly eval.

---

## 12. LLM layer

All structured generation goes through the Gemini Interactions API.

```mermaid
flowchart LR
    subgraph Callers
        IngestEnrich["bookmark enrich"]
        Digest["cluster digest"]
        Ground["Google Search grounding"]
    end

    subgraph LLM["llm/"]
        Client["client.py<br/>get_genai_client"]
        Gen["generation.py"]
        GroundMod["grounding.py"]
    end

    subgraph Models
        Lite["gemini-3.1-flash-lite<br/>enrichment"]
        Flash["gemini-3.5-flash<br/>digest"]
        EmbedM["gemini-embedding-001<br/>vectors"]
    end

    IngestEnrich --> Gen --> Lite
    Digest --> Gen --> Flash
    Ground --> GroundMod --> Flash
    EmbedM -.->|"embeddings/"| EmbedEnc["gemini_encoder.py"]
```

**Digest modes:** structured `ClusterDigestCore` + optional `DIGEST_USE_GOOGLE_SEARCH` for live web context.

---

## 13. Self-improvement (planned P7)

```mermaid
flowchart TB
    subgraph Online["Online — shipped"]
        FB["feedback_events"]
        BP["bandit_params"]
        TS["Thompson sampling"]
    end

    subgraph Offline["Offline — planned"]
        Eval["Eval harness<br/>fixed context×cluster pairs"]
        GEPA["GEPA nightly pass"]
        OR["optimization_runs<br/>prompt diffs"]
    end

    subgraph Dashboard
        Chart["Engagement curve"]
        Diff["Prompt diff panel"]
    end

    FB --> Eval
    Eval --> GEPA --> OR
    OR --> Diff
    BP --> Chart
    TS --> Online
```

**Honest scope:** policy RSI at the application layer (bandit + prompt meta-optimization). No LLM weight training.

---

## 14. End-to-end lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant X as X API
    participant Ingest
    participant Mongo
    participant Heartbeat
    participant Rank
    participant Web
    participant Bandit

    Note over X,Mongo: Data plane (batch / incremental)
    User->>Ingest: kairos x sync
    Ingest->>X: GET bookmarks
    X-->>Ingest: tweets
    Ingest->>Mongo: bookmarks + enrichment
    User->>Ingest: kairos bookmarks embed|cluster
    Ingest->>Mongo: embeddings + clusters

    Note over User,Bandit: Policy plane (heartbeat loop)
    User->>Heartbeat: kairos heartbeat / POST /api/heartbeat
    Heartbeat->>Rank: evaluate_surface
    Rank->>Mongo: clusters, bandit_params
    Rank-->>Heartbeat: SURFACE + digest
    Heartbeat->>Mongo: save notification
    Heartbeat->>Web: EventBus → SSE → inbox

    User->>Web: Dismiss / Snooze
    Web->>Heartbeat: POST /api/feedback
    Heartbeat->>Mongo: feedback_events + bandit_params
    Heartbeat->>Web: SSE feedback event

    User->>Heartbeat: next heartbeat
    Heartbeat->>Rank: evaluate_surface
    Rank->>Bandit: updated α/β
    Rank-->>Heartbeat: KAIROS_OK or different cluster
```

---

## 15. Configuration

Central settings in `config.py` (env + `.env`):

| Setting | Default | Effect |
|---------|---------|--------|
| `EMBEDDING_BACKEND` | `gemini` | Vector encoder dispatch |
| `DAILY_SURFACE_BUDGET` | `3` | Max surfaces / day |
| `SURFACE_SCORE_THRESHOLD` | `0.12` | Min adjusted score |
| `MIN_CALENDAR_GAP_MINUTES` | `30` | Attention capacity gate |
| `SNOOZE_TTL_MINUTES` | `120` | Snooze exclusion window |
| `DIGEST_USE_GOOGLE_SEARCH` | `true` | Ground digest with web |
| `DELIVERY_TARGETS` | `web` | Adapter fan-out |

---

## Module index

```
src/kairos/
├── cli.py                 # CLI entry
├── config.py              # Settings
├── agent/                 # Antigravity harness + tools
├── bookmarks/             # Enrich, embed, cluster, pipeline
├── core/                  # Policy: context, ranking, bandit, feedback
├── db/                    # MongoDB repositories
├── delivery/              # Web + OS adapters
├── embeddings/            # Local + Gemini encoders
├── ingest/                # X OAuth, sync, normalize
├── llm/                   # Gemini generation + grounding
├── models/                # Pydantic schemas
├── observability/         # EventBus
└── web/                   # FastAPI + static dashboard
```

---

## Related docs

- [PLAN.md](../PLAN.md) — product thesis and build order
- [demo-readiness/FAQ.md](demo-readiness/FAQ.md) — judge Q&A
- [demo-readiness/PHASE_REVIEWS.md](demo-readiness/PHASE_REVIEWS.md) — adversarial phase log
- [demo-readiness/THEME_LOG.md](demo-readiness/THEME_LOG.md) — hackathon theme proofs
