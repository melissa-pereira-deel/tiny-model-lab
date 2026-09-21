# tiny-model-lab

[![ci](https://github.com/melissa-pereira-deel/tiny-model-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/melissa-pereira-deel/tiny-model-lab/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

For the last few years, "add AI to this" has meant one thing: a network call. A
prompt goes out, tokens come back, and the interesting part of your product
happens on someone else's hardware, on someone else's schedule, at someone
else's price.

Something quieter has been getting practical alongside it. Models small enough
to compile in — kilobytes to a few megabytes, running locally, doing exactly one
narrow thing. Not a service you call. **A part you ship.**

[gpu-lexer](https://gpu-lexer.vercel.app/) is 27.5KB. It syntax-highlights code
in the browser and works out which language it's looking at rather than being
told. Nobody using it thinks about a model, because it isn't a feature anyone
sees. It's infrastructure, like a spell-checker.

That is the shift worth paying attention to: a model as a **software primitive**.
A regex that learned. A shader with weights. Something you reach for the way you
reach for a parser — because it is small, local, and yours. It changes what you
can put in an interface, because a thing that answers in under 100 ms can be
part of a gesture instead of a request.

Most tasks that sound like this shouldn't be models at all. **This repo is
mostly here to tell you which** — and to make sure that when you do build one,
you can prove it beat the four lines of code it replaced.

> **⚠️ Status: early, and measured about it.**
>
> The harness, the gates, the CLI and both worked examples run today, with 367
> tests and CI on Python 3.10 and 3.14 across Ubuntu and Windows. The six
> commands, five subagents and six skills are written and usable; they have not
> been evaluated at scale.
>
> A real model now goes through the whole pipeline — trained in PyTorch,
> exported to ONNX, verified numerically, quantized to int8, gated on bytes on
> disk. **Nothing has been promoted**, because in both examples the baseline
> won. That is the outcome this repo predicts for most tasks, and it is still a
> thinner result than a shipped champion would be.
>
> Treat version 0.1 as a well-argued starting point, not a proven system. The
> most useful thing you can send is a negative result: *"I trained this, the
> baseline won, here's what I learned."*

---

## Models as parts, not services

An API call is a wonderful default and a bad primitive. It is someone else's
uptime, someone else's latency floor, someone else's per-token bill, and it
cannot run on a plane. For open-ended work — reasoning, world knowledge,
generation — that trade is obviously worth it. For a narrow, closed, repeated
judgement, it is obviously not, and we have been making it anyway because it was
the only move anyone had tooling for.

A tiny model earns its place by buying something a user can feel. There are
exactly four honest answers:

- **Latency** the network cannot deliver. Not "faster" — *categorically* faster.
- **Privacy** that makes the feature legal to ship at all.
- **Offline**, because the thing has to work on a train.
- **Cost at frequency** low enough to run continuously rather than on demand.

"It feels more elegant" is not on the list. Neither is accuracy — tiny models
rarely win on accuracy, and reaching for one on those grounds is usually a
mis-scoped task wearing a disguise.

The latency argument is the one that most changes what you can design:

| Band | Ceiling | What it buys |
|---|---|---|
| Instant | 100 ms | Direct manipulation. No spinner. A network round-trip cannot reach here. |
| Flow | 1 s | Thought stays unbroken. |
| Attention | 10 s | Needs visible progress, and the design has to change — not the model. |

Those numbers are Miller (1968) and Nielsen (1993). They are perceptual facts
about people, not engineering targets, which is why they live in the code rather
than in a config someone can negotiate with.

---

## The catch: nobody knows when to stop

The hard part of tiny-model work is not training. It is **knowing when to stop**,
and knowing whether the thing you trained is better than what it replaced.

This is where the field is quietly dishonest. A model reports 0.92 and everyone
feels good. Nobody measured the regex. The regex gets 0.97.

So the central mechanic here is a gate: **every experiment names a specific
existing thing it must beat, with a measured number, before any training
starts.** Ties go to the baseline, because the baseline ships without weights,
without a training pipeline, and without silent failure modes. Equal accuracy is
not equal value.

That rule is a strict `>` in `harness/gates.py`, and everything else in this
repo exists to enforce it. If your metric runs the other way — a loss, a word
error rate — say so with `baseline.higher_is_better: false` and the comparison
inverts. The gate refuses to guess: a metric whose name reads like something
you minimise, with nobody having said which way it goes, fails rather than
quietly comparing backwards.

```
/spike       (no subagent)  →  one cheap measurement, so a field carries a real number
/scope       task-triage    →  should this be a model at all?
/data        data-builder   →  labels, and a held-out split that does not leak
/experiment  trainer        →  baseline first, then the model, budgets enforced
/gate        evaluator      →  promote / iterate / stop
/ship        embedder       →  export, verify numerically, write the model card
```

---

## Try it in one second

```bash
git clone https://github.com/melissa-pereira-deel/tiny-model-lab
cd tiny-model-lab
pip install -e .
python examples/01-hello-tiny/run.py
```

No ML dependencies, no GPU, no download. It ends with the outcome nobody plans
for and everybody eventually gets:

```
baseline 'rule classifier (isspace/isdigit/isalnum/else)': 1.0000 on held-out

... two earlier evals elided; the third and last reads:

--- eval: n=4000 ---
[FAIL] baseline: candidate accuracy=0.9200 vs deterministic baseline 'rule classifier (isspace/isdigit/isalnum/else)'=1.0000 (higher is better)
       -> The baseline still wins. Do NOT tune hyperparameters yet -- that is the expensive way to discover a scoping error. In order: (1) improve the input representation, which is where most tiny-model gains live; (2) check label quality on 20 disagreements by hand; (3) if neither moves it, write this up as a negative result and ship the baseline.
[PASS] size: artifact 0.7 KB vs budget 5.0 KB
[PASS] latency: p95 0.0 ms vs 'instant' band ceiling 100 ms
[PASS] patience: last 2 evals ['0.9200', '0.9200'] vs best-before 0.9040
[PASS] wallclock: 0.0 min elapsed vs cap 5 min

accuracy / size / latency curve:
variant           acc    size KB    p95 ms
lookup-250     0.9040        0.7       0.0
lookup-1000    0.9200        0.7       0.0
lookup-4000    0.9200        0.7       0.0

Outcome: the deterministic baseline wins, so the baseline ships.
That is a successful run. The harness cost you one second to learn it
instead of a week, and the reasoning is now in the run manifest.
```

That is a **successful** run. Without the baseline gate you would have seen
0.92, felt good, and shipped something worse than four `if` statements.

---

## The ladder

Most tasks that sound like tiny models aren't. Work up from the bottom and stop
at the first rung that works:

| Rung | Use when | Cost to try |
|---|---|---|
| Deterministic rule | Output follows known rules | minutes |
| Classical ML | Tabular, closed output space | minutes |
| **Tiny model** | Learned representation, closed output, cheap labels | **days** |
| Large model API | Open-ended, world knowledge, reasoning | minutes |

The ladder is asymmetric on purpose. Three of the four rungs cost minutes. One
costs days. Earn it.

---

## The shape of task that fits

These are *shapes*, not a portfolio. One of them has now been built and taken
through the whole pipeline in `examples/02-config-lexer/`, where the baseline
won. They are what the triage questions are looking for, and
they share a signature: a closed output space, a bounded input, and labels you
can get for free from a tool that already exists.

**A learned lexer.** Highlight code without shipping a grammar per language.
The teacher is any existing parser; the win is that it generalises to languages
it never saw. This one is real — it is gpu-lexer, and it is the reference case.

**Shape snapping in a drawing tool.** Rectangle / ellipse / arrow / line while
the finger is still down. The teacher is your current recogniser. The win is
`instant` — a snap that arrives after a round-trip feels like a bug.

**Intent triage in a command bar.** Route a keystroke to search, navigation, or
calculation before the user finishes typing. The teacher is your own analytics.
The win is cost at frequency: this fires on every keypress.

**On-device redaction.** Spot what looks like a name, an address, or a card
number before anything is uploaded. The teacher is a regex suite plus a large
model for the hard cases. The win is privacy — it is what makes the feature
shippable at all.

**Gesture or sensor classification.** A wearable deciding between four motions.
The teacher is hand-labelled, which caps your dataset — so this is the shape
most likely to come back from triage as *classical ML, not a tiny model*, and
that is a good outcome.

Notice how many of these are decided by the teacher. **Where your labels come
from is a bigger design decision than your architecture**, and it is the
question people skip.

---

## What it works with

Three different answers, and the README used to blur them.

| Layer | What it actually needs |
|---|---|
| **The five gates** | Five numbers. `run_all` takes floats and a sequence of floats; `gates.py` imports nothing outside the standard library and this package |
| **Size measurement** | `stat()` and a division. It measures a `.wasm`, a Swift binary and an `.mlpackage` identically, because it never opens the file — which is why promotion can afford to run it on anything |
| **Promotion** | Copies a file or a directory, having measured its bytes and re-run the size gate on them. That is the only thing it inspects: the `target` field is not even validated — write `rust-wasm` and everything still runs |
| **Latency** | `latency_ms` times a *Python callable* — the one real boundary. But `latency_gate` takes a bare float, so measure p95 in your own runtime and hand the number over |
| **The workflow layer** | Claude Code. `AGENTS.md` is already vendor-neutral and the skills are plain Markdown, so the doctrine ports even where the tooling doesn't |
| **The training guard** | bash. On Windows it is silently absent — the test skips rather than fails |

So: **the discipline is technology-agnostic; the plumbing is Python.** The gate
logic is about ten lines of comparisons. If you work in Rust, Swift or
TypeScript, porting it is an afternoon, and you would lose nothing that matters.

The evidence, rather than the assurance: **CI runs on Ubuntu, installs no ML
framework at all, and passes.** The core has exactly one runtime dependency, a
YAML parser. Every mention of PyTorch, MLX, Core ML or Apple silicon in this
repo is prose — there is no hardware-specific code anywhere in `harness/`.

---

## Using it on your own project

```bash
pip install git+https://github.com/melissa-pereira-deel/tiny-model-lab
cd my-project
python -m harness init        # creates experiments/ and runs/, drops a blank spec
```

`init` also plants the marker the harness uses to find your project, so runs,
champions and the ledger land in *your* directory. The CLI mirrors the slash
commands:

```bash
python -m harness validate experiments/my-task.yaml
python -m harness spikes                       # what you measured, what is still open
python -m harness gate     runs/20260918T2114Z--my-task
python -m harness ship     runs/20260918T2114Z--my-task model.onnx
```

`ship` writes `champion/champion.json` and appends to `runs/LEDGER.md` in your
project. Add `--champion-dir DIR` to send both somewhere else — which is how you
try promotion inside a clone of this repo without leaving files in it.

**pip gives you the gates. You copy the agent layer.** `.claude/` is
deliberately not packaged — clone the repo and copy it into your project, the
way you would any set of prompts. Without it you still get the contract, the
five gates, the run manifests and the promotion rule. What you lose is `/scope`
as one word, the five subagents' isolated context, and the `PreToolUse` hook
that refuses training when no experiment file exists.

Nothing about the gates requires an agent at all. `import harness` and use them
from a plain script.

---

## Design gates are first-class

A model can pass every technical budget and still be the wrong thing to ship.
The `evaluator` checks five things drawn from Google PAIR, Apple's HIG for
machine learning, and Amershi et al.'s CHI 2019 guidelines:

1. **Failure state** — what does wrong look like on screen?
2. **Uncertainty legibility** — if confidence varies and the UI renders everything identically, the interface is lying
3. **User override** — a wrong output you can't escape is worse than no output
4. **Privacy legibility** — if nothing leaves the device, *say so where users can see it*
5. **First-run cost** — model download and warm-up is the one moment every user experiences

These are judgement, not arithmetic, and the tooling says so: `python -m harness
gate` prints the five computable gates and then states plainly that the design
checks and the promote / iterate / stop verdict are yours to make. A harness
that faked them would be worse than one that admits the gap.

---

## What's in here

```
.claude/
  agents/      5 subagents: task-triage, data-builder, trainer, evaluator, embedder
  skills/      6 skills: triage, dataset synthesis, architecture, quantization,
               export, and design-eval
  commands/    /scope  /data  /experiment  /gate  /ship — one per subagent,
               plus /spike, which runs in the main conversation
  hooks/       refuses training without an experiment file; logs sessions
harness/       the contract, the spike, the gates, profiling, promotion, CLI —
               plain Python plus templates/, so they ship with the package
docs/          concepts, harness design, stop conditions, do's and don'ts,
               how to prompt the agent
examples/      01 dependency-free in a second; 02 trains, exports, quantizes
tests/         367 of them, including the hooks and the gate arithmetic
CHANGELOG.md   what changed, with gate semantics as its own category — a
               stricter gate invalidates a run that already passed
```

Two pages worth reading before you start. **[How to prompt this
agent](docs/prompting-guide.md)** — the six commands, the five subagents, and
why naming your deployment target inside a `/scope` prompt saves a round trip.
**[Do's and don'ts](docs/dos-and-donts.md)** — the rules that are actually
enforced, each pointing at the file that enforces it.

---

## Stack defaults

Advice, not requirements. Nothing in `harness/` checks your hardware.

- **Browser or cross-platform target → PyTorch + MPS.** The ONNX and Core ML export paths are mature.
- **Artifact stays local → MLX.** Excellent on Apple silicon, but it has no first-class converter to Core ML or ONNX — pick your export path *before* your training framework.
- Training tiny models on MPS is fine. **Serving from MPS is not.**

---

## Reading

- [gpu-lexer](https://gpu-lexer.vercel.app/) — the reference tiny model, and the existence proof for the whole argument
- Belcak et al., [Small Language Models are the Future of Agentic AI](https://arxiv.org/abs/2506.02153) — the case that small and specialised beats large and general for narrow work
- Böckeler, [Harness engineering for coding agent users](https://martinfowler.com/articles/harness-engineering.html) — guides steer before, sensors check after; this repo is mostly sensors
- [Google PAIR People + AI Guidebook](https://pair.withgoogle.com/guidebook/) — where the design gates come from
- Amershi et al., [Guidelines for Human-AI Interaction](https://doi.org/10.1145/3290605.3300233) (CHI 2019) — the other half
- Miller (1968) and Nielsen (1993) on response times — the 100 ms / 1 s / 10 s bands, unchanged in fifty years

Sibling project: [creative-technologist-agent](https://github.com/melissa-pereira-deel/creative-technologist-agent)
— named thinking lenses for deciding *what* to build, plus engineering skills
for building it well. Two of them meet this repo. [On-Device ML
Optimization](https://github.com/melissa-pereira-deel/creative-technologist-agent/blob/main/skills/on-device-ml/SKILL.md)
covers quantization, the Core ML pipeline and Neural Engine constraints — where
the question gets asked; here is where the answer gets a number. And
[Performance as
Experience](https://github.com/melissa-pereira-deel/creative-technologist-agent/blob/main/skills/performance-as-experience/SKILL.md)
draws the same 100 ms boundary from the same perceptual literature as
`LATENCY_BANDS_MS`. Note it bins the rest differently — ~50 ms and a <16 ms /
<300 ms / <1 s audit scale, against instant / flow / attention here. Shared
foundation, not interchangeable taxonomies.

---

## License

MIT — see [LICENSE](LICENSE).

---

Created by Melissa de Britto. Open-sourced because the negative results are the
part nobody publishes, and they are the part that would help.
