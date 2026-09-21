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

    def test_the_author_is_spelled_one_way(self) -> None:
        """#22: LICENSE, pyproject and the README footer disagreed for months.

        Unlike the version above, these three cannot be made to agree by
        construction -- a name is a literal in each file, and there is nowhere
        sensible to put the single copy. So this is a sensor instead, and the
        second half is the one that earns its place: a rename that stops
        halfway leaves the old spelling somewhere, and nothing else in this
        repo would notice.

        It cannot reach harmonic-parser, which copied LICENSE verbatim and is
        a different repository. That one is kept in step by hand.
        """
        author = "Melissa de Britto"
        superseded = "Melissa Pereira"
        for name in ("LICENSE", "pyproject.toml", "README.md"):
            text = (REPO_ROOT / name).read_text()
            assert author in text, f"{name} does not name the author as {author!r}"
            assert superseded not in text, (
                f"{name} still carries the superseded spelling {superseded!r}. "
                "The GitHub org slug melissa-pereira-deel is a handle and is "
                "spelled differently, so it does not trip this."
            )


class TestPromotionDirection:
    """#23's most expensive half: the champion comparison running backwards.

    A single gate comparing the wrong way loses one run. `evaluate_promotion`
    comparing the wrong way installs a worse incumbent every time, and the
    ledger records each one as an improvement.
    """

    def losing_run(self, runs_dir: Path, **baseline) -> Path:
        """Perplexity 2.40 against a baseline of 2.10 — genuinely worse."""
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.metric = "perplexity"
        exp.baseline.value = 2.10
        exp.budgets.max_size_kb = 1000
        for key, value in baseline.items():
            setattr(exp.baseline, key, value)
        run_dir = start_run(exp, runs_dir=runs_dir)
        record_eval(
            run_dir, variant="v1", metric_value=2.40,
            size_kb=3.0, p95_ms=2.0, elapsed_minutes=0.2,
        )
        return run_dir

    def test_a_worse_loss_is_refused_when_the_contract_says_so(
        self, tmp_path: Path
    ) -> None:
        """The bug, from the other end. 2.40 is worse perplexity than 2.10, and
        before the contract carried a direction this promoted."""
        run_dir = self.losing_run(tmp_path / "runs", higher_is_better=False)
        ok, message = evaluate_promotion(run_dir, champion_dir=tmp_path / "champion")
        assert not ok
        assert "gates failed" in message

    def test_an_undeclared_loss_is_refused_before_it_can_promote(
        self, tmp_path: Path
    ) -> None:
        run_dir = self.losing_run(tmp_path / "runs")
        ok, message = evaluate_promotion(run_dir, champion_dir=tmp_path / "champion")
        assert not ok
        assert "higher_is_better" in message

    def test_the_champion_comparison_reads_the_contract(self, tmp_path: Path) -> None:
        """With an incumbent at 2.00, a run at 2.40 must lose on a loss metric.

        This is the comparison that is not a gate, so it needs its own cover:
        `evaluate_promotion` resolves direction separately from `run_all`.
        """
        champion = tmp_path / "champion"
        champion.mkdir()
        (champion / "champion.json").write_text(
            json.dumps({"run_id": "earlier", "metric_value": 2.00, "metric": "perplexity"})
        )
        # This run beats its own baseline (2.40 < 2.10 is false, so widen it)
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.metric = "perplexity"
        exp.baseline.value = 3.00
        exp.baseline.higher_is_better = False
        exp.budgets.max_size_kb = 1000
        run_dir = start_run(exp, runs_dir=tmp_path / "runs")
        record_eval(
            run_dir, variant="v1", metric_value=2.40,
            size_kb=3.0, p95_ms=2.0, elapsed_minutes=0.2,
        )

        ok, message = evaluate_promotion(run_dir, champion_dir=champion)
        assert not ok, message
        assert "champion not beaten" in message


