---
name: dataset-synthesis
description: Build training data for a tiny model using deterministic teachers, large-model labelling, and synthetic generation — with honest splits and label audits. Use when starting a tiny-model project, when labels are scarce or expensive, or whenever someone proposes hand-labelling a dataset.
---

# Dataset synthesis

For tiny models, data quality dominates data quantity. A 27KB model cannot memorise its way out of noisy labels.

## Source hierarchy

**1. Deterministic teacher — best.** An existing parser, linter, compiler, or rule engine that already produces correct labels. Free, consistent, unlimited. gpu-lexer trains against Shiki's TextMate scopes.

The reframe worth internalising: your "teacher" does not have to be a neural network. Any existing tool that solves the problem slowly, or largely, or only in some languages, is a label factory.

**2. Large-model teacher — good, audit it.** Prompt a capable model to generate inputs and labels at volume. Its errors are *systematic*, not random, and a tiny student will learn them faithfully. Audit before you train.

**3. Hand labels — reserve for verification.** Highest quality, lowest volume. Spend them on the held-out set, where quality matters and volume does not.

## Splits that do not lie

Split by the unit that generalisation has to cross:

- Code → by repository, never by file
- Users → by user
- Time series → by time, always forward
- Documents → by document, not by paragraph

Random splits leak. The resulting number is real in your notebook and fictional in production.

## Non-negotiables

- **Build the held-out set first, then do not look at it.** If you inspect it to debug, it is burned. Generate a fresh one and say so out loud.
- **Audit 20 examples by hand before every training run.** You will find label bugs. You always find label bugs.
- **Record provenance, gitignore the corpus.** Commit how the data was made, not the data.

## Reporting

State dataset size, split strategy, label source, and your honest estimate of label noise. If the teacher is a large model, name its failure modes — the student inherits them silently.
