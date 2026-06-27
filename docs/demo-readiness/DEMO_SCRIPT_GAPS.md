# Demo Script Gaps

Checklist of what the **rehearsal script** needs vs what exists. Update after adversarial reviews.

## Must-have beats (hackathon)

| Beat | Status | Blocker |
|------|--------|---------|
| 30s pitch (interrupt policy, not search) | 📝 script needed | — |
| Show bookmark corpus (enriched) | ✅ | — |
| Show **topic clusters** | ✅ partial | 2 clusters; 41 noise — rehearse narrative |
| Show **silence** (KAIROS_OK) | ✅ | Gate-driven; dismiss can trigger OK |
| Show **surface** (cluster digest) | ✅ | `kairos heartbeat --delivery return_only` |
| User dismisses → policy adapts | ✅ | Browser dismiss → admin bandit panel + SSE; CLI fallback |
| Snooze → re-queue story | ✅ | Inbox snooze button → `POST /api/feedback` |
| Learning visible (diff or metrics) | ✅ partial | α/β in admin panel + `/api/bandit`; no chart; GEPA panel is mock |
| Web dashboard live | ✅ | `kairos serve` + SSE + inbox feedback |

## Nice-to-have (cut if behind)

- Full FastAPI dashboard + Chart.js
- Live X sync on stage
- GEPA nightly Cloud Routine
- OS notifications (terminal-notifier)
- MCP in Claude Code live
- `kairos ingest update` incremental orchestrator

## Known demo risks

1. **Digest latency** — 10–25s on heartbeat; rehearse with `DIGEST_USE_GOOGLE_SEARCH=false`
2. **Mock sidebar widgets** — context gap/clusters/sparkline hardcoded; hide or wire before judge
3. **Mock GEPA panel** — admin UI shows fake v3→v4 diff; say "P7" or hide section
4. **Dismiss doesn't always switch cluster** — show β increase in admin bandit panel
5. **Weak cluster story** — one 51-member mega-cluster; one-liner ready
6. **Context stub** — cafe/90min gap is demo persona; say so upfront
7. **X API auth** — token refresh fallback; MongoDB snapshot

## Rehearsal script (60s) — browser (preferred)

```bash
# Terminal 1
uv run kairos serve

# Terminal 2
DIGEST_USE_GOOGLE_SEARCH=false uv run kairos heartbeat
# → digest appears in browser inbox (SSE)

# Browser: click "Not relevant" → flip to admin mode
# → SSE feedback event + bandit β increase in panel

# Optional second tick
uv run kairos heartbeat
```

## Rehearsal script (60s) — CLI fallback

```bash
uv run kairos bookmarks clusters
DIGEST_USE_GOOGLE_SEARCH=false uv run kairos heartbeat --delivery return_only
uv run kairos feedback <notification_id> --action dismissed
uv run kairos heartbeat --delivery return_only
```

**Pitch line:** "Everyone embeds bookmarks. Kairos learns *when* to interrupt — and gets quieter when you dismiss at the wrong moment."

## P6 review actions (2026-06-27)

1. Commit P4+P5+P6 core work  
2. Hide or wire mock sidebar + GEPA panel before stage  
3. Write 30s pitch script (see `.cursor/skills/kairos-hackathon-themes/PITCH_SNIPPETS.md`)  
