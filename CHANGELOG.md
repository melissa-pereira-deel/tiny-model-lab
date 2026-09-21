# Changelog

Notable changes to this project, in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
format, following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**One deliberate deviation: `Gate semantics` is a category of its own**, listed
first. Most of what changes here is not a feature but a rule — a gate's
arithmetic, a validator's requirement, the guard's match patterns. A gate that
gets stricter invalidates a run that *passed* yesterday, which is a different
kind of breakage from "Changed" and the one worth finding fastest. It is only
ever used for changes to what a gate accepts or rejects; rewording a gate's
remediation is a `Changed`.

## [Unreleased]

### Gate semantics

- `baseline_gate` refuses a run whose baseline is declared
  `measured_at_runtime` and is still `0.0`, instead of comparing against the
  zero. Previously a baseline that never arrived was compared as a real number,
  so every positive candidate "beat" it — the exact comparison this harness
  exists to prevent. Strictly stricter: a run that passed can now fail.
- `baseline_gate` refuses a run whose `baseline.metric` reads like something
  you minimise — loss, perplexity, WER, RMSE — when `baseline.higher_is_better`
  is unset, instead of assuming higher. Previously every gate assumed higher
  and **no CLI path could say otherwise**: `gate_run` did not accept the
  parameter and `cmd_ship` never passed it, so `python -m harness gate` and
  `python -m harness ship` compared backwards for any loss. A model scoring
  worse than the baseline passed, printed `PASS`, and promoted; `patience_gate`
  read a rising loss as improvement; and each promotion installed an incumbent
  worse than the last. Strictly stricter, and #23.

  Unlike the entry above, **this invalidates nothing in this repo.** Both
  examples, the template and every local manifest use `accuracy`, which is
  unaffected. The runs it would have caught are ones nobody here has written.

- `promote()` measures the artifact and runs the size gate on **the bytes it is
  about to copy**, instead of on `size_kb` from the manifest. It also refuses an
  artifact measuring 0.0 KB, and one it cannot read. Previously nothing between
  the runner writing that number and the gate reading it ever looked at a file:
  `record_eval` validates nothing, `load_run` checks the key is present rather
  than true, and `cmd_ship` checked only `artifact.exists()`. So a run could
  gate on a self-reported 1 KB, print `PASS`, and promote a 4 MB file, with the
  champion card recording 1 KB. Strictly stricter, and #24.

  **This one does invalidate something in-tree.**
  `examples/02-config-lexer/run.py` gates the int8 eval (4985 bytes) and then
  hands `promote()` the fp32 `best_path` (8641 bytes) — the card would have
  reported the first file's number for the second file's bytes. It is latent
  there only because the baseline wins and promotion never runs, but it is the
  defect, in the one example that measures everything else correctly.

  No tolerance was added, deliberately. Refusing when the claimed and measured
  numbers merely *disagree* needs a threshold nobody has measured, and an
  unmeasured constant is what spike records exist to prevent. The budget is the
  only number here anyone argued for, so the budget is the only thing that
  refuses: 4 MB fails because it is over 50 KB, not because the manifest said
  something else. A discrepancy that still fits the budget promotes, with both
  numbers on the report and in the card.

  `python -m harness gate` is unchanged and still cannot check this. It takes a
  run directory and no artifact, on purpose — it runs every loop during
  training, when the export usually does not exist. Ship is the first moment
  the bytes are real. The gate now says so in its own output rather than
  printing `artifact 1.0 KB` about a file it never opened.

### Added

- The spike — `harness/spike.py` and `harness/templates/spike.md`. A spike is
  the measurement that gives a contract field its value, or that decides
  whether a contract should be written at all; the record is
  `experiments/<slug>.spike.md`, committed beside the contracts and the
  refusals. `informs` is checked against the flattened keys of
  `harness/templates/experiment.yaml` read at runtime, plus the literal
  `scope`, so the kinds of spike come from the contract rather than from a
  list somebody has to keep in step with it. `budget_minutes` is capped at 480
  — one working day, a judgement call and documented as one, unlike
  `LATENCY_BANDS_MS`. Its output is a finding, never a run: there is no
  `run_id` in the record and `gate` on a spike path exits 2.
- `python -m harness spikes [directory]` — lists a project's spike records and
  refuses the ones that are not yet one. Exit 1 on any problem, 0 with "no
  spike records" when there are none, which is this repo's own answer. It
  takes a directory rather than a path because the question it answers is
  what is still open, and no single record answers that. Deliberately not in
  CI or the pre-PR block: vacuous here, and a project using the harness is
  where it earns a place.
- `/spike <question or path>` — the sixth command, and the only one that does
  not delegate to a subagent. Isolated context exists to keep training logs
  out of the conversation; a spike's output is one sentence and one number, so
  there is nothing to isolate. It writes the record before measuring, stops at
  `budget_minutes`, never calls `start_run()`, and hands back to `/scope` when
  a question turns out to be an experiment.
