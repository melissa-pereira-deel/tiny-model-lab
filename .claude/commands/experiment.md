---
description: Run one experiment from an experiment.yaml — baseline first, then the model, gated throughout.
---

Run the experiment defined at: $ARGUMENTS

Delegate to the `trainer` subagent. Enforce this order:

1. Verify the experiment file parses (`python -m harness.validate <path>`).
2. Train and record the **baseline** if it has no measured number yet.
3. `start_run()` to create the run directory and manifest.
4. Train the simplest model that could work.
5. After every eval: `record_eval()`, then run the gates.
6. Stop on any gate failure and follow its remediation rather than improvising.

Report a summary with numbers, not a training log.
