# Kairos — developer guide

Senior-engineer map of how the system fits together, where complexity lives, and what to watch for when extending the product.

**New here?** Start with the animated walkthrough at http://127.0.0.1:8420/walkthrough after `just demo-serve`.

---

## Mental model

Kairos is a **contextual bandit** over bookmark **clusters**, not a search engine.

| Layer | Question it answers | Key code |
|-------|---------------------|----------|
| Ingest | What did the user save? | `ingest/sync.py`, X API |
| Enrich / research | What is each bookmark? | `bookmarks/enrich.py`, `bookmarks/research.py`, `link_fetch.py` |
| Cluster | What topics exist? | `bookmarks/index.py` (HDBSCAN) |
| Heartbeat | Should we interrupt *now*? | `core/ranking.py`, `core/heartbeat.py` |
| Delivery | How does the user see it? | `delivery/web.py` → SSE + inbox |
| Learn | Did they care? | `core/feedback.py` → bandit α/β |

**Silence is the default.** `KAIROS_OK` means all gates passed but policy chose not to surface, or a gate failed.

---

## UI ↔ backend contract

The dashboard (`web/static/index.html`) talks to FastAPI (`web/app.py`). Everything else (CLI, MCP) shares MongoDB but may not hit the same process.

### HTTP endpoints the UI uses

| UI action | Method | Path | Backend |
|-----------|--------|------|---------|
| Load inbox | GET | `/api/notifications` | `list_notifications(user_id=…)` |
| Dismiss / snooze | POST | `/api/feedback` | `heartbeat_service.record_feedback` |
| Auto / manual cycle | POST | `/api/heartbeat` | `run_decision_cycle` or ADK when `via_agent` / `HEARTBEAT_DEFAULT_VIA_AGENT` |
| Demo surface | POST | `/api/demo/surface` | reset headspace + cycle |
| Sidebar context | GET | `/api/context` | `get_context_async` |
| Clusters | GET | `/api/clusters` | `list_clusters` |
| Bandit panel | GET | `/api/bandit` | `list_bandit_params` |
| Metrics sparkline | GET | `/api/metrics` | `feedback_events` aggregates |
| Config / demo flags | GET | `/api/config` | `settings` subset (+ `job_backend`, `heartbeat_default_via_agent`) |
| GEPA run | POST | `/api/optimize` | `run_gepa` |
| GEPA history | GET | `/api/optimize/runs` | `list_optimization_runs` |
| Google OAuth status | GET | `/api/google/status` | session user or `KAIROS_USER_ID` |
| Live narration | SSE | `/api/stream` | `event_bus` (in-process only) |
| Prep pipeline | POST | `/api/prep/start` | `dispatch_prep_job` → local or Arq |
| Prep status | GET | `/api/prep/{job_id}` | Mongo `prep_jobs` |

### SSE event kinds (`data.kind`)

| kind | UI effect |
|------|-----------|
| `pipeline` | Admin log — ranking steps |
| `intelligence` | Admin log — LLM fusion, digest |
| `activity` | Admin “last decision” panel |
| `indicator` | Listening UI: `data.status` `alert` = surfacing, `ok` = silent |
| `notification` | Inbox card (`data.digest`) |
| `feedback` | Refresh bandit + notifications |
| `session` | Cycle start/finish |

**Important:** SSE replays in-process history **and** Mongo `pipeline_events` when `EVENT_PERSIST_ENABLED=true`, so CLI heartbeats that persist events still appear in the admin log after refresh.

### Notification statuses

Backend: `pending` · `snoozed` · `dismissed` · `acted` · `expired`

UI history maps `acted` → displayed as “engaged” (positive feedback).

---

## Prep vs runtime (common confusion)

| Phase | When | What runs | Gemini? |
|-------|------|-----------|---------|
| **Prep** | `just demo-corpus` or `kairos bookmarks prep` | enrich + research + embed + cluster | Yes, batch |
| **Cluster** | `kairos bookmarks embed && cluster` | vectors + HDBSCAN | Label only |
| **Heartbeat** | Surface / auto-heartbeat | rank → gates → digest | Yes, per surface |

Pre-research fills **bookmark cards** in the digest. Digest generation uses one LLM call when `INTELLIGENCE_DIGEST_RUNTIME_FAST=true` (demo default).

```bash
uv run kairos bookmarks prep              # full pipeline — preferred
uv run kairos bookmarks prep --sync       # incremental X sync first (default)
uv run kairos bookmarks prep --sync --full-sync   # full X pagination
# or step-by-step:
uv run kairos bookmarks enrich && research && embed && cluster
```

