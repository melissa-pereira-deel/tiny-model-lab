---
description: Run one experiment from an experiment.yaml — baseline first, then the model, gated throughout.
---

Run the experiment defined at: $ARGUMENTS

Delegate to the `trainer` subagent. Enforce this order:

1. Verify the experiment file (`python -m harness validate <path>`). A file whose baseline is measured by the runner must say `measured_at_runtime: true`; validate accepts that, and the baseline gate later refuses a number that never arrives. It also checks the split: `dataset.split_by` must name the unit generalisation has to cross, and a random split needs `dataset.split_rationale` to say why nothing leaks. Neither flag is an exemption — both cost you a sentence you have to mean.
2. Measure and record the **baseline** before anything else is trained.
3. `start_run()` to create the run directory and manifest.
4. Train the simplest model that could work.
5. After every eval: `record_eval()`, then run the gates.
6. Stop on any gate failure and follow its remediation rather than improvising.

Report a summary with numbers, not a training log.
