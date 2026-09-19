# How to prompt this agent

Everything below exists in this repo. There are five commands and five
subagents; nothing else is wired up.

## The five commands

One per subagent, in pipeline order.

| Command | Delegates to | Produces |
|---|---|---|
| `/scope <task>` | `task-triage` | `experiments/<slug>.yaml`, or a written refusal naming which rung of the ladder to use instead |
| `/data <path>` | `data-builder` | a dataset with an untouchable held-out split, a named split unit, and a 20-example label audit |
| `/experiment <path>` | `trainer` | a run directory and manifest, baseline measured first, gated after every eval |
| `/gate <run>` | `evaluator` | every gate result plus the five design checks, ending in **promote** / **iterate** / **stop** |
| `/ship <run>` | `embedder` | an export verified numerically at each hop, plus a `MODEL_CARD.md` |

`/scope` is the only one that takes a free-form task. The rest take a path,
because by then there is a file to point at.

The subagents run with isolated context, which is the point: training logs and
dataset dumps stay out of your main conversation, and what comes back is the
verdict and the numbers.

Underneath, the commands call this — it is the part that is just Python, and
you can use it without Claude Code at all:

```bash
python -m harness init                      # scaffold a project
python -m harness validate <experiment.yaml>   # /scope and /data end here
python -m harness gate     <run-dir>
python -m harness ship     <run-dir> <artifact> [--champion-dir DIR]
```

**There is no training subcommand, deliberately.** The harness core stays
dependency-light — torch is an optional extra — so the training script belongs
to your experiment, not to the harness. `/experiment` is the one command whose
middle has no CLI equivalent, and `.claude/hooks/guard-experiment.sh` is what
stands in for one: it refuses to run a training script when no experiment file
exists.

What you lose without Claude Code is the triage conversation and the isolated
context, not the gates.

## Name the target and the constraint in the `/scope` prompt

`task-triage` asks five questions before it will produce anything. Two of them
are about your deployment, and answering them up front saves a full round trip:

- **Question 4** — what does tiny buy that an API call does not? It accepts four
  answers: sub-100ms latency the network cannot deliver, privacy that makes the
  feature shippable at all, offline capability, or per-inference cost low enough
  to run continuously. "It feels more elegant" is not one, and if none of the
  four apply the verdict is `large-model`.
- **Question 5** — what is the size budget? It asks what the user will actually
  download, and if nobody has a number it will propose one *from the deployment
  target* and make you agree to it.

So say where it runs and what it runs on. "In the browser" already answers a lot
of question 5; "on a five-year-old Android phone, offline" answers most of both.

It is also the cheapest way to avoid the stack trap: `AGENTS.md` defaults you to
PyTorch + MPS for browser and cross-platform targets specifically because MLX has
no first-class converter to ONNX or Core ML. Triage can only apply that rule if
it knows where the artifact is going.

## Example prompts

**Scoping, with the target stated:**

```
/scope Classify a hand-drawn stroke as rectangle / ellipse / arrow / line so the
whiteboard snaps it to a clean shape while the finger is still down. Runs on
iPad via Core ML, fully offline. The snap has to land inside the instant band or
the gesture feels like it lagged. Labels can come from our existing shape
recogniser, which gets simple strokes right and fails on anything drawn fast.
```

That prompt answers both questions before they are asked: the target is Core ML
on iPad, the win is latency plus offline, and it names the existing recogniser —
which becomes the mandatory baseline in the experiment file.

**Scoping something that should probably be refused:**

```
/scope We want a tiny model that writes alt text for images in our CMS. It runs
server-side when an editor uploads, so latency is not critical and there is no
privacy constraint.
```

Expect a `large-model` verdict, and expect that to be the useful answer. Open-
ended generation with no latency, privacy, offline, or cost-at-frequency
argument is the case triage exists to turn down. A refusal is a result — write
it into `experiments/` so nobody re-derives it in six weeks.

**Running and gating:**

```
/experiment experiments/stroke-shapes.yaml

Background the training and check in — do not sit in a loop. Report the curve,
not the epochs, and stop at the first gate failure rather than working around it.
```

```
/gate runs/20260918T2114Z--stroke-shapes

Include the design checks, and tell me which latency band it landed in and what
that means for whether the snap needs a visible transition.
```

## What not to expect

- **Don't ask for "it depends."** `/scope` is instructed to return a verdict or a
  refusal, never a survey of options.
- **Don't ask to skip the baseline.** The trainer measures it first, and
  `.claude/hooks/guard-experiment.sh` blocks training when no experiment file
  exists at all. A baseline the runner measures is declared with
  `measured_at_runtime: true`, and `baseline_gate` refuses the run if the number
  never arrives.
- **Don't ask to tune hyperparameters after a baseline failure.** The gate's own
  remediation tells the agent to fix the representation first; asking for a
  learning-rate sweep puts you in an argument with the harness.
- **Don't ask `/ship` to export an unpromoted run.** It checks
  `champion/champion.json` and refuses.

## If you are new here

Read `docs/concepts.md` for the vocabulary, `docs/stop-conditions.md` for what
ends a run, and `docs/dos-and-donts.md` for the rules and the files they live in.
