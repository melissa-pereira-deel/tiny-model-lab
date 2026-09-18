# AGENTS.md — tiny-model-lab

A map, not a manual. Each line below exists because something went wrong without it.

## What this repo is for

Taking a narrow task from idea to an embedded model of kilobytes-to-low-megabytes
that runs locally, in a browser or on a device — and, more often, discovering
early that it should not be a model at all.

## The rule that matters most

**Every experiment names a specific existing thing it must beat, with a measured
number.** Not "improve accuracy". A named baseline. If you cannot name one, the
task is not scoped yet and no training should start.

Ties go to the baseline. It ships without weights.

## Order of operations

1. `/scope <task>` → `task-triage` subagent → produces `experiments/<slug>.yaml` or a refusal
2. `data-builder` → dataset with an untouchable held-out split
3. `/experiment <path>` → `trainer` subagent → baseline first, then the model
4. `/gate <run>` → `evaluator` subagent → promote / iterate / stop
5. `/ship <run>` → `embedder` subagent → export, verify numerically, write the model card

Do not skip step 1. Do not skip the baseline in step 3.

## Stop conditions are enforced, not advisory

Read from `experiment.yaml`: size budget, latency band, wall-clock cap, patience.
When a gate fails it returns a remediation — follow it rather than improvising.
The remediation exists because the improvisation was already tried.

Never extend patience mid-run to rescue a plateau. Change something structural
or stop. A new seed is not a structural change.

## Stack defaults

- Browser or cross-platform target → **PyTorch + MPS**, because ONNX and Core ML export paths are mature
- Artifact stays local → **MLX** (no first-class converter to Core ML or ONNX exists)
- Training tiny models on MPS is fine; **serving from MPS is not**

## Where to look

| You need | Read |
|---|---|
| Should this be a model at all? | `.claude/skills/tiny-model-triage/` |
| How to get labels | `.claude/skills/dataset-synthesis/` |
| What architecture | `.claude/skills/architecture-selection/` |
| Fitting a size budget | `.claude/skills/quantization-strategy/` |
| Getting it into a product | `.claude/skills/export-pipeline/` |
| Is the *feature* good? | `.claude/skills/design-eval/` |
| Why the harness is shaped this way | `docs/harness-design.md` |
| Concepts, analogy-first | `docs/concepts.md` |

## Conventions

- `runs/` holds manifests; corpora and checkpoints are gitignored
- `champion/` holds exactly one promoted model, changed only via `harness/promote.py`
- Provenance is committed; artifacts are not
- Report p95 latency measured warm, plus cold start separately
