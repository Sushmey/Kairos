# Demo Script Gaps

Checklist of what the **rehearsal script** needs vs what exists. Update after adversarial reviews.

## Must-have beats (hackathon)

| Beat | Status | Blocker |
|------|--------|---------|
| 30s pitch (interrupt policy, not search) | 📝 script needed | — |
| Show bookmark corpus (enriched) | ✅ | — |
| Show **topic clusters** | ✅ partial | 2 clusters; 41 noise — rehearse narrative |
| Show **silence** (KAIROS_OK) | ✅ partial | Heartbeat returns OK but gate reasons hardcoded |
| Show **surface** (cluster digest) | ❌ | `ranking.py` stub — no cluster pick |
| User dismisses → policy adapts | ❌ | bandit update stub |
| Snooze → re-queue story | ❌ | snooze context stamp |
| Learning visible (diff or metrics) | ❌ | GEPA or bandit dashboard |

## Nice-to-have (cut if behind)

- Full FastAPI dashboard + Chart.js
- Live X sync on stage
- GEPA nightly Cloud Routine
- OS notifications (terminal-notifier)
- MCP in Claude Code live
- `kairos ingest update` incremental orchestrator

## Known demo risks

1. **Empty policy** — clusters exist but heartbeat can't surface them (P4)
2. **CLI-heavy** — lead with `bookmarks clusters` + heartbeat, not OAuth tour
3. **Over-explaining embeddings** — judge cares about *when*, not Gemini vs BGE
4. **Weak cluster story** — one 51-member mega-cluster; prepare one-liner ("dense dev-tools topic")
5. **X API auth** — rehearse token refresh; have MongoDB snapshot fallback

## Rehearsal fallback

If live heartbeat fails: pre-record terminal showing:
1. `kairos bookmarks clusters` (2 clusters)
2. MongoDB cluster doc with centroid + member_count
3. Planned `feedback_events` update showing α/β change (once P5 wired)

## P3 review actions (2025-06-27)

1. Wire `ranking.py` → prove one `SURFACE` heartbeat  
2. Demo-script the 51-member cluster as primary digest candidate  
3. Defer incremental ingest CLI until after P4  
