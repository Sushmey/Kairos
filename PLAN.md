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

Kairos is a **contextual bandit**: at each candidate moment, score bookmarks for fit-to-this-moment, decide whether to interrupt at all, and update the policy on sparse implicit feedback. "Learns when depending on headspace" is the exact specification of a bandit policy improving over time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        INGEST LAYER                         │
│  X bookmark export → LLM enrichment → SQLite + embeddings   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      CONTEXT SENSOR                         │
│  Calendar (Google API) · Geofence · Time · Restraint budget │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     BANDIT POLICY                           │
│  Thompson sampling over feasible candidates → interrupt gate│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      DELIVERY LAYER                         │
│  Surface bookmark + "Why now" rationale · Capture feedback  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    SLEEP-TIME PASS (nightly)                │
│  Re-enrich · GEPA-tune prompts · Emit "what I learned" diff │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Bookmark Schema (enriched at ingest)

```python
{
  "id": str,
  "url": str,
  "raw_text": str,
  "embedding": list[float],          # sentence-transformers
  "topic_tags": list[str],
  "consumption_mode": str,           # read-deep | skim | watch | act-in-world | save-to-project
  "energy_cost": float,              # 0.0–1.0 (long ML thread = high, 2-min video = low)
  "geo_anchor": str | None,          # extracted place/product name if present
  "geo_coords": tuple | None,        # resolved lat/lon if geo_anchor
  "perishability": str,              # evergreen | dated | time-sensitive
  "created_at": datetime,
  "last_surfaced_at": datetime | None,
  "surface_count": int,
}
```

### Context Feature Vector (live at decision time)

```python
{
  "hour": int,                        # 0–23
  "day_of_week": int,                 # 0=Mon
  "is_weekend": bool,
  "calendar_gap_minutes": int,        # minutes until next event
  "meeting_density_today": float,     # meetings / 8h workday
  "minutes_since_last_meeting": int,
  "next_event_title_embedding": list[float],  # intent signal
  "location_type": str,               # desk | commute | gym | cafe | near_anchor | unknown
  "surfaces_today": int,              # restraint counter
  "time_since_last_surface_minutes": int,
}
```

### Feedback Event Schema

```python
{
  "bookmark_id": str,
  "context_snapshot": dict,           # context vector at time of surface
  "action": str,                      # opened | dwelled | saved | acted | snoozed | dismissed | ignored
  "snooze_duration_minutes": int | None,
  "timestamp": datetime,
  "reward": float,                    # computed from action (see Reward Function)
}
```

---

## Reward Function

| Action | Reward | Rationale |
|--------|--------|-----------|
| `acted` (went to place, added to todo) | +1.0 | Highest signal — passive → execution achieved |
| `dwelled` (opened + read >30s) | +0.7 | Strong engagement |
| `opened` | +0.3 | Weak positive |
| `saved` (copy to doc/note) | +0.6 | Signals utility |
| `snoozed` | 0.0 (re-queue) | Right thing, wrong time — re-surface with context stamp |
| `dismissed` | −0.3 | Wrong thing |
| `ignored` (surfaced, no interaction) | −0.5 | Worst: trained user to ignore |

**Snooze is the most valuable label.** A snooze says "relevant content, wrong context" — re-queuing with the context snapshot stamped on it is how the policy learns timing without explicit feedback.

---

## Bandit Policy

**Algorithm:** Thompson sampling over a logistic reward model per bookmark class.

Why not an LLM: sparse feedback (tens of events), not thousands. Thompson sampling converges in exactly this regime, stays interpretable, and the exploration half is critical — pure exploitation surfaces the same five bookmarks forever and never discovers the other 95% of the hoard.

**Feature join:** `[context_vector ‖ bookmark_features]` → logistic model → P(positive engagement)

**Interrupt gate:** Before surfacing, check:
1. `surfaces_today < daily_budget` (starts at 5, learned per user)
2. `calendar_gap_minutes > bookmark.energy_cost_minutes` (enough time to consume)
3. `time_since_last_surface_minutes > min_gap` (no spam)
4. Score exceeds exploration-adjusted threshold

If gate fails → silence. **Silence is the feature.**

---

## "Why Now" Rationale

Every surfacing includes one generated line exposing the policy decision:

> *"Dense read · 90-min gap · you usually absorb these Sunday morning at a coffee shop"*

Generated by an LLM prompt, tuned by GEPA on feedback signal. This doubles as UX (transparency) and demo evidence (learning happened — the rationale changes between sessions).

---

## Calendar Pull Mode

When a calendar event title semantically matches a bookmark cluster → proactively assemble a dossier before the event. No manual query needed.

Example: Event titled "Straiker interview prep" → surface the hoarded threads on AI security, MCP, prompt injection.

Implementation: on each calendar poll, embed event titles, cosine-search bookmark index, threshold at 0.7 similarity, bundle top-k into a pre-event digest.

---

## Geo-Anchoring

At ingest, extract place/product mentions from bookmark text (LLM). Resolve to coordinates. Geofence radius: 300m.

Trigger: user enters geofence AND calendar gap AND energy budget permit → surface the bookmark with "you're near [place]".

Demo simplification: a manual "I am here" location toggle rather than continuous background GPS (avoids OS permissions hell during hack).

---

## Sleep-Time Pass (Nightly)

1. **Re-enrich** bookmarks where `surface_count == 0` with updated context stats
2. **Update bandit** parameters from accumulated feedback log
3. **GEPA-tune** the enrichment prompt and rationale-generation prompt against the feedback-labeled eval set
4. **Emit a diff:** "here's how my model of your attention changed — added attribution extraction, updated coffee-shop context weight"

