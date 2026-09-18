---
description: Export a promoted model to its target and wire it into a product surface.
---

Delegate to the `embedder` subagent for: $ARGUMENTS

Refuse if the run has not been promoted — check `champion/champion.json`.

Export via the path in the experiment's `target` field, verify numerically
against the source framework at every hop, and report the disagreement rate as a
number. Then write a `MODEL_CARD.md` from `templates/MODEL_CARD.md`, stating
honestly what the model does not do.
