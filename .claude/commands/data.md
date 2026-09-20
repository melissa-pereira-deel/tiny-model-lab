---
description: Build and audit the dataset for an experiment — teacher labelling, an untouchable held-out split, a label audit.
---

Delegate to the `data-builder` subagent for: $ARGUMENTS

This is step 2 of five. `/scope` has already written the experiment file; this
fills in the half of it that decides whether any later number means anything.

1. **Read the `dataset` block in the experiment file first.** It is the
   contract, and `python -m harness validate` enforces it: `split_by` must name
   the unit generalisation has to cross, and a random split is only accepted
   with a written `split_rationale` saying why nothing leaks. Decide the split
   before you generate anything, because deciding it afterwards means deciding
   it from the numbers.
2. **Build the held-out set first, then do not look at it.** If you inspect it
   to debug, it is burned — generate a fresh one and say so out loud.
3. **Work down the source hierarchy**: deterministic teacher, then large-model
   teacher, then hand labels. A parser, linter or compiler that already solves
   the problem slowly is a label factory. Reserve hand labels for the held-out
   set, where quality matters and volume does not.
4. **Audit 20 examples by hand before anything is trained.** Every time. You
   will find label bugs, and no metric would have surfaced them until much
   later and much more expensively. Record it as
   `experiments/<slug>-label-audit.spike.md` with `informs: dataset.teacher`,
   so what you checked and what you found outlive the session.
5. **Record provenance in the experiment file, gitignore the corpus.** Fill in
   `source`, `teacher`, `size` and `holdout_size` with what you actually did,
   not what was planned.
6. **Finish by running `python -m harness validate <path>`.** If it refuses, the
   dataset block does not describe a split anyone can trust yet.

Report the size, the split strategy, the label source, and your honest estimate
of label noise. If the teacher is a large model, name its failure modes — the
student inherits them silently.

If the task cannot be labelled cheaply, stop and say so. That is a triage
failure, and catching it here costs an afternoon instead of three days.
