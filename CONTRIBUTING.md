# Contributing

## What's most wanted

**Negative results.** A documented case of "I trained this, the baseline won,
here's what I learned" is worth more to this repo than another architecture.
The whole premise is that most tasks shouldn't be models, and the evidence for
that claim is currently thin because nobody publishes it.

Also valuable:

- **Worked examples** that train a real model end to end and export it
- **Export-path notes** — especially MLX, Core ML, and WebGPU correctness gotchas
- **Better gates**, particularly computational (fast, deterministic) rather than inferential
- **Corrections** where a claim here is wrong or has gone stale

## Ground rules

- Every example names a baseline and reports its number. No exceptions.
- Report p95 latency measured warm, with cold start stated separately.
- State what a metric actually measures. Agreement with a teacher tool is not objective correctness, and conflating the two is the most common dishonesty in this field.
- Keep the harness core dependency-light. Heavy dependencies go in optional extras.

## Skills and subagents

Follow the existing shape: YAML frontmatter with `name` and `description`, where
the description says both what it does *and* when to trigger. Keep SKILL.md
bodies under ~500 lines and push detail into references.

## Before opening a PR

```bash
pip install -e ".[dev]"
python examples/01-hello-tiny/run.py
ruff check .
```
