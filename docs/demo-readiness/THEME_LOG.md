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
