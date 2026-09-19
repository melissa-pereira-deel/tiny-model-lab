# Contributing

## What's most wanted

**Negative results.** A documented case of "I trained this, the baseline won,
here's what I learned" is worth more to this repo than another architecture.
The whole premise is that most tasks shouldn't be models, and the evidence for
that claim is currently thin because nobody publishes it.

Also valuable:

- **Worked examples** that train a real model end to end and export it — `examples/02-config-lexer/` is the reference shape. A third that ends with the model *winning* would be the most useful one yet; both of the current examples end with the baseline ahead
- **Export-path notes** — especially MLX, Core ML, and WebGPU correctness gotchas
- **Better gates**, particularly computational (fast, deterministic) rather than inferential
- **Corrections** where a claim here is wrong or has gone stale

## Ground rules

- Every example names a baseline and reports its number. No exceptions. A baseline measured by the runner declares `measured_at_runtime: true`; that defers the number, it does not excuse it.
- Report p95 latency measured warm, with cold start stated separately.
- State what a metric actually measures. Agreement with a teacher tool is not objective correctness, and conflating the two is the most common dishonesty in this field.
- Keep the harness core dependency-light. Heavy dependencies go in optional extras.

## Skills and subagents

Follow the existing shape: YAML frontmatter with `name` and `description`, where
the description says both what it does *and* when to trigger. Keep SKILL.md
bodies under ~500 lines and push detail into references.

## Before opening a PR

Everything CI runs, in the order it runs it:

```bash
pip install -e ".[dev]"
python -m harness validate examples/*/experiment.yaml
python examples/01-hello-tiny/run.py
ruff check .
pytest -q
```

CI additionally parse-checks `harness/templates/experiment.yaml`, which cannot
be validated — it is a blank form and is invalid on purpose. That only matters
if you are editing the template itself.

**If you changed a rule, add it to `CHANGELOG.md` under `[Unreleased]`.** A gate's
arithmetic, a validator's requirement, the guard's match patterns — those are the
changes someone pinned to a version cannot discover any other way, and a gate
that gets stricter goes under `Gate semantics` because it invalidates a run that
passed. New features and fixes are worth a line too; `tests/test_changelog.py`
only enforces that the version and the categories stay honest, not that you
wrote an entry.
