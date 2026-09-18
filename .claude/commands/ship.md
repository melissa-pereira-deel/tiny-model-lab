---
description: Export a promoted model to its target and wire it into a product surface.
---

Delegate to the `embedder` subagent for: $ARGUMENTS

Promote with `python -m harness ship <run-dir> <artifact>`. It refuses unless
every gate passes and the run strictly beats the current champion, and it is the
only thing that writes `champion/champion.json` and appends to `runs/LEDGER.md`.
A refusal is the answer, not an obstacle to route around.

Export via the path in the experiment's `target` field, verify numerically
against the source framework at every hop, and report the disagreement rate as a
number. Then write a `MODEL_CARD.md` from `harness/templates/MODEL_CARD.md`, stating
honestly what the model does not do.
