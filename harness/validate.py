"""Validate an experiment file before anything expensive happens.

Usage:  python -m harness.validate experiments/my-task.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

from .experiment import LATENCY_BANDS_MS, Experiment


def validate(path: str | Path) -> list[str]:
    problems: list[str] = []
    try:
        exp = Experiment.from_yaml(path)
    except Exception as err:  # noqa: BLE001 - surfacing the message is the point
        return [f"could not parse: {err}"]

    if exp.baseline.value == 0.0:
        problems.append(
            "baseline.value is 0.0 — measure the baseline before training the model, "
            "otherwise the comparison is decoration. (If 0.0 is genuinely the measured "
            "value, set it from a script at runtime as examples/01-hello-tiny does.)"
        )
    if not exp.baseline.name.strip():
        problems.append("baseline.name is empty — name the specific thing you must beat")
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
