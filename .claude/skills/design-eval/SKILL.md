---
name: design-eval
description: Evaluate an embedded model as an interaction, not just as a metric — latency bands, failure states, uncertainty legibility, user override, and privacy legibility. Use before shipping any model-backed feature, when reviewing a prototype that uses inference, or whenever someone reports accuracy numbers as if they settle whether a feature is ready.
---

# Design evaluation for embedded models

Accuracy tells you whether the model is right. This tells you whether the feature is good. A model can pass every technical gate and still be the wrong thing to ship.

## Latency bands

From Miller (1968) and Nielsen (1993). These are facts about human perception, not targets you can negotiate.

| Band | Ceiling | What it buys you |
|---|---|---|
| Instant | 100 ms | Feels like direct manipulation. No spinner, no feedback, no acknowledgement needed. |
| Flow | 1 s | Thought stays unbroken. No feedback needed, but the seam is felt. |
| Attention | 10 s | Attention holds only with visible progress. Design the wait. |

**This is the whole argument for on-device inference.** A network round-trip cannot reach the instant band. Local inference can. If your tiny model lands at 400ms, you have not built an instant interaction — you have built a flow-band interaction with extra steps, and you should either fix the latency or design the feedback.

Measure p95 warm, and report cold start separately. The first interaction is what the user judges you on.

## The five checks

1. **Failure state.** Every tiny model is wrong sometimes. What does wrong look like on screen? Degrade gracefully — a missed highlight is fine, a mangled document is not. If there is no designed wrong-state, the feature is unfinished.
2. **Uncertainty legibility.** If confidence varies and the UI renders everything with identical authority, the interface is lying to the user. Either surface the uncertainty or suppress low-confidence output entirely.
3. **User override.** Correction, dismissal, or opt-out. A wrong output the user cannot escape is worse than no output at all.
4. **Privacy legibility.** If nothing leaves the device, say so where the user can see it. This is the strongest thing local inference buys and it is completely invisible unless you show it.
5. **First-run cost.** Model download, warm-up, permission prompts. Design this moment — it is the only one every user experiences.

## Provenance

These consolidate Google PAIR's People + AI Guidebook, Apple's Human Interface Guidelines for machine learning, and Amershi et al., "Guidelines for Human-AI Interaction" (CHI 2019) — the most-cited practitioner framework, validated across 20 AI-infused products.

All three presuppose that the feature should exist. That question belongs to `tiny-model-triage`, which runs first.
