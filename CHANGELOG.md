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
