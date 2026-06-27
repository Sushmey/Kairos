# Kairos — Beyond the Hackathon

Talking points for "what's next?" questions. Ordered by impact, not difficulty.

---

## 1. Cross-user transfer: the persona prior

**The problem:** cold start. Every new user's bandit begins from uniform priors — the policy is useless for the first week.

**The direction:** with enough users, cohort patterns emerge. A "senior ML engineer at a startup" has similar attention patterns to other senior ML engineers at startups. Multi-task bandit: new users inherit priors from the nearest cohort. The synthetic gym personas we built for the demo become the pre-training archetypes — learned from real cohorts rather than scripted.

**What it unlocks:** first-session quality is already useful, not random. Onboarding improves without any additional user data collection.

---

## 2. Richer headspace signals

**Current context vector:** calendar gap, meeting density, location type, hour of day. Proxies.

**Real signals, unbounded by hackathon scope:**
- Communication burst after meetings — the 15-minute Slack/email processing window is the highest-information-density moment in a knowledge worker's day, fully observable from calendar + message metadata
- Tab count / context switching rate — attention fragmentation is directly measurable in a native app
- Wearables — HRV is a direct stress/recovery signal; step count signals location transitions
- Typing cadence — keystroke rhythm distinguishes deep focus from distracted browsing

**The architecture doesn't change.** The sensor layer does. More signals → richer context vector → the bandit's cluster×context features become more separable → faster convergence per user.

---

## 3. Information diet, not just bookmarks

X bookmarks are one channel. A knowledge worker's actual information diet:

- GitHub stars, Pocket/Instapaper saves, Notion pages, Slack saved messages
- Email newsletters (unread, starred)
- PDF papers in Zotero/Mendeley
- YouTube watch-later, podcast episodes

The bandit doesn't care about source — it cares about cluster×context fit. Unify ingest across sources and Kairos becomes a **personal knowledge operating system**, not a bookmark resurfacer. The surfacing policy is identical; the corpus is everything you've ever saved anywhere.

This also solves fragmentation: people save in six places and retrieve from none. Kairos becomes the single retrieval surface because it's the only one that knows *when* to surface something.

---

## 4. The interrupt policy as a platform

**Current scope:** bandit governs one decision — surface a bookmark cluster or stay silent.

**The generalization:** the same architecture governs any proactive AI action:
- PR review reminders at the right moment (not when CI passes, but when the engineer is in review headspace)
- Meeting prep assembly triggered by calendar signals
- Incident post-mortems nudged when the team has recovery time
- Learning resources surfaced when you hit a knowledge gap in a codebase you're exploring

Kairos becomes an **interrupt policy layer** that any agent can query. "Is now a good time to interrupt this user?" is a question every proactive AI system needs to answer. We have the only system that learns the answer per-user from behavioral signals.

---

## 5. The RL gym as a publishable benchmark

**Current role:** demo prop. Generates synthetic engagement events that seed the policy curve.

**The research artifact:**

> *SWE-Attention: A Gym for Evaluating Proactive AI Agents*

- Diverse synthetic personas with varied calendar patterns, topic affinities, engagement styles
- Reward functions grounded in attention research (context switching cost, post-meeting processing windows, cognitive load theory)
- Evaluation metric: policy performance across persona diversity, not just average engagement rate
- Ablation-ready: linear bandit vs. neural bandit vs. LLM-as-policy vs. cosine similarity baseline

A system that works for Alex but fails Jordan is not generalizable — the gym surfaces that. That's a workshop paper, a benchmark release, or both.

---

## 6. LLM as prior, bandit as likelihood

**The cold start problem has a cleaner solution than cohort priors alone.**

An LLM can generate a synthetic interaction history from a user profile:

> "Given that this user works in ML infrastructure, reads distributed systems papers,
> and has 40% of their bookmarks tagged 'systems', generate their predicted
> engagement distribution over these 8 clusters."

The LLM sets the prior. The bandit updates it with real behavioral evidence.  
This is principled Bayesian reasoning: prior from language understanding, likelihood from observation. Day-one quality is immediately useful. This framing is novel — most bandit deployments initialize with uniform priors or hand-tuned heuristics.

---

## 7. The policy as a transferable artifact

At scale, the *policy* itself is a user asset — not just the bookmarks, but the learned model of their attention:

- **Export:** attention policy is portable across devices and services
- **Share:** "use a senior SRE's reading habits as your onboarding template"
- **Fork:** inherit the team's collective policy and personalize from it
- **Audit:** "why did Kairos think 2pm on Tuesday was the right moment for this?"

The attention policy is more valuable than the content it gates. Content is abundant; knowing when someone is ready to receive it is rare.

---

## 8. Local-first / privacy mode

The entire pipeline can run locally:
- Local enrichment (Llama 3 / Gemma via Ollama)
- Local embeddings (already supported: `EMBEDDING_BACKEND=local`)
- Local MongoDB
- Local bandit parameters
- No attention data leaves the device

In a world where attention patterns are among the most sensitive behavioral data a person generates, local-first is a genuine differentiator — not just a checkbox.

---

## One-liner for the "what's next?" question

> "The hackathon proves the loop works. At scale, the question isn't whether
> a bandit can learn one user's habits — it's what a million users' worth of
> attention data tells you about human information processing,
> and whether you can use that to make day one for user one million
> as good as session 100 for user one."
