"""Tests for .gitignore.

The recurring failure in this repo is a documented rule with nothing enforcing
it — `split_by` (#15), the metric's direction (#23), the artifact's size (#24).
An ignore rule is the same kind of thing: a comment saying what should not be
committed, and nothing that notices when it stops being true.

This one stopped being true silently. `champion/*.onnx` contains a slash, so git
anchors it to the repo root; it never reached `examples/*/champion/`, and
nothing matched `champion.json` or `LEDGER.md` anywhere. A successful promotion
inside `examples/02-config-lexer` would have left three untracked files and
failed CI's clean-tree check (#28) — on a day when the interesting news was that
the model had finally won.

These ask git, rather than reading the patterns and reasoning about them. The
reasoning is what was wrong.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="asks git about its own rules")


def is_ignored(path: str) -> bool:
    """Would git ignore this path? Asked of git, not inferred from the file.

    `-q` rather than `-v`, and the difference is not cosmetic: with `-v`, git
    reports *any* matching pattern including a negation, so `runs/LEDGER.md`
    exits 0 while being emphatically not ignored. `-q` answers the question
    actually being asked.

    `--no-index` because none of these paths exist on disk — they are the files
    a promotion *would* write.

    Exit 0 is ignored and 1 is not; anything else (128: no repo, no git) is an
    error and must not be reported as `False`. A helper that answered "not
    ignored" when it could not tell would make every assertion below pass
    vacuously in exactly the situation it cannot see.
    """
    proc = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode not in (0, 1):
        pytest.skip(f"git could not answer for {path!r}: rc={proc.returncode} {proc.stderr.strip()}")
    return proc.returncode == 0


# Everything promote() writes: the copied artifact, the card, the ledger.
# `harness/promote.py` creates all three under whatever champion_dir it is given.
PROMOTION_OUTPUT = ("conv-raw-chars-int8.onnx", "model.mlpackage/weights.bin", "champion.json",
                    "LEDGER.md")


class TestExampleOutputIsIgnored:
    """An example's promotion output is output, not this repo's decision trail."""

    @pytest.mark.parametrize("example", ["01-hello-tiny", "02-config-lexer"])
    @pytest.mark.parametrize("filename", PROMOTION_OUTPUT)
    def test_a_promotion_inside_an_example_leaves_nothing_untracked(
        self, example: str, filename: str
    ) -> None:
        """This is CI's clean-tree check, asked ahead of time.

        01 has no promotion step today, so its half is latent — which is
        precisely the state 02's half was in when it was filed.
        """
        assert is_ignored(f"examples/{example}/champion/{filename}")

    @pytest.mark.parametrize("filename", ["manifest.json", "MODEL_CARD.md", "artifacts/m.onnx"])
    def test_run_output_stays_ignored_too(self, filename: str) -> None:
        """The neighbouring rule, so a rewrite of one cannot quietly drop the
        other. Note `manifest.json` is ignored here and kept at the root: the
        `!runs/*/manifest.json` negation is root-anchored and deliberately does
        not reach an example."""
        assert is_ignored(f"examples/02-config-lexer/runs/r1/{filename}")


class TestTheRootDecisionTrailIsNot:
    """The half that matters.

    The obvious way to close #28 is to broaden `champion/*.onnx` to
    `**/champion/*.onnx`, or to ignore `champion/` outright. Either would also
    stop tracking the repo's own champion card and ledger, which are the record
    of what was ever actually best — and nothing would have said so.
    """

    @pytest.mark.parametrize("path", ["champion/champion.json", "champion/LEDGER.md"])
    def test_the_champion_card_and_ledger_are_committed(self, path: str) -> None:
        assert not is_ignored(path), (
            f"{path} must stay tracked — it is the decision trail, not an artifact. "
            "If a rule was just widened to cover examples/*/champion/, it reached "
            "too far."
        )

    @pytest.mark.parametrize("path", ["runs/LEDGER.md", "runs/SESSIONS.md",
                                      "runs/20260101T000000Z--task/manifest.json"])
    def test_the_run_provenance_is_committed(self, path: str) -> None:
        assert not is_ignored(path)

    @pytest.mark.parametrize("path", ["champion/model.onnx", "champion/model.safetensors",
                                      "runs/20260101T000000Z--task/artifacts/model.onnx",
                                      "runs/20260101T000000Z--task/checkpoints/epoch3.bin"])
    def test_the_bytes_are_not(self, path: str) -> None:
        """The other side of line 1: provenance is committed, bytes are not."""
        assert is_ignored(path)


def test_the_helper_can_tell_the_two_apart() -> None:
    """Guards everything above.

    Every assertion here is `is_ignored(...)` or its negation, so a helper stuck
    on one answer would make half this file pass for the wrong reason. A tracked
    file that plainly is not ignored, and a `.pyc` that plainly is.
    """
    assert not is_ignored("README.md")
    assert is_ignored("harness/__pycache__/promote.cpython-314.pyc")