class TestMeasuredSize:
    """#24: the size gate compares the bytes being shipped, not the claim.

    Its sibling, #23, was 'the gate compares the wrong way round'. This one is
    'the gate compares against a number nobody checked'. Together they are the
    two ways the promotion path can pass something it should not, and this is
    the half where the harness can actually check the answer against the world
    -- accuracy and p95 are gone once a run ends, and the artifact is not.
    """

    def run_claiming(self, runs_dir: Path, claimed_kb: float, budget_kb: float = 50) -> Path:
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.value = 0.50
        exp.budgets.max_size_kb = budget_kb
        run_dir = start_run(exp, runs_dir=runs_dir)
        record_eval(
            run_dir, variant="v1", metric_value=0.99,
            size_kb=claimed_kb, p95_ms=1.0, elapsed_minutes=0.1,
        )
        return run_dir

    def test_the_issue_as_filed(self, tmp_path: Path) -> None:
        """Gate on a self-reported 1 KB, ship 4 MB. This used to promote."""
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        big = tmp_path / "big.bin"
        big.write_bytes(b"\0" * 4_000_000)

        result = promote(
            run_dir, big, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md"
        )

        assert result.startswith("REFUSED"), result
        assert "3906.2 KB vs budget 50.0 KB" in result
        assert not (tmp_path / "c").exists()

    def test_the_refusal_is_the_ordinary_one(self, tmp_path: Path) -> None:
        """An oversized artifact is over budget, not a special kind of lie.

        Deliberate: the remediation for 4 MB against a 50 KB budget really is
        'quantize, then prune'. Inventing a second failure mode for it would
        have meant inventing a tolerance to separate the two.
        """
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        big = tmp_path / "big.bin"
        big.write_bytes(b"\0" * 4_000_000)

        result = promote(
            run_dir, big, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md"
        )
        assert "post-training quantization" in result

    def test_a_discrepancy_inside_the_budget_still_promotes(self, tmp_path: Path) -> None:
        """40 KB claimed as 1 KB, against a 50 KB budget.

        The bytes fit the budget and the budget is what the contract is about.
        Refusing this would need a threshold on the gap between the two
        numbers, and nobody has measured one.
        """
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"\0" * 40_960)

        champion = tmp_path / "c"
        result = promote(run_dir, artifact, champion_dir=champion, ledger=tmp_path / "L.md")

        assert result.startswith("PROMOTED"), result
        card = json.loads((champion / "champion.json").read_text())
        assert card["size_kb"] == 40.0
        assert card["size_kb_reported"] == 1.0

    def test_the_ledger_records_the_measured_number(self, tmp_path: Path) -> None:
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"\0" * 40_960)
        ledger = tmp_path / "L.md"

        promote(run_dir, artifact, champion_dir=tmp_path / "c", ledger=ledger)

        assert "40.0 KB" in ledger.read_text()
        assert "1.0 KB" not in ledger.read_text()

    def test_both_numbers_are_in_the_report(self, tmp_path: Path) -> None:
        """Printed on a pass too. A line that only appears on a mismatch is one
        a reader can conclude nothing from when it is absent."""
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"\0" * 40_960)

        ok, message = evaluate_promotion(
            run_dir, artifact=artifact, champion_dir=tmp_path / "c"
        )
        assert ok, message
        assert "artifact 40.0 KB on disk" in message
        assert "the manifest recorded 1.0 KB" in message

    def test_a_directory_artifact_sums_the_tree(self, tmp_path: Path) -> None:
        """A .mlpackage or a split ONNX model is a directory, and what the user
        downloads is all of it."""
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        bundle = tmp_path / "model.mlpackage"
        (bundle / "weights").mkdir(parents=True)
        (bundle / "weights" / "w.bin").write_bytes(b"\0" * 20_480)
        (bundle / "meta.json").write_bytes(b"\0" * 1_024)

        champion = tmp_path / "c"
        result = promote(run_dir, bundle, champion_dir=champion, ledger=tmp_path / "L.md")

        assert result.startswith("PROMOTED"), result
        card = json.loads((champion / "champion.json").read_text())
        assert card["size_kb"] == 21.0

    def test_an_empty_file_is_refused(self, tmp_path: Path) -> None:
        """Zero clears every budget, because zero is under every number."""
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        empty = tmp_path / "model.onnx"
        empty.write_bytes(b"")

        result = promote(
            run_dir, empty, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md"
        )

        assert result.startswith("REFUSED"), result
        assert "0.0 KB" in result
        assert "export that failed" in result
        assert not (tmp_path / "c").exists()

    def test_an_empty_directory_is_refused_the_same_way(self, tmp_path: Path) -> None:
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        bundle = tmp_path / "model.mlpackage"
        bundle.mkdir()

        result = promote(
            run_dir, bundle, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md"
        )
        assert result.startswith("REFUSED"), result
        assert "export that failed" in result

    def test_a_missing_artifact_refuses_rather_than_raising(self, tmp_path: Path) -> None:
        """`promote` promises a refusal string. A path that vanished between
        the gate and the ship is a refusal like any other, not a traceback."""
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)
        gone = tmp_path / "never-existed.onnx"

        result = promote(
            run_dir, gone, champion_dir=tmp_path / "c", ledger=tmp_path / "L.md"
        )

        assert result.startswith("REFUSED"), result
        assert "cannot measure the artifact" in result

    def test_without_an_artifact_nothing_changes(self, tmp_path: Path) -> None:
        """The backwards-compatibility pin.

        `artifact=None` is what lets you ask 'would this promote?' before the
        export exists, which is the only question the gate subcommand can
        answer. It has to behave exactly as it did before #24.
        """
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=1.0)

        ok, message = evaluate_promotion(run_dir, champion_dir=tmp_path / "c")

        assert ok, message
        assert "gated on the manifest's 1.0 KB" in message
        assert "nothing has checked against a file" in message

    def test_the_example_02_skew(self, tmp_path: Path) -> None:
        """The in-tree case, as a unit.

        examples/02-config-lexer used to gate the int8 eval (4985 bytes) and
        then pass `best_path`, the fp32 file (8641 bytes), to promote(), so the
        card reported the eval's number for the other file's bytes. It never
        executed -- the baseline wins there -- but it was the defect in the one
        example that measures everything else correctly. The example ships the
        int8 file now (#27); these numbers stay as a regression test for the
        harness behaviour, which is what made the mismatch visible.
        """
        run_dir = self.run_claiming(tmp_path / "runs", claimed_kb=4985 / 1024)
        shipped = tmp_path / "conv-raw-chars.onnx"
        shipped.write_bytes(b"\0" * 8641)

        champion = tmp_path / "c"
        promote(run_dir, shipped, champion_dir=champion, ledger=tmp_path / "L.md")

        card = json.loads((champion / "champion.json").read_text())
        assert card["size_kb"] == 8641 / 1024
        assert card["size_kb_reported"] == 4985 / 1024


