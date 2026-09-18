---
name: tiny-model-triage
description: Decide whether a narrow task should be a tiny embedded model, classical ML, a deterministic rule, or a large-model API call. Use this whenever anyone proposes putting a model inside a product, mentions on-device or in-browser inference, says "we could train a small model for this", or asks whether an AI feature is worth building — even if they have already decided and just want help executing.
---

# Tiny-model triage

Most tasks that sound like tiny models are not. Work the ladder from the bottom.

## The ladder

Start at the bottom and stop at the first rung that works.

| Rung | Use when | Cost to try |
|---|---|---|
| Deterministic rule / parser / lookup | Output is fully specified by the input under known rules | minutes |
| Classical ML (logistic regression, trees) | Tabular or hand-featurisable, closed output space | minutes |
| Tiny neural model (KB–few MB) | Needs learned representation, closed output, cheap labels | days |
| Large model API | Open-ended generation, world knowledge, reasoning | minutes |

The ladder is asymmetric on purpose: rungs 1, 2, and 4 cost minutes to try. Rung 3 costs days. Earn it.

## The four legitimate reasons to go tiny

A tiny model has to win on a dimension the user can feel:

1. **Latency** — the network round-trip alone breaks the interaction. An API call cannot land under 100ms; local inference can.
2. **Privacy** — data cannot leave the device, so the feature is only shippable locally. Health, finance, journaling, unreleased work.
3. **Offline** — it has to work on a plane, a subway, a construction site, rural Goiás.
4. **Cost at frequency** — you want to run it continuously (every keystroke, every frame), which is only sane at ~zero marginal cost.

If none of the four apply, use an API. "More elegant" is not a reason.

## The baseline requirement

Every experiment names a specific existing thing it must beat. Not "improve accuracy" — a named tool with a measured number. If you cannot name one, the task is not scoped. This is the single highest-value constraint in this repo.

## Expected output

A filled `templates/experiment.yaml`, or a written refusal naming which rung of the ladder to use instead. Never "it depends".

## Worked contrast

**Good candidate** — highlighting code in a browser editor without shipping a grammar per language. Closed output space (token classes), free labels from an existing highlighter, wins on size and generality, needs to run per-keystroke. This is gpu-lexer, ~27.5KB.

**Bad candidate** — "summarise the user's document". Open-ended output, needs world knowledge, no closed label set, and a 2-second response is acceptable. Use an API, or a built-in browser model if privacy demands local.

**Trap** — "classify support tickets into 8 categories". Sounds like a tiny model. Is almost always logistic regression over embeddings, trains in seconds, ships as a matrix. Rung 2.
