# Do's and don'ts

Every item here points at a specific rule in this repo. If a line does not name
a file, it does not belong on this page.

## The gate

**Don't weaken the baseline comparison to make a result look better.**
`baseline_gate` in `harness/gates.py` uses a strict `>`. That is not a rounding
preference. A tie means the baseline ships, and the baseline ships *without a
training pipeline, without weights to download, and without silent failure
modes* — three liabilities the model brings whether or not it matches on the
metric. Equal accuracy is therefore not equal value, so equal accuracy loses.
The same strictness appears again in `evaluate_promotion` in
`harness/promote.py`: a run that ties the current champion does not replace it.

**Don't relax a gate to unblock a run.** When a gate fails it returns a
`remediation` string written to be read and followed. `baseline_gate`'s
remediation is explicit that hyperparameter tuning is the *wrong* first move —
it names the order: improve the input representation, hand-check twenty
disagreements for label quality, then write it up as a negative result. The
remediation exists because the improvisation was already tried.

**Do treat a losing run as a finished result.** `examples/01-hello-tiny/run.py`
ends with the baseline winning and exits 0. That is the example, not a caveat
to it.

## Scoping

**Don't skip `/scope`.** `.claude/hooks/guard-experiment.sh` is a `PreToolUse`
hook that refuses a training command while `experiments/` holds no `*.yaml`.
The refusal is the feature: it makes "let me just try something quickly" cost an
explicit, visible decision. `tests/test_guard_hook.py` holds it to that.

**Don't write `baseline.value: 0.0` and move on.** `harness/validate.py` rejects
it by name: *"measure the baseline before training the model, otherwise the
comparison is decoration."* If a runner measures it — the way
`examples/01-hello-tiny/run.py` assigns `exp.baseline.value` before `start_run()`
— say so with `baseline.measured_at_runtime: true`.

**Don't treat `measured_at_runtime` as a way out.** It is a declaration that the
number arrives later, not permission to skip it. `baseline_gate` in
`harness/gates.py` refuses any run whose baseline still reads 0.0 when the gates
run, before it computes the comparison at all — because a 0.0 baseline is one
every candidate "beats", which is precisely the false result this harness exists
to prevent. If your measurement genuinely is 0.0, state the metric in the
direction where it isn't: accuracy 1.0, not error 0.0.

**Don't look for a `kind: none` baseline.** `Baseline.VALID_KINDS` in
`harness/experiment.py` allows `deterministic`, `classical`, `existing_tool`,
and `previous_run`. There is deliberately no fifth option. If you cannot name
something simpler that already does the job, the task is not scoped yet.

**Don't leave `kill_criteria` empty.** `harness/validate.py` fails the file.
Gates stop a run; kill criteria end a project, and they have to be written
before you are invested — which is the only time writing them is uncomfortable
and therefore the only time it works.

**Don't submit a one-word hypothesis.** `validate.py` requires at least five
words, on the grounds that a hypothesis you cannot falsify is not one.

## Running

**Don't extend patience mid-run to rescue a plateau.** `patience_gate` stops
after N evals without *strict* improvement, and both `AGENTS.md` and
`.claude/agents/trainer.md` say the same thing: change something structural or
stop. A new seed is not a structural change. A new learning rate is barely one.
Changing the input representation is one, and it is usually the one that works.

**Do split by something meaningful.** `harness/templates/experiment.yaml` spells the
field as `split_by: repo | user | time | document — NOT random`. A random split
over correlated records measures memorisation and reports it as accuracy.

**Don't report agreement with a teacher as correctness.** `CONTRIBUTING.md`
calls this out as the most common dishonesty in the field. If your labels come
from a parser or a large model, your metric measures agreement with that tool,
including where it is wrong. Say which one you mean.

## Measuring

**Do report p95 warm, with cold start stated separately.** `latency_ms` in
`harness/profile.py` returns `cold_ms` alongside `p95_ms` for exactly this
reason, and `latency_gate` checks the p95. Mean latency hides the tail users
actually feel; cold start is a different UX problem with different fixes
(preload, warm-up, skeleton).

**Do measure the artifact on disk, not the parameter count.** `artifact_size_kb`
in `harness/profile.py` sums a directory tree so that a `.mlpackage` or a split
ONNX model reports what it really costs. Users download bytes.

**Don't treat the latency bands as tunable.** `LATENCY_BANDS_MS` in
`harness/experiment.py` carries a comment explaining why it lives in code rather
than config: 100 ms / 1 s / 10 s are perceptual facts about humans, not
engineering targets you get to negotiate.

## Shipping

**Don't hand-edit `champion/`.** `AGENTS.md` states that it changes only via
`harness/promote.py`, and `promote()` is the only thing that writes
`champion.json` and appends to `runs/LEDGER.md`. Editing around it costs you the
one honest record of what was ever actually best.

**Don't commit artifacts.** `.gitignore` excludes checkpoints, corpora, and
exported weights while explicitly keeping `manifest.json`, `LEDGER.md`, and
`SESSIONS.md`. The convention in `AGENTS.md` is one line: provenance is
committed, artifacts are not.

**Don't pick MLX for a browser target.** `AGENTS.md`, the README, and
`.claude/agents/trainer.md` agree: MLX has no first-class converter to ONNX or
Core ML, so choosing it for a cross-platform target strands you at export. Pick
the export path before the training framework.

**Don't plan to serve from MPS.** Training tiny models on MPS is fine. Serving
from it is not — `AGENTS.md`, stack defaults.

## Before a pull request

```bash
pytest -q
ruff check .
python examples/01-hello-tiny/run.py
```

All three run in CI (`.github/workflows/ci.yml`) on Python 3.10 and 3.12, which
also checks that every experiment file still parses.
