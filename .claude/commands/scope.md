---
description: Triage a task — should this be a tiny model at all? Produces experiment.yaml or a refusal.
---

Run the `task-triage` subagent on the following task. Work the ladder in the
`tiny-model-triage` skill from the bottom: deterministic, then classical, then
tiny model, then large-model API.

Task: $ARGUMENTS

Produce either:
1. A filled copy of `harness/templates/experiment.yaml` at `experiments/<slug>.yaml`, with a **named baseline and a measured number** — or, if the number can only be measured once the held-out split exists, `baseline.measured_at_runtime: true` and the name of the script that will measure it, or
2. A written refusal naming which rung of the ladder to use instead and why, or
3. One or more **open spike records** at `experiments/<slug>.spike.md`, from `harness/templates/spike.md`, each naming the contract field it will fill in `informs`. Write these instead of a contract carrying numbers nobody measured. Two or three cheap questions answered first is the difference between a contract and a wish list.

You have no Bash, so you write spike records and never run them. `/spike` runs them, and `python -m harness spikes` refuses one that is not a record yet. A contract that arrives with its uncertainties named as open spikes is a better first output than one that arrives complete and fictional.

Do not produce "it depends". Do not start any training.