- `/data <experiment-path>`, delegating to `data-builder`. It was the only
  subagent without a command, despite being step 2 of five in `AGENTS.md` — so
  the one step on the main path you had to know to invoke by name. Commands and
  subagents are 1:1 now, and `tests/test_agent_surface.py` keeps them that way.
- `python -m harness` — `init`, `validate`, `gate` and `ship` subcommands, plus
  a `tml` console script. `/gate` and `/ship` previously had no entry point, so
  every invocation re-improvised its own manifest loading.
- `ship` takes `--champion-dir DIR` and `--ledger PATH`. `--champion-dir` moves
  both the card and the ledger, so promotion can be tried without leaving files
  in a clone.
- `harness init` scaffolds `experiments/` and `runs/` and copies the blank
  experiment template into a new project.
- `validate` accepts several paths, so `examples/*/experiment.yaml` works.
- `gate_run()`, `band_landed_in()`, `load_run()`, `eval_history()` and
  `Experiment.from_dict()` in the library — one owner for reading a run back.
- `examples/02-config-lexer` — trains in PyTorch, exports to ONNX, verifies the
  conversion numerically, quantizes to int8 and gates on bytes on disk. The
  baseline wins.
- `docs/dos-and-donts.md` and `docs/prompting-guide.md`.
- Issue templates for bugs and negative results, and `.github/dependabot.yml`
  watching the GitHub Actions used by CI.

### Changed

- The places that already demanded a measurement now say where it goes.
  `/scope` and `task-triage` gain a third output: open spike records naming
  the fields they will fill, instead of a contract carrying numbers nobody
  measured — triage has no Bash, so it writes them and `/spike` runs them.
  The 20-example label audit, stated in imperative voice in
  `.claude/commands/data.md`, `.claude/agents/data-builder.md` and
  `.claude/skills/dataset-synthesis/SKILL.md`, becomes
  `experiments/<slug>-label-audit.spike.md` with `informs: dataset.teacher` —
  **the same sentence in all three**, because three copies of one rule
  drifting apart is the failure #14 was about. `experiments/README.md`
  describes the third file type that lives there, and the bug-report template
  lists `/spike`.
- `.claude/hooks/guard-experiment.sh` says what it does about spikes. **The
  match patterns are unchanged and no gate got stricter** — the guard globs
  `experiments/*.yaml`, a spike record is `<slug>.spike.md`, and the two have
  never met. What was missing was anything saying that on purpose, so
  `tests/test_guard_hook.py` gained a `spiked_project` fixture proving a spike
  record does not unlock training, and two entries pinning that spike code
  runs free while a spike script named `*train*.py` still does not.
- `validate` now checks the dataset: a `dataset` block must be present,
  `split_by` must name the unit generalisation has to cross, and `holdout_size`
  must be positive. A `split_by` naming a random split needs a written
  `split_rationale`. **Experiment files that validated before can now fail** —
  `examples/01-hello-tiny` was one of them.
- Runs, `champion/` and the ledger resolve from the working directory (or
  `TINY_MODEL_LAB_ROOT`) rather than from the installed package. Under a real
  `pip install` the old behaviour wrote run history into `site-packages`, so the
  only usable adoption model was living inside a clone.
- `Baseline` gained `measured_at_runtime`, and `validate` accepts a `0.0`
  baseline only when it is set. See Gate semantics above for the other half.
- `Baseline` gained `higher_is_better: bool | None`, and `validate` refuses a
  loss-shaped `metric` with it unset. See Gate semantics above for the other
  half.

  `None` — nobody said — is the default and resolves to higher, so every
  existing contract and manifest behaves exactly as before. The three-valued
  type is what gives the refusal an escape: a plain `bool` cannot tell "I mean
  higher" from "I did not think about it", and a refusal with no escape would
  be this validator's first.

  The direction lives in the contract rather than in a CLI flag so that a
  manifest can still be re-gated correctly a year later. The gates each read
  it off the experiment they already receive, which is why `gate_run`,
  `cmd_gate` and `cmd_ship` needed no change at all. `baseline_gate`,
  `patience_gate`, `run_all`, `evaluate_promotion` and `promote` keep their
  `higher_is_better` parameter as an override; it now defaults to `None`,
  meaning *ask the contract*.
- The champion card gains `size_kb_reported` beside `size_kb`. `size_kb` is now
  the measured number and describes the bytes in `champion/`; `size_kb_reported`
  is what the run claimed. Both are written every time rather than only on a
  mismatch — a field that appears conditionally is one a reader can conclude
  nothing from when it is absent, and the pair is the evidence the check ran.
  The ledger line already formatted `card['size_kb']`, so it became true
  without an edit.

  `evaluate_promotion` gains a keyword-only `artifact: Path | None = None`.
  `None` answers from the manifest alone, which is how you ask "would this
  promote?" before an export exists, and it is what keeps every existing caller
  working. It is not a way around the check: `promote()` always passes the
  artifact and `cmd_ship` always goes through `promote()`.

