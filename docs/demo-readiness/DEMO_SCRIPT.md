# Kairos Demo Script

3-minute narrative format. Three acts. Browser-first, CLI fallback.

---

## The story

**Persona:** Alex. Senior software engineer. 500 bookmarks saved over two years.  
Architectural patterns, ML papers, system design threads, startup war stories.  
Read: maybe 20 of them.

The problem isn't memory. It's timing.

---

## Act 1 — The graveyard (45s)

**Open:** user view, dashboard.

> "This is Alex's Kairos. Everything Alex has saved is here — clustered,
> enriched, ready. 99 bookmarks. Two years of intent."

Show the sidebar: Distributed Systems (51 bookmarks), AI/ML (14), startup threads.  
Point to engagement rate or history list — sparse.

> "The graveyard problem. Not forgetting — timing. Alex saves in one headspace,
> tries to retrieve in another. Kairos inverts this.
> Instead of Alex asking 'what did I save about X?'
> Kairos asks: *is this the right moment to surface it?*"

Key line to land:

> "Silence is the default. KAIROS_OK means: Alex is in a meeting, or
> in deep focus, or just came off a high-density morning. Not now."

---

## Act 2 — The right moment (90s)

**Context:** flip to admin view. Show the heartbeat tick.

> "Every 5 minutes, the policy evaluates. Gap in the calendar. Location.
> Meeting density. What Alex engaged with this week."

First tick: `KAIROS_OK`. Show the gate reasons panel.

> "Gate said no. 3 meetings this morning. Not now."

Simulate a gap opening (or narrate it):

> "2pm. Calendar clears. 42 minutes before the architecture review."

Run second heartbeat. `SURFACE`. Score `0.84`. Flip to user view — notification appears.

> "Distributed Systems. Why now: 'You have an architecture review in 42 minutes
> and haven't touched this cluster in 6 days.'"

Show the links — 3 bookmarks surfaced from the cluster.

**Demo person clicks "Not relevant"** (or snooze).

Flip to admin view. Point to the activity feed — `feedback: dismissed`.  
Bandit panel: β on Distributed Systems ticks up.

> "The policy just updated. That cluster's weight drops in this context class:
> dense-meeting day, pre-meeting window. Not forever — in this headspace."

Run a third heartbeat. Different cluster surfaces (or KAIROS_OK with new gate reason).

> "It learned. One interaction. Online update, no gradient steps on Gemini."

---

## Act 3 — The gym (45s)

> "One user, one interaction, isn't proof. So we built a simulation."

Pull up the engagement chart (or admin history with synthetic events seeded).

> "50 synthetic Alexes. Varied calendars. Different reading habits. Some snooze
> everything before noon. Some only engage on Fridays.
> 14 simulated days of interactions — 8,400 heartbeat decisions."

Show the curve: engagement rate climbing 45% → 74%.

> "The policy converged. And here's what's interesting — it converged faster
> for Alex than for Jordan, the founder with unpredictable meeting patterns.
> The gym told us *which users the policy can serve well*.
> That's an evaluation result, not just a demo prop."

Optional: show GEPA diff (if wired) or narrate:

> "The digest prompt also rewrote itself — the 'why now' line got sharper
> after the policy learned what dismiss patterns look like."

Close:

> "Everyone embeds bookmarks. Kairos learns when to interrupt —
> and gets quieter when you dismiss at the wrong moment.
> The gym is how we know it works before we deploy it."

---

## Mode guide for presenter

| Moment | View | Action |
|--------|------|--------|
| Opening — corpus story | User | Show sidebar clusters |
| Gate decisions | Admin | Run `kairos heartbeat` |
| Surface notification | User | Card appears via SSE |
| Dismiss / snooze | User | Click button |
| Bandit update | Admin | Point to β change |
| Gym curve | Admin | Engagement sparkline |

Toggle shortcut: **⬡ admin** / **◻ user** button top-right.

---

## Timing (strict)

| Act | Target | Max |
|-----|--------|-----|
| Act 1 — graveyard | 40s | 50s |
| Act 2 — right moment | 85s | 100s |
| Act 3 — gym | 40s | 50s |
| Buffer / Q&A hand-off | 15s | — |
| **Total** | **3:00** | **3:20** |

---

## If something breaks

| Failure | Recovery |
|---------|----------|
| Heartbeat slow (10–25s) | Say "Gemini generating the digest" — it's true. Run with `DIGEST_USE_GOOGLE_SEARCH=false` beforehand. |
| SSE notification doesn't appear | Refresh page; heartbeat result is cached — re-POST `/api/heartbeat` |
| Dashboard won't start | CLI fallback: `kairos bookmarks clusters` → `kairos heartbeat` → `kairos feedback` |
| Wrong cluster surfaces | Show the score anyway; the *mechanism* is the story, not the specific cluster |
| Bandit β doesn't visibly change | `/api/bandit` in browser, point to JSON — numbers don't lie |

---

## 30s pitch (elevator, non-demo context)

> "Everyone embeds bookmarks. Nobody reads them — because they saved them in
> one headspace and try to retrieve in another.
> Kairos is a contextual bandit that learns *when* to surface a topic cluster
> based on calendar gaps, location, and engagement history.
> Silence is the default. The policy updates from every snooze and dismiss.
> The longer you use it, the quieter it gets — until the moment is actually right."
