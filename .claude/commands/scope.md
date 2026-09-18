---
description: Triage a task — should this be a tiny model at all? Produces experiment.yaml or a refusal.
---

Run the `task-triage` subagent on the following task. Work the ladder in the
`tiny-model-triage` skill from the bottom: deterministic, then classical, then
tiny model, then large-model API.

Task: $ARGUMENTS

Produce either:
1. A filled copy of `harness/templates/experiment.yaml` at `experiments/<slug>.yaml`, with a **named baseline and a measured number** — or, if the number can only be measured once the held-out split exists, `baseline.measured_at_runtime: true` and the name of the script that will measure it, or
2. A written refusal naming which rung of the ladder to use instead and why.

Do not produce "it depends". Do not start any training.
