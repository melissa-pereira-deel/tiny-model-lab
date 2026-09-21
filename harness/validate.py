"""Validate an experiment file before anything expensive happens.

Usage:  python -m harness validate experiments/my-task.yaml

This module keeps its own entry point, so `python -m harness.validate <path>`
still works. The dispatcher is the documented one, and it takes several paths.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .experiment import LATENCY_BANDS_MS, Experiment

# Names that mean "random split", however they are spelled. Deliberately short
# and openly incomplete: the check reads a label, not a split, so it can never
# catch a determined liar. Its job is to make the honest answer cost one
# sentence instead of costing a lie.
RANDOM_SPLIT_NAMES = frozenset(
    {"random", "randomly", "shuffle", "shuffled", "stratified", "index", "none", "n/a", "na"}
)


def _dataset_problems(dataset: dict[str, Any] | None) -> list[str]:
    """Check the one rule the experiment contract stated and never enforced.

    `harness/templates/experiment.yaml` has said `split_by: repo | user | time
    | document — NOT random` since the first commit, and `dataset-synthesis`
    explains why: a random split over correlated records measures memorisation
    and reports it as accuracy. Nothing checked it, and the repo's own worked
    example declared `split_by: "document"` for a corpus of independent
    generated strings — a random split wearing a legal name.
    """
    if not dataset:
        return [
            "dataset block is missing — say where the labels came from and how the "
            "split was drawn. It is the only part of this file that records whether "
            "the headline number is measurable in production or only in your notebook."
        ]

    problems: list[str] = []
    split_by = str(dataset.get("split_by") or "").strip()
    rationale = str(dataset.get("split_rationale") or "")

    if not split_by:
        problems.append(
            "dataset.split_by is empty — split by the unit generalisation has to "
            "cross (repo, user, time, document, dialect). If the records genuinely "
            "are independent and random is the honest answer, write "
            "split_by: random and argue for it in dataset.split_rationale."
        )
    elif split_by.lower() in RANDOM_SPLIT_NAMES and len(rationale.split()) < 5:
        problems.append(
            f"dataset.split_by is {split_by!r} with no dataset.split_rationale — a "
            "random split is allowed here, but it has to be argued for in a "
            "sentence: name the grouping unit that does not exist. "
            "examples/01-hello-tiny draws every example independently from a "
            "generator, so there is no document, user or repo for a leak to cross. "
            "This check reads a label, not a split, so it cannot tell an honest "
            "split_by from a flattering one — the sentence is for the reader."
        )

    holdout = dataset.get("holdout_size", 0)
    if not isinstance(holdout, (int, float)) or isinstance(holdout, bool) or holdout <= 0:
        problems.append(
            "dataset.holdout_size must be positive — build the held-out set first, "
            "then do not look at it. Zero means either the size went unrecorded or "
            "there is no held-out set, and the second one makes every number the "
            "run reports a training score."
        )
    return problems


def validate(path: str | Path) -> list[str]:
    problems: list[str] = []
    try:
        exp = Experiment.from_yaml(path)
    except Exception as err:  # noqa: BLE001 - surfacing the message is the point
        return [f"could not parse: {err}"]

    if exp.baseline.value == 0.0 and not exp.baseline.measured_at_runtime:
        problems.append(
            "baseline.value is 0.0 — measure the baseline before training the model, "
            "otherwise the comparison is decoration. If a runner measures it and "
            "assigns it before start_run(), as examples/01-hello-tiny/run.py does, "
            "declare that with baseline.measured_at_runtime: true. That is not a way "
            "out: the baseline gate refuses any run whose number never arrived."
        )
    if not exp.baseline.name.strip():
        problems.append("baseline.name is empty — name the specific thing you must beat")
    if exp.baseline.direction_is_ambiguous():
        problems.append(
            f"baseline.metric is {exp.baseline.metric!r} with no "
            "baseline.higher_is_better — a metric you minimise is fine here, but "
            "it has to be declared, because every gate otherwise assumes higher "
            "is better and would pass a model that scored WORSE than the "
            "baseline. Write higher_is_better: false and the comparison inverts; "
            "write true if the name is misleading and this really does go up. "
            "This check reads the metric's name, not the metric, so it cannot "
            "tell which you meant — the line is what tells it."
        )
    if not exp.kill_criteria:
        problems.append(
            "kill_criteria is empty — name at least one condition that would make you "
            "abandon this, before you are emotionally invested in it"
        )
    if exp.budgets.max_size_kb <= 0:
        problems.append("budgets.max_size_kb must be positive")
    if len(exp.hypothesis.split()) < 5:
        problems.append("hypothesis is too vague to falsify — write a sentence")
    if exp.budgets.latency_band not in LATENCY_BANDS_MS:
        problems.append(f"unknown latency_band {exp.budgets.latency_band!r}")
    problems.extend(_dataset_problems(exp.dataset))
    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    problems = validate(sys.argv[1])
    if problems:
        print(f"INVALID — {sys.argv[1]}")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"VALID — {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
