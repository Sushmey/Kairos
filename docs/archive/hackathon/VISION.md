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

**Scaling the gym with PufferLib (when the policy outgrows the bandit).** Today's gym (`sim/`) runs the *real* ranking pipeline against MongoDB — correct, but slow, and deliberately matched to a bandit that converges in 20–100 observations. It is the wrong shape for deep RL. If we ever want to train a *neural* interrupt policy across many personas, the move is to reimplement the persona dynamics as a fast, pure-compute environment (no Mongo, no LLM in the hot loop) and host it in **[PufferLib](https://puffer.ai)** — high-throughput vectorized envs + PPO at millions of steps/sec. That buys the bridge from "bandit on sparse *real* feedback" to "policy *pretrained in simulation*, fine-tuned online" (ties to §6, LLM-as-prior). Honest caveat: PufferLib's value assumes a compute-bound simulator, so adopting it means *rebuilding* the gym divorced from the live pipeline — a real project, and pure scope creep for the bandit-first hackathon. It belongs here in the vision, not the build plan.

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

## 9. Standards & BYO observability — two telemetry planes

Kairos emits two kinds of signal, and they want different treatment:

- **Policy plane** — `should_surface`, `gate_reasons`, `adjusted_score`, bandit `α/β` posteriors, `context_class`, `derived_reward`. This is the differentiated IP. **No OTEL/OpenInference vocabulary exists for "interrupt decision" or "bandit posterior,"** so it stays a domain schema (`feedback_events`, EventBus events). A generic APM dashboard pointed at this would render token counts and drop the decisions into untyped attributes — worse than the bespoke admin view.
- **LLM / agent plane** — enrichment, digest generation, and the Antigravity tool-calling harness. This *is* standardizable. OpenInference (`openinference-instrumentation-google-genai`) and the OTEL GenAI conventions are the right vocabulary here.

The two planes are joined by a **correlation id** (`decision_id`) threaded heartbeat → ranking → LLM call → notification → feedback. The join is what answers "how is the agent behaving in conjunction with the policy" — *this digest that got dismissed; what prompt, inputs, grounding, and latency produced it?* The same join is the GEPA training tuple: `(prompt_version, inputs, output) ⨝ (reward)`.

**Why we don't adopt OTEL as the primary layer:** the EventBus is the decoupling seam, so an OTLP/OpenInference exporter for the LLM plane is an *additive fan-out consumer* — a ~1-day add the day an enterprise wants "bring your own observability stack," not a re-architecture. We keep the opinionated app posture now (our admin view is the differentiator) and expose the standards-compliant LLM-plane export as a roadmap item. The policy schema GEPA and the bandit depend on stays primary either way.

```
pipeline ──▶ EventBus ──┬──▶ SSE → admin dashboard          (today)
                        ├──▶ OTLP/OpenInference → Phoenix…   (BYO, later)
                        └──▶ webhook → customer sink         (later)
```

## 10. The self-improvement loop is self-contained — build, don't buy

The automated observability → eval → optimization loop needs **no SaaS integrations**. Every stage is already in-house: EventBus + agent hooks (tracing), MongoDB (trace/dataset store), the admin dashboard (metrics), `rewards.py` + the gym personas (eval scoring), Claude Code `/loop` or Cloud Routine (scheduling). The only genuine dependency delta is the **optimizer**: either `dspy` (ships `dspy.GEPA`, lets us cite the ICLR 2026 paper, heavier install) or a hand-rolled ~80-line reflective loop driven by the Gemini client we already have (zero new deps, keeps the "we built the whole stack" story pure). Put `core/optimize.py` behind a thin interface so the two are interchangeable. Declining Langfuse/LangSmith/Phoenix/Braintrust is deliberate — they'd duplicate the layer that *is* our demo and dilute the pitch into "we configured someone's SDK."

---

## One-liner for the "what's next?" question

> "The hackathon proves the loop works. At scale, the question isn't whether
> a bandit can learn one user's habits — it's what a million users' worth of
> attention data tells you about human information processing,
> and whether you can use that to make day one for user one million
> as good as session 100 for user one."
