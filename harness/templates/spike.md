---
# A spike is the measurement that gives a contract field its value — or that
# decides whether a contract should be written at all. Fill this in *before*
# you measure anything. `python -m harness spikes` refuses a blank form, and
# that refusal is the feature: a question with no threshold and no named
# consequence is a note, and notes do not change what gets built.
#
# Save as experiments/<slug>.spike.md. It is committed, like the contract and
# like a refusal. The training guard and CI both look for experiments/*.yaml,
# so this file unlocks neither — deliberately, and tests/test_guard_hook.py
# says so.

question: ""          # >= 5 words, and an actual question. "Do at least 90% of
                      # the corpus chord symbols parse with the published
                      # mapping?" Not "look into the chord mapping."

informs: ""           # Which contract field this measurement gives a value to:
                      # dataset.teacher, budgets.max_size_kb, baseline.value...
                      # Or the literal `scope`, when what it decides is whether
                      # a contract gets written at all. A list is fine.

threshold: ""         # What a yes looks like, written down before the number
                      # exists and can talk you into a different one. Nothing
                      # compares your finding to this: the check reads a label,
                      # not a measurement. It is for the reader, and for you.

if_not: ""            # >= 5 words: what changes when the answer is no. Which
                      # field moves, which rung of the ladder you drop to, or
                      # that the contract does not get written. Not an escape
                      # hatch: without a named consequence there is no stake,
                      # and a spike with no stake is indistinguishable from a
                      # note you will not reread.

budget_minutes: 0     # > 0 and <= 480, one working day. The ceiling is a
                      # judgement call, not a perceptual fact like the latency
                      # bands. A question that needs longer is not de-risking
                      # a contract any more — write the contract instead, and
                      # let budgets.max_wallclock_minutes do the capping.

status: open          # open | answered | abandoned

finding: ""           # >= 5 words once answered or abandoned. The sentence you
                      # would say out loud. `abandoned` still costs you one —
                      # it is how an over-budget spike closes without anyone
                      # editing budget_minutes to fit what it actually cost.

measured: null        # The number, if there is one. Some findings are a fact
                      # rather than a figure ("the licence forbids it").

elapsed_minutes: 0    # What it really took, so the next budget is an estimate
                      # from evidence rather than from optimism.
---

# <slug>

## What I did

The cheapest test that could answer the question. Name the data, the tool and
the command, so somebody can re-run it without asking you.

## What I found

The number, and what it means for `informs`. If the answer was no, say what
`if_not` now obliges — and go and do it, or this record is decoration.

## What this is not

Not a run. No `start_run()`, no manifest, no `runs/` directory, nothing
promotable. A manifest carries a comparison — a baseline, an eval history, a
wallclock — and a spike has one measurement against one threshold. If this
starts to need a manifest, stop: what you are doing is an experiment, and it
needs a contract first.
