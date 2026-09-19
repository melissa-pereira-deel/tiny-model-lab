# experiments/

One YAML per scoped task. `/scope` writes them here from
`harness/templates/experiment.yaml`; `.claude/hooks/guard-experiment.sh` refuses to run
a training script while this directory holds no `*.yaml`.

These files are **committed**. They are the contract — the named baseline, its
measured number (or `measured_at_runtime: true`, a promise that a runner supplies
it and that the baseline gate enforces), the budgets, and the kill criteria you
wrote down before you were invested. Corpora and checkpoints stay gitignored; the
reasoning does not.

A refusal is also a result. If `/scope` decides the task belongs on a lower rung
of the ladder, write that down here too — a short `<slug>-refused.md` naming the
rung and why — so the next person does not re-derive it.

The worked examples are deliberately not here. `examples/01-hello-tiny/` and
`examples/02-config-lexer/` each carry their own `experiment.yaml` next to their
runner, so each stays self-contained. The guard exempts 01 by path because CI
and the README's one-second promise both invoke it; 02 is not matched because
its entry point is `run.py`, not something with `train` in the name.
