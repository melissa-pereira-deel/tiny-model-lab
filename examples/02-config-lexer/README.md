# 02 — config lexer

Takes about a minute and needs the heavy extras. Example 01 is the one-second,
dependency-free version; this is the one that trains a real model and ships it
through the whole pipeline.

```bash
pip install -e ".[train]" onnx onnxruntime
python examples/02-config-lexer/run.py
```

## What it shows

The half of the loop 01 never reaches: **PyTorch → ONNX → onnxruntime**, with the
artifact measured in bytes on disk, the conversion verified numerically, int8
quantization applied and measured, and a model card written at the end.

The export happens *inside* the eval loop rather than after promotion, because
`size_gate` measures the exported artifact and not a parameter count. So the
export path is exercised whichever way the baseline gate goes — which matters
here, because the baseline won.

## The result, which is not the one the hypothesis predicted

The task: label a config-file line as comment / section / key / value. The
baseline is a regex rule set written against three dialects — `ini`, `env`,
`make` — and scored on two it had never seen, `toml_ish` and `yaml_ish`. It gets
**1.0000** on its own dialects and **0.8750** on the held-out ones.

`experiment.yaml` predicted that a conv over **character classes** would beat it,
because such a model never learns *which byte* is the separator, only that there
is one and whether anything follows it — so it should transfer to a dialect that
assigns with `:` instead of `=`.

Half of that was right. The class representation does exactly what was predicted
on values: yaml_ish `path: none` goes from **0.317** correct under the literal
representation to **1.000** under classes.

The other half was wrong, and it is the interesting part. Collapsing characters
into classes destroys a distinction the task needs. In `make`, a section header
is `build:` and a key is `CFLAGS :=` — under a class encoding both are *alpha,
separator, nothing after*. Section accuracy falls to roughly 0.58, and the model
cannot even fit the training dialects (0.9510). The richer representation bought
transfer on one label and paid for it on another.

| variant | held-out accuracy | ONNX size | p95 |
|---|---|---|---|
| baseline (regex rules) | **0.8750** | 0 bytes | — |
| conv over raw characters | 0.7892 | 8.4 KB | 0.0 ms |
| conv over character classes | 0.7658 | 5.3 KB | 0.0 ms |
| raw characters, int8 | 0.7892 | 4.9 KB | 0.1 ms |

*One run on one machine. The numbers move a little between machines and torch
versions; the shape does not.*

So the kill criterion written into `experiment.yaml` before any of this ran —
*"neither representation beats the rule set on the held-out dialects"* — fired,
and the run stops there. No hill-climbing past a stop condition to reach a nicer
number.

Note the raw model fits the training dialects at **1.0000**. This is a
generalisation gap, not an undertrained model, which is what makes it worth
reporting rather than fixing.

## What to look at

- `experiment.yaml` — the contract, including a hypothesis that turned out to be
  wrong. It has not been edited to match the outcome.
- `baseline.py` — written against the three training dialects and not touched
  afterwards. A baseline chosen to be weak makes the comparison decoration.
- the two disagreement rates — **0.0000** torch-vs-ONNX, so the conversion is
  exact here, and **0.0013** fp32-vs-int8, the price of halving the artifact.
  Three files in this repo demand that number; none of them names an acceptable
  value, so it is reported and not judged.
- `runs/<timestamp>--*/artifacts/*.onnx` — real bytes, which is what the size
  gate reads. Gitignored, like every artifact.
- `runs/<timestamp>--*/MODEL_CARD.md` — generated from the template.
- the promotion line: `REFUSED`, because the gates failed. That is the machinery
  working, not a bug.

## Honest limits

**The data is synthetic.** The generator in `dialects.py` is the ground truth by
construction, so there is no label noise — and equally, these numbers
demonstrate a mechanism rather than telling you anything about real config
files. A real corpus would be more convincing and would make the example depend
on a download.

**A headless example cannot answer the design questions.** `export-pipeline`
also asks for inference in a Web Worker, the WebGPU backend verified against
WASM, and measurement on target hardware. The five `design-eval` checks —
failure state, uncertainty legibility, user override, privacy legibility,
first-run cost — are all about a user interface. A `run.py` has none. They are
not covered here, and this example does not pretend otherwise.

**The opset is a choice, not a prescription.** Nothing in this repo specifies an
ONNX opset version, a runtime version, or an acceptable disagreement rate. The
opset is pinned at 17 in `run.py` so the artifact is reproducible; that number
came from me, not from the docs.

## The lesson

01's lesson was that an impoverished representation is a ceiling no amount of
data lifts. This one is the other edge of the same knife: a representation
chosen to generalise can quietly delete information the task depends on. Both
runs end with the baseline shipping, which is what the ladder in the README
predicts for most tasks that sound like tiny models.
