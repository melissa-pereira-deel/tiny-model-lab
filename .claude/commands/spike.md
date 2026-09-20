---
description: Run one cheap measurement against a written threshold, so a contract field carries a number somebody measured.
---

Run a spike on: $ARGUMENTS

The argument is either a question — "do at least 90% of the corpus chord
symbols parse with the published mapping?" — or a path to an open
`experiments/<slug>.spike.md` that `/scope` already wrote.

If it is a question, write the record first, from
`harness/templates/spike.md`. Filling in `informs`, `threshold` and `if_not`
*before* measuring is the entire mechanism: a threshold written after the
number exists is a number wearing a threshold's clothes.

Then measure, and finish the record — `status`, `finding`, `measured`,
`elapsed_minutes`. End by running `python -m harness spikes`, which refuses a
record that is not one yet.

## Four rules

1. **Cheapest test that could answer it.** Ten thousand rows, not the corpus.
   One afternoon's subset, not the full pipeline. A spike that costs what the
   experiment costs has bought nothing.
2. **Stop at `budget_minutes`.** Over the box, the way out is
   `status: abandoned` with a finding saying what you learned anyway — not an
   edit to `budget_minutes`, which would turn what you agreed to spend into a
   record of what it cost.
3. **Never `start_run()`, never a `*train*.py`.** A run manifest carries a
   *comparison* — a baseline, an eval history, a wallclock. A spike has one
   measurement against one threshold. There is no run directory, nothing to
   gate, and nothing promotable; `python -m harness gate` on a spike path
   exits 2 and that is correct.
4. **If it starts to look like training, stop and run `/scope`.** Wanting a
   manifest, an eval loop or a second variant means the question has grown
   into an experiment, and an experiment needs a contract with a named
   baseline first. Say that out loud rather than quietly continuing.

## Report

The finding in one sentence, the number if there is one, and what `if_not`
now obliges. If the answer was no, do that thing — or the record is
decoration.

## Why there is no subagent for this

The other five commands delegate because their output is noisy: training logs
and dataset dumps should not land in the conversation where you are thinking
about the interaction. A spike's output is one sentence and one number, so
isolation would buy nothing and cost you the context that makes the finding
mean something.

The honest caveat: that reasoning assumes spikes stay small. A project whose
questions are all data-crunching will feel the context cost, and should
revisit this — `docs/harness-design.md` says so rather than pretending it is
settled.
