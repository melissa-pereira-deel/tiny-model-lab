---
description: Run all gates on a run — technical plus interaction-design — and return promote / iterate / stop.
---

Run the `evaluator` subagent against: $ARGUMENTS

Report every gate result, including passes. Then run the five design checks from
the `design-eval` skill: failure state, uncertainty legibility, user override,
privacy legibility, first-run cost. Name which latency band the model landed in
and what that means for the interaction.

End with exactly one verdict: **promote**, **iterate** (naming the single
highest-leverage change), or **stop** (naming what was learned).