The diff is the closing demo slide. Watching the machine edit its own prompts is theater.

---

## Stack

| Component | Tool |
|-----------|------|
| Storage | SQLite (bookmarks, feedback) + DuckDB (metrics rollup) |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) |
| Bandit | `scikit-learn` logistic regression + Thompson sampling (custom, ~50 lines) |
| Prompt optimization | DSPy + GEPA |
| Calendar | Google Calendar API (OAuth2) |
| Bookmark ingest | X bookmark export CSV/JSON (not live API — see risk #1) |
| LLM calls | Claude claude-sonnet-4-6 via Anthropic SDK |
| Geo | `geopy` for geocoding, manual toggle for demo |

---

## X Bookmark Access — Risk #1 (De-risk First)

The X API bookmark endpoint requires OAuth2 user-context, is rate-limited, and pricing has been volatile. **Do not architect around the live API.**

Plan:
- Primary: ingest from X's data export (Settings → Your Account → Download an archive)
- Stretch: live sync via OAuth2 if quota allows
- Demo: use the export; judges will not care

**Verify current API state in hour 1 before any other decision.**

---

## Demo Strategy — No Real Feedback in 48h

Real continual learning takes weeks of data. A 48h demo with no feedback curve is a dead demo.

Solution:
1. Seed a **synthetic persona** with scripted preferences (e.g., "Rohit never reads long ML papers on back-to-back days, devours them Sunday at a cafe")
2. Simulate 2 weeks of feedback events against that persona
3. Show the engagement-rate curve climbing, dismissal/snooze rate falling
4. Do **one live adaptation on stage**: surface a bookmark in the "wrong" context, hit dismiss, watch the bandit update, surface a better one

Be explicit that real learning takes weeks; the simulator compresses it to 3 minutes. Judges respect this more than a fake-real demo.

---

## Build Order (Hackathon Sequencing)

### Hour 0–2: Foundation (non-negotiable first)
- [ ] Ingest X bookmark export → SQLite schema
- [ ] LLM enrichment pipeline (batch, async): topic, consumption_mode, energy_cost, geo_anchor, perishability
- [ ] Build the **eval harness** — a fixed set of context×bookmark pairs with ground-truth preferences from the synthetic persona. **Cannot demo learning without a yardstick. Build this before the bandit.**

### Hour 2–5: Context + Bandit
- [ ] Context sensor: Google Calendar poller, time features, restraint counter
- [ ] Thompson sampling bandit over logistic reward model
- [ ] Interrupt gate
- [ ] Feedback capture: opened / snoozed / dismissed / acted

### Hour 5–8: Delivery + Geo
- [ ] Surface endpoint with "Why now" rationale (LLM-generated)
- [ ] Geo-anchor extraction at ingest + geofence trigger
- [ ] Calendar pull mode (event title → bookmark dossier)

### Hour 8–12: Sleep-Time + GEPA
- [ ] Nightly consolidation: re-enrich, update bandit
- [ ] GEPA loop on rationale/enrichment prompts against feedback-labeled eval set
- [ ] "What I learned" diff generation

### Hour 12–24: Simulator + Demo
- [ ] Synthetic persona + feedback simulator
- [ ] Metrics rollup (DuckDB): engagement rate, dismissal rate, snooze→conversion rate per session
- [ ] Live accuracy chart (session-over-session)

### Hour 24–36: Polish + Edge Cases
- [ ] Restraint budget learning (per-user daily cap)
- [ ] Snooze re-queue with context stamp
- [ ] Demo script and stage choreography

### Hour 36–48: Buffer / Stretch
- [ ] Live X API sync (if time + quota)
- [ ] Real GPS geofence (if time + not an OS permissions nightmare)
- [ ] Additional bookmark sources (Pocket, Readwise export)

---

## Three Things to Do Before Anyone Else Starts

1. **Build the eval harness first.** You cannot demonstrate learning without a yardstick. Most teams realize this at hour 20. Self-generated evals from the corpus are also a self-improvement-stack flex in the pitch.

2. **Use snooze as your primary label.** "Right thing, wrong time" is the most informative signal for a timing model and the one every other team will miss. Implement snooze capture in hour 3, not hour 30.

3. **Make learning visible.** A session-to-session diff of what the system changed about itself — the prompt it rewrote, the context weight it shifted, the geo-anchor it learned — is worth more on stage than any accuracy number. Show the machine in the act of editing itself.

---

## Pitch Frame

> Most second brains are write-only graveyards. You bookmark 500 things and read 12. Kairos doesn't make you a better searcher — it becomes a better interrupter. It learns that you never read long ML threads on back-to-back days but devour them Sunday morning at a coffee shop. It learns that "not now" on a ramen rec means "remind me when I'm near Chinatown with an hour free." The policy improves every night on what it got wrong today, without you lifting a finger. Passive hoarding becomes execution.

---

## References

- GEPA (Agrawal et al., ICLR 2026 oral): https://arxiv.org/abs/2507.19457
- GEPA in DSPy: https://dspy.ai/api/optimizers/GEPA/overview/
- GEPA library: https://github.com/gepa-ai/gepa
- Contextual bandits / LinUCB (Li et al., WWW 2010): https://arxiv.org/abs/1003.0146
- Letta sleep-time compute (prior art to differentiate from): https://www.letta.com/blog/sleep-time-compute/