class TestCandidateIsNamed:
    """#27: the report and the card say which eval is shipping as which file.

    `promote()` takes the last eval as the candidate, so the artifact handed to
    it must be the one that eval describes. Nothing can check that -- an eval
    records numbers, not a path -- so this refuses nothing. It writes the two
    names down together, which is what nobody had done and why #27 survived
    until someone read the source.
    """

    def run_with(self, runs_dir: Path, **eval_metrics) -> Path:
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.value = 0.50
        exp.budgets.max_size_kb = 1000
        run_dir = start_run(exp, runs_dir=runs_dir)
        metrics = {
            "variant": "conv-raw-chars-int8",
            "metric_value": 0.99,
            "size_kb": 4985 / 1024,
            "p95_ms": 1.0,
            "elapsed_minutes": 0.1,
        }
        metrics.update(eval_metrics)
        record_eval(run_dir, **metrics)
        return run_dir

    def test_the_report_names_the_eval_and_the_file(self, tmp_path: Path) -> None:
        run_dir = self.run_with(tmp_path / "runs")
        artifact = tmp_path / "conv-raw-chars-int8.onnx"
        artifact.write_bytes(b"\0" * 4985)

        ok, message = evaluate_promotion(
            run_dir, artifact=artifact, champion_dir=tmp_path / "c"
        )

        assert ok, message
        assert "the last of 1 eval(s)" in message
        assert "'conv-raw-chars-int8'" in message
        assert "'conv-raw-chars-int8.onnx'" in message

    def test_a_mismatch_is_visible_in_the_report(self, tmp_path: Path) -> None:
        """#27 exactly: the int8 eval shipping the fp32 file.

        Not a refusal. The harness has no way to know that `conv-raw-chars` is
        a different model from `conv-raw-chars-int8` rather than a renamed
        export of it, and inventing a naming convention to guess with would
        fail on the first project that does not share it.
        """
        run_dir = self.run_with(tmp_path / "runs")
        fp32 = tmp_path / "conv-raw-chars.onnx"
        fp32.write_bytes(b"\0" * 8641)

        ok, message = evaluate_promotion(
            run_dir, artifact=fp32, champion_dir=tmp_path / "c"
        )

        assert ok, "still promotes -- this is legibility, not a gate"
        assert "variant 'conv-raw-chars-int8'" in message
        assert "shipping file 'conv-raw-chars.onnx'" in message

    def test_the_card_records_the_variant(self, tmp_path: Path) -> None:
        run_dir = self.run_with(tmp_path / "runs")
        artifact = tmp_path / "conv-raw-chars-int8.onnx"
        artifact.write_bytes(b"\0" * 4985)
        champion = tmp_path / "c"

        promote(run_dir, artifact, champion_dir=champion, ledger=tmp_path / "L.md")

        card = json.loads((champion / "champion.json").read_text())
        assert card["variant"] == "conv-raw-chars-int8"
        assert card["artifact"] == "conv-raw-chars-int8.onnx"

    def test_an_eval_without_a_variant_does_not_raise(self, tmp_path: Path) -> None:
        """`record_eval` takes arbitrary keywords and REQUIRED_EVAL_KEYS does
        not include `variant`, so it is not guaranteed to be there. `gate_run`
        already degrades to 'unnamed'; this does the same rather than crashing
        a promotion over a missing label."""
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.value = 0.50
        exp.budgets.max_size_kb = 1000
        run_dir = start_run(exp, runs_dir=tmp_path / "runs")
        record_eval(
            run_dir, metric_value=0.99, size_kb=1.0, p95_ms=1.0, elapsed_minutes=0.1
        )
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"\0" * 1024)
        champion = tmp_path / "c"

        result = promote(run_dir, artifact, champion_dir=champion, ledger=tmp_path / "L.md")

        assert result.startswith("PROMOTED"), result
        assert "variant 'unnamed'" in result
        card = json.loads((champion / "champion.json").read_text())
        assert card["variant"] == "unnamed"

    def test_without_an_artifact_it_says_so(self, tmp_path: Path) -> None:
        run_dir = self.run_with(tmp_path / "runs")

        ok, message = evaluate_promotion(run_dir, champion_dir=tmp_path / "c")

        assert ok, message
        assert "no file named" in message
