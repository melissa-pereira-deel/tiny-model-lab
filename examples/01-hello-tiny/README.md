# 01 — hello tiny

Runs in about a second. No ML dependencies.

```bash
python examples/01-hello-tiny/run.py
```

## What it shows

The full shape of a gated experiment: measure the baseline, start a run, train,
evaluate, gate, record. And it ends with the outcome nobody plans for and
everybody eventually gets — **the baseline wins, so the baseline ships.**

That is not a failed example. It is the single most valuable thing this harness
does. Without a baseline gate you would have looked at 0.92 accuracy, felt good,
and shipped a model that was worse than four lines of `if` statements.

## What to look at

- `experiment.yaml` — the contract, including `kill_criteria` written before any training, and `measured_at_runtime: true` because `run.py` measures the baseline on the held-out split rather than hard-coding it
- the gate output — note that `baseline` fails while `size` and `latency` pass; a model can pass every technical budget and still be the wrong thing to ship
- `runs/<timestamp>--*/manifest.json` — the provenance trail that survives the session
- the accuracy/size/latency table — the real deliverable of a tiny-model project is the curve, not a single number

## The lesson about representation

The model only sees the **first character**. That impoverished representation is
its ceiling, and no amount of extra data or parameters moves it — notice the
accuracy barely changes from 250 to 4000 examples.

This is the point of the `architecture-selection` skill: when a tiny model
plateaus, reach for the input representation, not the hyperparameters.
