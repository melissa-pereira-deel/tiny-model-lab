---
description: Run all gates on a run — technical plus interaction-design — and return promote / iterate / stop.
---

Run the `evaluator` subagent against: $ARGUMENTS

Start with `python -m harness gate $ARGUMENTS`. It reads the run manifest, runs
all five technical gates, and names the band the model actually landed in —
which is not necessarily the band the experiment declared. Do not re-implement
that loading by hand.

Report every gate result, including passes. Then run the five design checks from
the `design-eval` skill, which the CLI deliberately does not attempt: failure
state, uncertainty legibility, user override, privacy legibility, first-run
cost. Say what the landed band means for the interaction.

End with exactly one verdict: **promote**, **iterate** (naming the single
highest-leverage change), or **stop** (naming what was learned).