- `examples/01-hello-tiny` writes its lookup table to `runs/<id>/artifacts/` and
  measures it, instead of reporting `len(table) * 2 / 1024` for a file that did
  not exist. The estimate was labelled as one and still wrong in the way that
  matters — this is the example people copy, so it was the in-tree precedent
  for "whatever the runner says". The reported size moves from 0.1 KB to 0.7 KB
  against a 5 KB budget; the size gate still passes and the example's point,
  that the baseline wins, is unchanged.

- `baseline_gate`'s zero-baseline remediation, and its paraphrase in
  `docs/dos-and-donts.md`, now offer `higher_is_better: false` alongside the
  older advice to restate the metric in the direction where zero is not the
  answer. Both changed together, because one rule living in two files is how
  they drift.
- The size gate's remediation tries post-training quantization at int8 before
  quantization-aware training, matching the `quantization-strategy` skill, and
  names the declared target rather than a fixed ladder of bit widths. Text only;
  the pass/fail arithmetic is unchanged.
- Packaging modernised: PEP 639 license metadata, `dynamic` version read from
  `harness.__version__`, an explicit ruff rule set and a `ruff>=0.16` floor.
- CI runs on `actions/checkout@v7` and `actions/setup-python@v7`, off the
  deprecated Node 20 runtime, and now on Windows as well as Ubuntu. The claim
  that the harness core has no OS-specific code had one OS of evidence behind
  it. The hooks are bash, so their tests skip on Windows deliberately.
- The CI matrix tests **3.10 and 3.14** — the ends of the supported range —
  rather than 3.10 and 3.12. `requires-python` stays at `>=3.10` past that
  version's end of life: nothing here uses 3.11+ syntax and Ubuntu 22.04 LTS
  ships 3.10 with security maintenance to May 2027. The untested end turned out
  to be the new one, since 3.14 is what this repo is developed on. The policy
  is written down in `CONTRIBUTING.md` so it is not re-argued every October.
- `pyproject.toml` declares per-version classifiers. `Python :: 3` alone was
  honest and useless.

### Fixed

- The sibling-project link called `On-Device ML Optimization` a *lens*. That
  repo draws a line between thinking lenses, for deciding what to build, and
  engineering skills, for building it well — and it is one of the latter. The
  link now names the category correctly, and counts nothing: a number in this
  repo about another repo's inventory has no sensor behind it, and theirs had
  already drifted. It also names the second, stronger seam:
  `Performance as Experience` draws the same 100 ms boundary as
  `LATENCY_BANDS_MS`, from the same literature, while binning the rest
  differently.
- Gate output was not printable on a default Windows console. `GateResult`
  returned a U+2192 arrow, which is not in cp1252, so printing a failed gate
  raised `UnicodeEncodeError` — `examples/01-hello-tiny` died before its first
  gate. `gates.py` returns ASCII now: a library must not hand its caller a
  string the caller cannot print. The em dashes went too, since cp932, koi8-r
  and ascii all reject them. **01's transcript changed**: `→` is `->` and `—`
  is `--`.
- The CLI and both examples now declare UTF-8 output instead of inheriting the
  locale encoding, so the em dashes in their own prose survive as well.
- Both hooks hardcoded `python3`, which Git Bash on Windows generally does not
  have. The guard swallowed the failure and matched an empty command, so it
  failed **open** — silently not guarding on the one platform where it is most
  likely to be missing. It now falls back to `python`, and with no interpreter
  at all matches the raw hook payload rather than nothing.
- The `SessionEnd` hook appended unconditionally and ignored its payload, so one
  working session left ten entries in `runs/SESSIONS.md` inside four seconds,
  identical apart from the timestamp. It now names the session, the end reason
  and the most recent run — the fields that actually distinguish entries — and
  skips a write that says nothing new. Why it fires repeatedly is still unknown;
  recording `session_id` and `reason` is what makes the next time diagnosable.
- The `PreToolUse` guard matched paths where training never happens, and fired
  on prose — a commit message mentioning `python` and `train` was enough to
  block it. A guard that fires on prose gets switched off.
- `evaluate_promotion` rebuilt the experiment field by field and silently
  dropped `kill_criteria`, `dataset`, `architecture` and `tags`. An evaluator
  checking kill criteria saw an empty list at exactly the moment the answer
  should have been "stop the project".
- `quantization-strategy` said int8 was post-training and the first thing to
  try, while the size gate told the agent to reach for quantization-aware
  training at int8. The gate is what an agent reads at the moment of decision.
- CI ran `validate` on nothing: the loop only parse-checked YAML. It now runs
  the validator over every committed experiment file.

## [0.1.0] — 2026-09-18

Initial commit. Never tagged, never released, and not on PyPI — this is where
the record starts, not something anyone could have installed. `__version__` has
read `0.1.0` since that commit and everything above happened on top of it.

[Unreleased]: https://github.com/melissa-pereira-deel/tiny-model-lab/compare/3058ac5...HEAD
[0.1.0]: https://github.com/melissa-pereira-deel/tiny-model-lab/commit/3058ac5
