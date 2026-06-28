# Hackathon Theme Log

Append-only. Each entry from `kairos-hackathon-themes` skill after a development phase.

Official tracks:
- **Continual Learning** (primary)
- **Self-Improvement Stack** (secondary)
- **Recursive Intelligence** (stretch — honest scope only)

---

## Baseline — post P3 — 2025-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PLANNED | Data plane only; stubs | "Corpus exists; bandit learns after P4–P5." |
| Self-Improvement Stack | PARTIAL | MongoDB; EventBus | "Contracts exist; feedback log not wired." |
| Recursive Intelligence | NONE | — | "Out of scope until P7 GEPA." |

**Verdict:** THEME-GAP

---

## Phase P4 — Rank + Bandit — 2025-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PARTIAL | Thompson sampling reads `bandit_params`; live SURFACE | "Policy picks when to interrupt — learning weights come from feedback." |
| Self-Improvement Stack | PARTIAL | Notifications + bandit_params collections; EventBus | "Every surface is persisted for later eval." |
| Recursive Intelligence | NONE | — | — |

**Strongest theme this phase:** Continual Learning (thesis architecture live)
**Weakest theme / judge risk:** No closed feedback loop yet — looks like smart notifications until P5
**Verdict:** THEME-READY for P4 scope · Continual Learning needs P5 for PROVEN
**Next (max 2):**
1. P5 feedback loop
2. Rehearse SURFACE beat

---

## Phase P5 — Feedback Loop — 2025-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PROVEN | `feedback_events` + online α/β; dismiss → beta 1.8 observed | "Dismiss at the wrong moment increments β — policy adapts without retraining." |
| Self-Improvement Stack | PARTIAL | feedback_events, bandit_params, notifications in MongoDB | "Every interaction is logged for eval and offline GEPA." |
| Recursive Intelligence | NONE | — | "Prompt RSI via GEPA in P7 — not weight training." |

**Strongest theme this phase:** Continual Learning (primary hackathon track)
**Weakest theme / judge risk:** No engagement curve / prompt diff dashboard yet (Self-Improvement Stack)
**Verdict:** THEME-READY — primary track demo-able via CLI + MongoDB
**Next (max 2):**
1. P6 observability (SSE + inbox) for Self-Improvement Stack visibility
2. P7 GEPA for Recursive Intelligence honest story

---

## Phase P6 — Surface UX — 2026-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PROVEN | Snooze/dismiss in inbox → `POST /api/feedback` → α/β update; SSE `feedback` events | "One tap on 'Not relevant' increments β — the bandit adapts without retraining." |
| Self-Improvement Stack | PROVEN | EventBus → `GET /api/stream` SSE; `/api/bandit`, `/api/notifications`; admin activity feed | "Every heartbeat, surface, and feedback event streams live — stored for eval and GEPA." |
| Recursive Intelligence | NONE | GEPA panel in HTML is mock only | "Prompt RSI via GEPA in P7 — not weight training." |

**Strongest theme this phase:** Self-Improvement Stack (observability finally visible without MongoDB Compass)
**Weakest theme / judge risk:** Mock GEPA diff in admin UI could over-promise RSI; sidebar context still fake
**Verdict:** THEME-READY — primary + secondary tracks demo-able in browser
**Next (max 2):**
1. P7: real GEPA + `optimization_runs` to replace mock GEPA panel
2. P8: 30s pitch + live browser adaptation beat on stage

---

## Phase MCP — FastMCP Server — 2026-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PROVEN | `record_feedback` + `run_heartbeat` via MCP stdio | "Claude Code dismisses in chat → bandit β updates — same loop as the web inbox." |
| Self-Improvement Stack | PROVEN | MCP tools + existing EventBus/SSE/MongoDB stack | "Host transcript + persisted feedback_events — eval-ready from any MCP client." |
| Recursive Intelligence | NONE | — | "GEPA still P7; Kairos MCP is policy only." |

**Strongest theme this phase:** Continual Learning — feedback path now works in browser, CLI, **and** MCP hosts
**Weakest theme / judge risk:** Calendar context still stub unless Google Workspace Calendar MCP is configured separately
**Verdict:** THEME-READY — agent-native demo path unlocked; calendar is a **second MCP server** per PLAN.md
**Next (max 2):**
1. Configure Google Calendar MCP + agent prompt protocol
2. Rehearse Claude Code `/loop` with Kairos MCP

---

## Phase A.5 — Sensors + multi-user + gym — 2026-06-27

| Theme | Score | Proof artifact | Pitch line |
|-------|-------|----------------|------------|
| Continual Learning | PARTIAL | Persona gym (`kairos sim run`) drives the real bandit; `/api/metrics` engagement curve from `feedback_events`; per-user `bandit_params` | "Across 14 simulated days and 3 lifestyles, engagement climbs as the policy learns each persona's right moment." |
| Self-Improvement Stack | PARTIAL→PROVEN | `db/metrics.py` aggregation + `/api/metrics` curve; gym as eval harness; `db/vector_search.py` real $vectorSearch | "The gym is our evaluation harness — we replay synthetic lifestyles through the real policy and watch convergence." |
| Recursive Intelligence | NONE | — | "Still policy + (planned) prompt only; no weights. GEPA is the next loop." |

**Strongest theme this phase:** Self-Improvement Stack — the gym is genuine evaluation infrastructure, not a slide.
**Weakest theme / judge risk:** Continual Learning demo is **blocked live** by the `read_context` asyncio bug; curve is real but the single-user dismiss beat won't run until fixed. Recursive Intelligence still absent (GEPA unbuilt).
**Verdict:** THEME-GAP — primary theme (Continual Learning) regressed to non-demonstrable live despite strong infrastructure.
**Next (max 2):**
1. Fix heartbeat blocker so the live dismiss→learn beat runs
2. Build GEPA loop (`optimization_runs`) to give Recursive Intelligence an honest PARTIAL
