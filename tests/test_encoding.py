"""Output has to survive a console that is not UTF-8.

Found by adding `windows-latest` to CI (#11). The worked example died with
`UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'` before
printing a single gate — a real bug for a Windows user, not a CI artefact.

Two separate fixes, because they are two separate mistakes:

- `gates.py` returned a U+2192 arrow. That is a *library* handing its caller a
  string the caller may not be able to print. It is ASCII now.
- The programs inherited the locale encoding. They declare UTF-8 now. Measured:
  before that, the em dashes alone broke cp932, koi8-r and ascii.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = REPO_ROOT / "examples" / "01-hello-tiny" / "run.py"

# cp1252 is what a default Windows console uses and is where this was found.
# The others are legacy encodings that the em dash alone was enough to break.
HOSTILE_ENCODINGS = ["cp1252", "cp932", "koi8-r", "ascii"]


def run(args: list[str], encoding: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("encoding", HOSTILE_ENCODINGS)
def test_the_worked_example_runs(encoding: str) -> None:
    """The README promises this takes a second and works. On any console."""
    proc = run([str(EXAMPLE)], encoding)
    assert proc.returncode == 0, f"{encoding}: {proc.stderr.strip().splitlines()[-1:]}"
    assert "UnicodeEncodeError" not in proc.stderr


@pytest.mark.parametrize("encoding", HOSTILE_ENCODINGS)
def test_the_cli_runs(encoding: str) -> None:
    spec = "examples/01-hello-tiny/experiment.yaml"
    proc = run(["-m", "harness", "validate", spec], encoding)
    assert proc.returncode == 0, f"{encoding}: {proc.stderr.strip().splitlines()[-1:]}"
    assert "UnicodeEncodeError" not in proc.stderr


def test_gate_output_is_ascii() -> None:
    """The library half, checked at the source rather than through a console.

    A failing gate is the case that matters: the arrow only appeared in the
    remediation line, so a suite that never failed a gate would never see it.
    """
    from harness.experiment import Baseline, Budgets, Experiment
    from harness.gates import run_all

    exp = Experiment(
        task="t",
        hypothesis="a tiny model can beat the regex tagger on unseen formats",
        baseline=Baseline(kind="deterministic", name="regex", metric="accuracy", value=0.9),
        budgets=Budgets(max_size_kb=1, latency_band="instant"),
    )
    passed, results = run_all(
        exp,
        candidate_value=0.1,   # loses, so every remediation is rendered
        size_kb=999.0,
        p95_ms=9999.0,
        eval_history=[0.1],
        elapsed_minutes=99999.0,
    )
    assert not passed, "this fixture is meant to fail every gate"
    rendered = "\n".join(str(r) for r in results)
    offenders = sorted({c for c in rendered if ord(c) > 127})
    assert not offenders, f"gate output must be ASCII, found {offenders}"
