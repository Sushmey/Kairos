## Learned User Preferences

- Prefer conventional commits grouped thematically (e.g. `feat(core):`, `feat(delivery):`, `docs:`) rather than one large commit.
- Keep documentation changes in separate `docs:` commits from code scaffolding.
- Delivery and UI should stay channel-agnostic: policy core decides; adapters handle web inbox, MCP host transcript, and optional OS notify.
- MCP integrations must respect host-agent mechanisms (render in transcript, optional local dashboard) rather than assuming a single delivery surface.
- Use one fixed embedding vector space in config; agents orchestrate pipeline timing, not per-request embedding model selection.

## Learned Workspace Facts

- Kairos is a contextual bandit for bookmark surfacing — optimizing when to interrupt, not on-demand search.
- LLM stack is Gemini: Interactions API (`google-genai`) for structured batch calls; Antigravity SDK (`google-antigravity`) for the agent harness and tool loop.
- Primary bookmark ingest is X API v2 `GET /2/users/{id}/bookmarks` (OAuth2 user token); X data export is the bootstrap fallback.
- Default embeddings via Gemini API (`gemini-embedding-001@768`); local sentence-transformers optional (`EMBEDDING_BACKEND=local`). HDBSCAN clustering on embeddings; Gemini names and summarizes clusters after grouping.
- Cluster digest generation uses Google Search grounding (`DIGEST_USE_GOOGLE_SEARCH`, default on) for timely web context in notifications.
- Cluster IDs are regenerated on each HDBSCAN run — no cross-run stable IDs or topic taxonomy yet.
- `HeartbeatService` is the channel-agnostic policy core; it returns `KAIROS_OK` or `SURFACE` and fans out via delivery adapters (`web`, `os`, MCP return payload).
- Python package lives under `src/kairos`, packaged with hatch; dependencies managed with `uv`.
- Data store is MongoDB (bookmarks, clusters, notifications, feedback_events); vector search drives ranking.
- Web gateway pattern: FastAPI + SSE (`/api/stream`, `POST /heartbeat`) with an inbox UI; OpenClaw-style heartbeat ack for silence.
- After each PLAN build-order phase, run adversarial judge skill (`.cursor/skills/kairos-adversarial-judge/`) and hackathon theme auditor (`.cursor/skills/kairos-hackathon-themes/`); update `docs/demo-readiness/` (FAQ, PHASE_REVIEWS, DEMO_SCRIPT_GAPS, THEME_LOG).
