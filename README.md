# Kairos

Contextual bandit that learns **when** to surface bookmark clusters — silence is the default.

## Quick start

```bash
cp .env.example .env   # MONGODB_URI, GEMINI_API_KEY
brew install just      # or: cargo install just
just demo-serve
```

Open http://127.0.0.1:8420 → **Surface now** → dismiss → Admin view (bandit β).

## Docs

| Doc | Purpose |
|-----|---------|
| [docs/TECH_DEBT.md](docs/TECH_DEBT.md) | Simplification roadmap + **what's next** |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Senior-engineer map + UI↔API contract |
| [docs/demo-readiness/DEMO.md](docs/demo-readiness/DEMO.md) | Stage runbook |
| [docs/demo-readiness/FAQ.md](docs/demo-readiness/FAQ.md) | Judge Q&A |
| [docs/LOCAL_QUEUE.md](docs/LOCAL_QUEUE.md) | Optional Arq + Redis prep queue |
| [PLAN.md](PLAN.md) | Product thesis + original build order |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/MCP_SETUP.md](docs/MCP_SETUP.md) | MCP + Google OAuth |

**Walkthrough:** after `just demo-serve`, open http://127.0.0.1:8420/walkthrough for an animated prep → heartbeat tour. Optional Manim video: [scripts/manim/README.md](scripts/manim/README.md).

## CLI

```bash
uv run kairos bookmarks prep   # enrich → research → embed → cluster (preferred)
uv run kairos bookmarks sync    # X bookmarks (raw; prep enriches)
uv run kairos heartbeat         # one policy cycle (direct path)
uv run kairos heartbeat --via-agent   # ADK sensor-fusion path
uv run kairos optimize readiness     # GEPA sample check
uv run kairos serve             # web dashboard
uv run kairos worker            # Arq prep worker (optional; needs --extra queue)
uv run kairos mcp               # MCP server
```
