---
name: architecture-selection
description: Choose an architecture and input representation for a narrow task — classical baselines, CNNs, GRUs, tiny transformers, and the representation design that matters more than any of them. Use when starting a tiny-model experiment, when a model has plateaued, or whenever someone reaches for a transformer by default.
---

# Architecture and representation

The representation is the product. Most of the win in a tiny model comes from framing the input so the task becomes easy — not from the model.

## Representation first

gpu-lexer is the reference case. Instead of tokenising per language, a CPU pass splits text into word runs, whitespace, newlines, and symbols, then records language-neutral features: part kind, length, edge characters, hashes, neighbouring symbol pairs. Only then does a model embed those sparse features into learned channels. The cleverness is upstream of the network.

Before touching architecture, ask:

- What structure does the data actually have — locality, order, symmetry, hierarchy?
- What can a deterministic pass compute for free, so the model does not have to learn it?
- What can be removed from the input without hurting the task? Smaller input, smaller model.

Spending a day here routinely beats a week of hyperparameter tuning.

## Inductive-bias ladder

Pick the weakest thing that fits the structure. Stronger bias means less data and fewer parameters.

| Structure in the data | Reach for |
|---|---|
| Independent features, tabular | Logistic regression, then gradient-boosted trees |
| Local / spatial / translation-invariant | 1D or 2D convolutions |
| Sequential, modest range | GRU, or convolutions plus a scan |
| Long-range, content-dependent pairing | Attention — and only here |

Gradient-boosted trees still beat neural networks on most tabular problems. They are also the fastest thing to try. Note their inference latency is often *higher* than a small network's, which matters if you are targeting the instant band.

## On the bitter lesson

Sutton's argument is that general methods leveraging computation beat handcrafted structure. At tiny scale with narrow tasks and little data, you are in the opposite regime — for now.

The useful distinction (Cranmer): bake in inductive biases grounded in the **mathematical structure of the data** — locality, symmetry, invariance. Do not bake in **arbitrary human heuristics** about how the task ought to be solved. The first kind ages well; the second becomes the ceiling.

Hyung Won Chung's framing is the one to hold: add the structure your current compute and data require, and plan to remove it later, because it will eventually bottleneck you.

## Hybrids are usually right

gpu-lexer and JPU both pair a learned classifier with a deterministic composition step that guarantees valid output structure. Let the model handle the fuzzy part and let code enforce the invariants. You get learned flexibility without learned nonsense.
