# experiments/

One YAML per scoped task. `/scope` writes them here from
`templates/experiment.yaml`; `.claude/hooks/guard-experiment.sh` refuses to run
a training script while this directory holds no `*.yaml`.

These files are **committed**. They are the contract — the named baseline, its
measured number (or `measured_at_runtime: true`, a promise that a runner supplies
it and that the baseline gate enforces), the budgets, and the kill criteria you
wrote down before you were invested. Corpora and checkpoints stay gitignored; the
reasoning does not.

A refusal is also a result. If `/scope` decides the task belongs on a lower rung
of the ladder, write that down here too — a short `<slug>-refused.md` naming the
rung and why — so the next person does not re-derive it.

The worked example is deliberately not here: `examples/01-hello-tiny/` carries
its own `experiment.yaml` next to its runner, so the example stays
self-contained and the guard exempts it by path.
