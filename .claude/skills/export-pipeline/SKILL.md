---
name: export-pipeline
description: Export a trained tiny model to its deployment target — ONNX and transformers.js for browsers, Core ML for Apple platforms, TFLite for embedded, or hand-written WGSL — with numerical verification at each hop. Use when a model is ready to ship, when choosing a training framework based on where it must run, or when converted-model accuracy looks wrong.
---

# Export pipeline

Choose the export path **before** choosing the training framework. This ordering prevents the most annoying failure in tiny-model work: a trained model you cannot ship.

## Paths

| Target | Route | State |
|---|---|---|
| Browser | PyTorch → ONNX → onnxruntime-web / transformers.js | Mature. WebGPU backend fast but verify numerically. |
| Apple native | PyTorch → coremltools | Supported and maintained. |
| Embedded / MCU | → LiteRT / TFLite Micro, via Edge Impulse or MediaPipe | Mature. |
| Maximum control | Hand-written WGSL compute shaders | Most work, smallest artifact. gpu-lexer's route. |
| Local LLM only | MLX → GGUF / Ollama | Fine if the artifact never leaves your machine. |

## The MLX caveat

MLX is excellent on Apple silicon and genuinely pleasant for local fine-tuning. It has **no first-class converter to Core ML or ONNX** — the coremltools issue tracking this has been open since March 2025.

So: if the artifact must ship to a browser or a cross-platform target, **train in PyTorch with the MPS backend** and keep the export path clean. Use MLX when the model stays local, or when you plan to hand-write the forward pass and only need the weights.

Also: training tiny models on MPS is fine, serving from MPS is not. Do not plan production inference there.

## Verify at every hop

After each conversion, run the same held-out set through the converted model and compare against the source framework. **Report the disagreement rate as a number.**

A conversion that silently changes 2% of predictions is a real bug with no exception attached. It surfaces in production, as a user complaint, weeks later.

## Browser specifics

- Run inference in a **Web Worker**. The main thread belongs to the interaction.
- Verify the **WebGPU backend against WASM** before trusting it; correctness issues on some op sets are real and silent.
- Measure on **target hardware**. Integrated GPUs behave differently from discrete ones, and benchmarks from your Mac Studio say nothing about a mid-range laptop.
- Budget the **first-run download** as a design problem, not a footnote.
