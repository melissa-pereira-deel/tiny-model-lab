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
to prevent. If your measurement genuinely is 0.0, either declare
`baseline.higher_is_better: false` and keep the metric you have, or state it in
the direction where zero is not the answer: accuracy 1.0, not error 0.0.

**Don't leave the metric's direction to chance.** If `baseline.metric` reads
like something you minimise — loss, perplexity, WER, RMSE — `baseline_gate`
refuses the run until `baseline.higher_is_better` says which way it goes.
Every gate assumed higher-is-better and no CLI path could say otherwise, so a
model scoring *worse* than the baseline passed and was promoted, silently.
The check reads the metric's name rather than the metric, and says so; the
declaration is what tells it. Declaring `true` is a valid answer.

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

**Don't fill a contract field with a number nobody measured.** Write an open
`experiments/<slug>.spike.md` instead and answer it — `harness/spike.py`
refuses a record without a question, a threshold, a named consequence and a
budget of at most 480 minutes, and `python -m harness spikes` is what runs the
refusal. `informs:` is checked against the flattened keys of
`harness/templates/experiment.yaml` read at runtime, so the field you claim to
be measuring has to be a field the contract actually has. The 480-minute
ceiling is a judgement call and `harness/spike.py` says so in as many words —
unlike `LATENCY_BANDS_MS`, there is no literature behind it.

## Running

**Don't extend patience mid-run to rescue a plateau.** `patience_gate` stops
after N evals without *strict* improvement, and both `AGENTS.md` and
`.claude/agents/trainer.md` say the same thing: change something structural or
stop. A new seed is not a structural change. A new learning rate is barely one.
Changing the input representation is one, and it is usually the one that works.

**Do split by something meaningful.** `harness/templates/experiment.yaml` spells the
field as `split_by: repo | user | time | document — NOT random`. A random split
over correlated records measures memorisation and reports it as accuracy.
`validate.py` now enforces this, along with a positive `holdout_size`. If the
records really are independent and random is honest, say so — `split_by: random`
passes once `split_rationale` names the grouping unit that does not exist.
Note what the check cannot do: it reads the label, not the split. This rule was
added because `examples/01-hello-tiny` declared `split_by: "document"` for a
corpus of standalone generated strings and passed validation.

**Don't let a spike turn into a run.** A spike record is a measurement and
only a contract may authorise training. `.claude/hooks/guard-experiment.sh`
globs `experiments/*.yaml`, so `<slug>.spike.md` unlocks nothing, and
`tests/test_guard_hook.py::test_a_spike_record_does_not_unlock_training` is
what keeps that true rather than coincidental. From the other end, `load_run`
in `harness/experiment.py` raises without a `manifest.json`, so
`python -m harness gate` on a spike path exits 2. If the question needs an
eval loop, a second variant or a wallclock, it is an experiment: run `/scope`
and write the contract.

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
one honest record of what was ever actually best. If the reason you were reaching
for a hand-edit is that promotion would write into a clone you did not want to
change, `python -m harness ship --champion-dir DIR` moves the card and the ledger
together — that is the supported way out, and it is what
`examples/02-config-lexer` uses.

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
python -m harness validate examples/*/experiment.yaml
python examples/01-hello-tiny/run.py
ruff check .
pytest -q
```

All four run in CI (`.github/workflows/ci.yml`) on Python 3.10 and 3.14 — the
ends of the supported range — across Ubuntu and Windows. CI also parse-checks
the blank template, the one file that cannot be validated, because being
invalid is its job.