---

## Data models

| Layer | Typed as | Examples |
|-------|----------|----------|
| Policy / surface | Pydantic `models/schemas.py` | `HeartbeatResult`, `ClusterDigest`, `DigestLinkCard` |
| Prep jobs | Pydantic `models/jobs.py` | `PrepJobParams`, `PrepJobRecord` |
| GEPA | Pydantic `models/optimize.py` | `GepaRunResult`, `FixtureEvalResult` |
| Sensors | Pydantic `models/sensors.py` | `CalendarEvent`, `FuseHeadspacePayload` |
| Pipeline stages | `@dataclass` in `bookmarks/` | `PipelineResult`, `EnrichResult`, `ClusterResult` |
| SSE | `@dataclass` `AgentEvent` | In-process + Mongo replay |

Prefer Pydantic at **API and persistence boundaries**; keep lightweight dataclasses for internal stage counters. JSON serialization uses **orjson** (`orjson.dumps` / `orjson.loads`).

---

## Complexity hotspots

1. **Research worker** — per bookmark: HTTP link fetch (`trafilatura` + OG fallback) + optional grounded Gemini; two concurrency semaphores (`bookmarks/research.py`).
2. **Ranking** — vector search fallback, Thompson sampling, optional moment-fit, multi-step digest (`core/ranking.py`, `llm/generation.py`).
3. **Cluster rebuild** — full recluster still deletes stale cluster docs; stable `cluster_id` reuse when centroid cosine ≥ `CLUSTER_ID_REUSE_THRESHOLD` (`bookmarks/index.py`).
4. **Enrich paths** — X sync is raw-only by default; enrich/research via `kairos bookmarks prep` (single path).
5. **Demo headspace** — `reset_demo_headspace` vs Google sync vs `DEFAULT_DEMO_OVERRIDE` for embedding can disagree on gates.

---

## Incorrect or fragile assumptions

| Assumption | Reality |
|------------|---------|
| X sync enriches inline | Default `enrich=False`; use `kairos bookmarks prep` |
| Architecture “skip cluster when fingerprints unchanged” | Skips when no unclustered embeddings and embed wrote 0 rows |
| Enrich skip = “already enriched” | Legacy rows without `enrich_source_hash` may skip if `consumption_mode` set |
| Research hash includes link body | Embed fingerprint uses tags + raw_text only — research won't trigger re-embed |
| `GET /api/google/status` ignores session | Uses session cookie user, then `KAIROS_USER_ID` fallback |
| Anonymous web users | `bandit_user_id` → `__default__` shared namespace |
| Sidebar bookmark count | Sums cluster `member_count` — noise bookmarks excluded |
| Partial research failure | Exit 0 if any succeeded; Justfile may still show ⚠ |
| Snooze survives demo reset | TTL 120m; cluster blocked per `context_class` |
| SSE only in-process | Mongo `pipeline_events` replays when `EVENT_PERSIST_ENABLED=true` |

---

## Demo flow (`Justfile`)

```
demo-serve = demo-prep + demo-surface + dashboard
demo-prep  = demo-corpus + gym + reset + optional Google sync
demo-corpus = enrich + research + embed + cluster (via bookmarks prep)
```

Env: `.env.demo` — `DEMO_MODE`, `AUTO_HEARTBEAT=false`, lower `SURFACE_SCORE_THRESHOLD`, digest search off.

---

## Extension checklist

- [ ] New API route? Update `walkthrough.html` API table and this doc.
- [ ] New SSE kind? Handle in `handleEvent()` + `logPrefix` map.
- [ ] New bookmark field? `BookmarkDocument`, `build_bookmark_link_card`, `applyNotification` mapping.
- [x] Multi-user notifications + Google status — bandit metrics still global in `/api/metrics`.
- [ ] After embed, run cluster or avoid clearing `cluster_id` mid-flight.

---

## Manim explainer (optional)

See `scripts/manim/README.md` — programmatic animation of the heartbeat loop using [3b1b/manim](https://github.com/3b1b/manim) (install `manimgl`, not community `manim`).

```bash
pip install manimgl
manimgl scripts/manim/kairos_flow.py KairosFlow
```

---

## Related docs

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system design
- [demo-readiness/DEMO.md](./demo-readiness/DEMO.md) — stage runbook
- [demo-readiness/FAQ.md](./demo-readiness/FAQ.md) — judge Q&A
- [MCP_SETUP.md](./MCP_SETUP.md) — agent path
- [LOCAL_QUEUE.md](./LOCAL_QUEUE.md) — optional Arq + Redis for prep jobs
