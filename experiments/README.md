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

A measurement is a result too, and it is the third thing that lives here:
`<slug>.spike.md`, Markdown with YAML frontmatter, written by `/scope` or
`/spike` and checked by `python -m harness spikes`. A spike is the measurement
that gives a contract field its value — `informs:` names which one — or that
decides whether a contract should be written at all. It carries a threshold
written *before* the number exists, a named consequence if the answer is no, and
a time box of at most 480 minutes. These are committed for the same reason the
contracts are: the number in `budgets.max_size_kb` is worth more when the file
beside it says where the number came from.

Spike records are `.md` on purpose. The guard and CI both glob `*.yaml` in this
directory, so a spike unlocks neither training nor the build —
`tests/test_guard_hook.py::test_a_spike_record_does_not_unlock_training` pins
that, because a spike is a measurement and only a contract may authorise a run.
The record lives here; spike *code* does not, since the guard blocks scripts run
out of `experiments/` while no contract exists. Put it in `spikes/` or `tools/`.

The worked examples are deliberately not here. `examples/01-hello-tiny/` and
`examples/02-config-lexer/` each carry their own `experiment.yaml` next to their
runner, so each stays self-contained. The guard exempts 01 by path because CI
and the README's one-second promise both invoke it; 02 is not matched because
its entry point is `run.py`, not something with `train` in the name.
