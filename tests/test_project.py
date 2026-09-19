"""Tests for project resolution and promotion.

Both exist because of one old line: `REPO_ROOT = Path(__file__).parent.parent`.
Resolved at import from the *package's* location, it meant a normal
`pip install` wrote your run history into site-packages, and it meant no test
could ever exercise `promote()` without dirtying the working tree — so the one
branch that mutates `champion/` and the ledger had never been run.
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

import pytest

from harness.experiment import (
    Experiment,
    project_root,
    record_eval,
    runs_root,
    start_run,
)
from harness.promote import evaluate_promotion, promote

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_SPEC = REPO_ROOT / "examples" / "01-hello-tiny" / "experiment.yaml"


@pytest.fixture
def somewhere_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project directory that is not this repo, and is the working directory."""
    (tmp_path / "experiments").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TINY_MODEL_LAB_ROOT", raising=False)
    return tmp_path


def winning_run(runs_dir: Path) -> Path:
    """A run that clears every gate, so promotion is actually reachable."""
    exp = Experiment.from_yaml(EXAMPLE_SPEC)
    exp.baseline.value = 0.50
    exp.budgets.max_size_kb = 1000
    run_dir = start_run(exp, runs_dir=runs_dir)
    record_eval(
        run_dir, variant="v1", metric_value=0.91,
        size_kb=3.0, p95_ms=2.0, elapsed_minutes=0.2,
    )
    return run_dir


class TestProjectRoot:
    def test_env_var_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TINY_MODEL_LAB_ROOT", str(tmp_path))
        assert project_root() == tmp_path.resolve()

    def test_finds_the_nearest_experiments_marker(self, somewhere_else: Path) -> None:
        assert project_root() == somewhere_else.resolve()

    def test_walks_up_from_a_subdirectory(
        self, somewhere_else: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """You should be able to run from src/ and still land on the project."""
        nested = somewhere_else / "src" / "deep"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert project_root() == somewhere_else.resolve()

    def test_falls_back_to_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TINY_MODEL_LAB_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        assert project_root() == tmp_path.resolve()

    def test_runs_land_in_the_project_not_the_package(self, somewhere_else: Path) -> None:
        """The whole point: a pip-installed harness must not write to site-packages."""
        assert runs_root() == somewhere_else.resolve() / "runs"
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        run_dir = start_run(exp)
        assert somewhere_else.resolve() in run_dir.resolve().parents

        package_dir = Path(__import__("harness").__file__).resolve().parent
        assert not (package_dir / "runs").exists()
        assert not (package_dir.parent / "champion").exists()


class TestPromotion:
    """The branch that had never been executed by any test."""

    def test_promotes_a_run_that_clears_every_gate(self, tmp_path: Path) -> None:
        champion = tmp_path / "champion"
        ledger = tmp_path / "LEDGER.md"
        run_dir = winning_run(tmp_path / "runs")
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"not really a model")

        result = promote(run_dir, artifact, champion_dir=champion, ledger=ledger)

        assert result.startswith("PROMOTED"), result
        assert (champion / "model.onnx").exists()
        card = json.loads((champion / "champion.json").read_text())
        assert card["metric_value"] == 0.91
        assert card["beats_baseline"]
        assert "0.9100" in ledger.read_text()

    def test_promotion_writes_nothing_into_this_repo(self, tmp_path: Path) -> None:
        """AGENTS.md says champion/ changes only via promote(). A test must not."""
        run_dir = winning_run(tmp_path / "runs")
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"x")
        promote(run_dir, artifact, champion_dir=tmp_path / "champion", ledger=tmp_path / "L.md")

        assert not (REPO_ROOT / "champion").exists()
        assert not (REPO_ROOT / "runs" / "LEDGER.md").exists()

    def test_a_tie_keeps_the_incumbent(self, tmp_path: Path) -> None:
        """Strict improvement, the same rule the baseline gate uses."""
        champion = tmp_path / "champion"
        champion.mkdir()
        (champion / "champion.json").write_text(json.dumps({"metric_value": 0.91}))

        run_dir = winning_run(tmp_path / "runs")  # also 0.91
        ok, reason = evaluate_promotion(run_dir, champion_dir=champion)
        assert not ok
        assert "tie keeps the incumbent" in reason

    def test_refuses_a_run_that_fails_a_gate(self, tmp_path: Path) -> None:
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.value = 0.99
        run_dir = start_run(exp, runs_dir=tmp_path / "runs")
        record_eval(
            run_dir, variant="v1", metric_value=0.10,
            size_kb=1.0, p95_ms=1.0, elapsed_minutes=0.1,
        )
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"x")

        result = promote(run_dir, artifact, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md")
        assert result.startswith("REFUSED")
        assert not (tmp_path / "c").exists()


class TestPackaging:
    def test_version_is_declared_in_exactly_one_place(self) -> None:
        """pyproject declares `dynamic = ["version"]` and reads __version__.

        The two cannot drift by construction, which is the fix. This test
        catches the dynamic config silently breaking instead — a literal
        creeping back into pyproject would show up as installed metadata
        disagreeing with the source.
        """
        import harness

        try:
            installed = metadata.version("tiny-model-lab")
        except metadata.PackageNotFoundError:
            pytest.skip("package not installed, so there is no metadata to compare")
        assert installed == harness.__version__
