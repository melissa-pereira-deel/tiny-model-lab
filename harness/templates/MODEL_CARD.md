# Model card: <name>

## What it does
One sentence. The narrow task, stated plainly.

## What it does not do
Be specific and generous here. This section is the reason model cards exist.

## Numbers

| | |
|---|---|
| Size (shipped bytes) | |
| p95 latency (warm, target hw) | |
| Cold start | |
| Metric vs baseline | |
| Baseline it beats | |
| Disagreement vs source framework | |
| Disagreement vs full precision | |

The two disagreement rows are the number `export-pipeline`, `quantization-strategy`
and the `embedder` subagent all ask for: how often the converted or quantized
artifact picks a different answer than the thing it came from, on the same
held-out set. No threshold is prescribed anywhere in this repo — report it,
say what you think it means, and do not invent a pass mark.

## What the metric actually measures
State the comparison honestly. If you measure agreement with a teacher tool,
say so — agreement with a teacher is not objective correctness, and the
difference matters to anyone deciding whether to trust this.

## Training data
Source, teacher, split strategy, size, known label noise.

## Failure modes
Where it is wrong, and what wrong looks like in the interface.

## Intended deployment
Target runtime, hardware assumed, what happens when unavailable.

## Privacy
What leaves the device. Ideally: nothing. Say it plainly.
