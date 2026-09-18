# tiny-model-lab

A Claude Code harness for researching, training, and embedding **tiny models** —
the kilobyte-to-few-megabyte kind that run locally in a browser or on a device
and do exactly one narrow thing.

Built for interaction designers, design engineers, and creative technologists:
people who can prototype in code, care how an interaction *feels*, and want the
model to be a material they can work with rather than an API they call.

> A 27.5KB model that syntax-highlights code in the browser, inferring the
> language rather than being told — [gpu-lexer](https://gpu-lexer.vercel.app/) —
> is the reference case. The model isn't a feature you see. It's infrastructure,
> like a spell-checker.

## What makes this a harness and not a tutorial

The hard part of tiny-model work isn't training. It's **knowing when to stop**,
and knowing whether the thing you trained is better than the four lines of code
it replaced.

So the central mechanic is a gate: every experiment names a specific existing
thing it must beat, with a measured number, before any training starts. Ties go
to the baseline, because the baseline ships without weights.

```
/scope       task-triage    →  should this be a model at all?
/experiment  trainer        →  baseline first, then the model, budgets enforced
/gate        evaluator      →  promote / iterate / stop
/ship        embedder       →  export, verify numerically, write the model card
```

## Try it in one second

```bash
git clone https://github.com/YOUR-USERNAME/tiny-model-lab
cd tiny-model-lab
pip install -e .
python examples/01-hello-tiny/run.py
```

No ML dependencies, no GPU, runs instantly. It ends with the outcome nobody
plans for and everyone eventually gets:

```
[FAIL] baseline: candidate accuracy=0.9200 vs deterministic baseline=1.0000
[PASS] size: artifact 0.1 KB vs budget 5.0 KB
[PASS] latency: p95 0.0 ms vs 'instant' band ceiling 100 ms

Outcome: the deterministic baseline wins, so the baseline ships.
```

That's a **successful** run. Without the baseline gate you'd have seen 0.92,
felt good, and shipped something worse than four `if` statements.

## What's in here

```
.claude/
  agents/      5 subagents: task-triage, data-builder, trainer, evaluator, embedder
  skills/      6 skills: triage, dataset synthesis, architecture, quantization,
               export, and design-eval
  commands/    /scope  /experiment  /gate  /ship
  hooks/       refuses training without an experiment file; logs sessions
harness/       experiment specs, gates, profiling, promotion — plain Python
docs/          concepts (analogy-first), harness design, stop conditions
examples/      worked, runnable
templates/     experiment.yaml, MODEL_CARD.md
```

## The ladder

Most tasks that sound like tiny models aren't. Work up from the bottom, stop at
the first rung that works:

| Rung | Use when | Cost to try |
|---|---|---|
| Deterministic rule | Output follows known rules | minutes |
| Classical ML | Tabular, closed output space | minutes |
| **Tiny model** | Learned representation, closed output, cheap labels | **days** |
| Large model API | Open-ended, world knowledge, reasoning | minutes |

The ladder is asymmetric on purpose. Three of the four rungs cost minutes. One
costs days. Earn it.

A tiny model has to win on something the user can feel: **latency** the network
can't deliver, **privacy** that makes the feature shippable at all, **offline**
capability, or **cost at frequency** low enough to run continuously. "More
elegant" isn't one of them.

## Design gates are first-class

A model can pass every technical budget and still be the wrong thing to ship.
The `evaluator` checks five things drawn from Google PAIR, Apple's HIG for
machine learning, and Amershi et al.'s CHI 2019 guidelines:

1. **Failure state** — what does wrong look like on screen?
2. **Uncertainty legibility** — if confidence varies and the UI doesn't show it, the interface is lying
3. **User override** — a wrong output you can't escape is worse than no output
4. **Privacy legibility** — if nothing leaves the device, *say so where users can see it*
5. **First-run cost** — model download and warm-up is the one moment every user experiences

And the latency band, which is the whole argument for going local:

| Band | Ceiling | What it buys |
|---|---|---|
| Instant | 100 ms | Direct manipulation. No spinner. A network round-trip can't reach here. |
| Flow | 1 s | Thought unbroken. |
| Attention | 10 s | Needs visible progress. |

## Stack defaults

- **Browser / cross-platform target → PyTorch + MPS.** The ONNX and Core ML export paths are mature.
- **Artifact stays local → MLX.** Excellent on Apple silicon, but it has no first-class converter to Core ML or ONNX — pick your export path *before* your training framework.
- Training tiny models on MPS is fine. **Serving from MPS is not.**

## Status

Early and honest about it. The harness, gates, and worked example run today. The
subagents and skills are written and usable; they haven't been evaluated at
scale. Treat version 0.1 as a well-argued starting point, not a proven system.

Issues and PRs welcome — especially negative results. A documented case of
"trained this, baseline won, here's why" is worth more here than another
architecture.

## Reading

- [gpu-lexer](https://gpu-lexer.vercel.app/) — the reference tiny model
- Belcak et al., [Small Language Models are the Future of Agentic AI](https://arxiv.org/abs/2506.02153)
- Böckeler, [Harness engineering for coding agent users](https://martinfowler.com/articles/harness-engineering.html)
- [Google PAIR People + AI Guidebook](https://pair.withgoogle.com/guidebook/)
- Amershi et al., [Guidelines for Human-AI Interaction](https://doi.org/10.1145/3290605.3300233) (CHI 2019)

## License

MIT — see [LICENSE](LICENSE).
