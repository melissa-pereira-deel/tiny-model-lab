# Why the harness is shaped this way

## Agent = model + harness

The model is fixed; you do not train it. The harness is everything around it —
instructions, tools, gates, feedback loops — and it is the part you control.
That is the whole premise of harness engineering as a discipline, named in
February 2026 by Ryan Lopopolo at OpenAI and independently by Mitchell Hashimoto.

Hashimoto's formulation is the operating principle here: *anytime you find an
agent makes a mistake, take the time to engineer a solution such that the agent
never makes that mistake again.* Every guard and gate in this repo is the
residue of a specific failure mode.

## Guides and sensors

Birgitta Böckeler's taxonomy gives us two axes worth keeping straight.

**Guides** are feedforward — they steer before the agent acts. Here: `AGENTS.md`,
the skills, the experiment template, the `PreToolUse` guard that refuses training
without an experiment file.

**Sensors** are feedback — they observe after the agent acts. Here: the gates,
the promotion rule, the session log.

The second axis is **computational** (deterministic, fast, reliable — tests,
linters, a size check) versus **inferential** (semantic, slow, non-deterministic —
LLM-as-judge). This harness is deliberately weighted toward computational
sensors, because an agent can run them every loop and trust the answer.

Böckeler warns against having only one kind. Feedback-only keeps repeating the
same mistakes. Feedforward-only encodes rules but never learns whether they
worked. You need both.

**Where the spike sits, precisely.** A spike record is a *guide*. It steers
before the measurement — the threshold is written while the number does not
exist and cannot talk you into a different one — and it is inferential,
because only a reader can say whether the finding actually met the threshold.
`python -m harness spikes` is a *computational sensor*, but the thing it
senses is the guide, not a run: it checks that the record is complete, that
`informs` names a field the contract has, and that the box was not quietly
widened after the fact. It cannot check that the measurement was honest, and
`harness/spike.py` says so in the refusal itself — the same admission
`validate.py` makes about reading a label rather than a split.

So this does **not** fill the empty computational-guide cell, and it would be
worth very little if it claimed to. A computational guide would be something
that stops you before the mistake using arithmetic rather than prose; a
checker that reads a form you already filled in is a sensor, whatever the form
is about.

## Why gates, specifically

The dominant failure mode of agent-driven ML is not bad code. It is a
plausible-looking loop that burns a night of compute going nowhere, producing a
number nobody can interpret because there was never anything to compare it to.

Two things prevent this, and they are the load-bearing parts of this repo:

1. **A named baseline with a measured number**, decided before training
2. **Patience and wall-clock caps**, enforced by something other than the agent's judgment

Everything else is convenience.

## Why the promotion gate is strict

`harness/promote.py` will only promote a run that passes every gate *and*
strictly improves on the current champion. Ties lose. This is modelled on
gpu-lexer's rule — promote only a run that strictly improves untouched
verification accuracy and passes the language guards.

The effect is that `runs/` accumulates honest history instead of becoming a
graveyard of things that were briefly called best.

## What this repo deliberately does not do

It does not run autonomous architecture search or an open-ended experiment tree.

That is not modesty, it is arithmetic. MLE-bench's reference setup consumed on
the order of 1,800 GPU-hours for a single pass and reached a bronze-medal
equivalent in under a fifth of competitions at first attempt. Research-grade
automated ML agents buy their results with enormous compute and high variance.
A solo builder on one machine gets far more from a small number of well-chosen,
hard-gated experiments than from a search.

**Humans steer. Agents execute.**

## Subagents, and why only five

Context isolation is the real reason to split an agent, not tidiness. Training
logs should not pollute the conversation where you are thinking about the
interaction design. Each subagent here has a genuinely different tool scope and
a different failure mode.

Beyond that, more tools measurably degrade tool selection. Anthropic's own
guidance is that the most successful implementations use simple, composable
patterns rather than complex frameworks. Five is already generous.

`/spike` is the sixth command and deliberately has no sixth subagent. Its
output is one sentence and one number, so there is nothing to isolate, and
isolating it would cost the surrounding context that makes a finding mean
anything.

That argument has a stated assumption: it holds while spikes stay small. A
project whose questions are all data-crunching — parse a million rows, profile
a corpus — will feel the context cost in the main conversation, and should
give `/spike` a subagent at that point. Saying so here is better than
pretending the question is settled, because the answer depends on a property
of your project rather than of this harness.
