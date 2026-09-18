---
name: quantization-strategy
description: Decide between post-training quantization and quantization-aware training, pick a bit width, and compress a model to fit a size budget without silently destroying accuracy. Use when a model is over its size budget, when targeting sub-8-bit weights, or before any export to a browser or embedded target.
---

# Quantization strategy

Quantization is storing weights at lower precision. Think of it as choosing how many decimal places to keep: at some point the number is still useful, and a little past that it is not.

## The decision

| Bit width | Method | Expect |
|---|---|---|
| int8 | Post-training (PTQ) | Usually near-lossless. Try this first, it takes minutes. |
| int6 | QAT strongly preferred | Workable with training-time simulation. gpu-lexer ships int6. |
| int4 and below | QAT required | PTQ degrades badly here. Budget for retraining. |

**PTQ** quantizes an already-trained model. Cheap, immediate, and the right first attempt.

**QAT** simulates quantization during training, so the model learns weights that survive it. It uses a straight-through estimator to keep gradients flowing through the non-differentiable rounding step. Costs a retrain, holds up at 4 bits and below.

## Order of operations

1. Measure the exported artifact size. Not parameters — bytes on disk, summing directories for `.mlpackage` or split ONNX.
2. If over budget, try PTQ int8 first.
3. Still over: QAT at the next width down.
4. Still over: reduce width or depth, then prune.
5. **Re-run the baseline gate after every step.** Compression that breaks accuracy is not a win, and it is easy to miss because the size number moves in the direction you wanted.

## The trap

Quantization failures are quiet. The model loads, runs, produces plausible output, and is worse in a way no exception surfaces. Always compare the quantized model against the full-precision one on the same held-out set and report the disagreement rate as a number.
