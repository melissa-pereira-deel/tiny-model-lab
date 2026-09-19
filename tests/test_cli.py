"""Tests for the harness command line.

`/gate` and `/ship` had no entry point, so each invocation improvised its own
manifest loading. These tests pin the thing that replaced the improvisation:
exit codes an agent can branch on, and a refusal to report anything the manifest
does not actually contain.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.__main__ import main
from harness.experiment import Experiment, load_run, record_eval, start_run
from harness.gates import band_landed_in, gate_run

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_SPEC = REPO_ROOT / "examples" / "01-hello-tiny" / "experiment.yaml"


def make_run(tmp_path: Path, **eval_metrics) -> Path:
    """A run directory with one recorded eval, outside the repo."""
    exp = Experiment.from_yaml(EXAMPLE_SPEC)
    exp.baseline.value = 0.50  # beatable, so the candidate is not the subject
    exp.budgets.max_size_kb = 1000
    run_dir = start_run(exp, runs_dir=tmp_path)
    metrics = {
        "variant": "v1",
        "metric_value": 0.99,
        "size_kb": 12.0,
        "p95_ms": 4.0,
        "elapsed_minutes": 0.1,
    }
    metrics.update(eval_metrics)
    record_eval(run_dir, **metrics)
    return run_dir


class TestExitCodes:
    """An agent branches on these, so they are part of the contract."""

    def test_no_arguments_prints_usage(self, capsys) -> None:
        assert main([]) == 2
        assert "Usage:" in capsys.readouterr().out

    def test_unknown_subcommand(self) -> None:
        assert main(["frobnicate"]) == 2

    def test_gate_without_a_run_dir(self) -> None:
        assert main(["gate"]) == 2

    def test_gate_on_a_missing_directory(self, capsys) -> None:
        assert main(["gate", "/nonexistent/run"]) == 2
        assert "UNGATEABLE" in capsys.readouterr().out

    def test_gate_passes_when_every_gate_passes(self, tmp_path: Path) -> None:
        assert main(["gate", str(make_run(tmp_path))]) == 0

    def test_gate_fails_when_a_gate_fails(self, tmp_path: Path) -> None:
        """The worked example loses to its baseline, which is the point of it."""
        run_dir = make_run(tmp_path, metric_value=0.10)  # loses to baseline 0.50
        assert main(["gate", str(run_dir)]) == 1

    def test_validate_subcommand_matches_the_module(self) -> None:
        assert main(["validate", str(EXAMPLE_SPEC)]) == 0
        blank = REPO_ROOT / "harness" / "templates" / "experiment.yaml"
        assert main(["validate", str(blank)]) == 1

    def test_validate_without_a_path(self) -> None:
        assert main(["validate"]) == 2


class TestValidateTakesSeveralFiles:
    """CONTRIBUTING tells contributors to pass a glob.

    A command that accepted exactly one path worked only while this repo had
    exactly one example, and would have started failing the day a second landed.
    """

    BLANK = REPO_ROOT / "harness" / "templates" / "experiment.yaml"

    def test_all_good_passes(self) -> None:
        assert main(["validate", str(EXAMPLE_SPEC), str(EXAMPLE_SPEC)]) == 0

    def test_one_bad_fails_the_lot(self) -> None:
        assert main(["validate", str(EXAMPLE_SPEC), str(self.BLANK)]) == 1

    def test_reports_every_file_not_just_the_first_bad_one(self, capsys) -> None:
        main(["validate", str(self.BLANK), str(EXAMPLE_SPEC)])
        out = capsys.readouterr().out
        assert "INVALID" in out
        assert "VALID —" in out  # the good one is still reported after the bad one


class TestGateOutput:
    def test_reports_every_gate_including_passes(self, tmp_path: Path, capsys) -> None:
        main(["gate", str(make_run(tmp_path))])
        out = capsys.readouterr().out
        for gate in ("baseline", "size", "latency", "patience", "wallclock"):
            assert gate in out

    def test_names_the_band_the_model_landed_in(self, tmp_path: Path, capsys) -> None:
        """The one thing the library does not already report.

        `latency_gate` names the band the experiment *declared*. A model
        budgeted for 'instant' that measures 400 ms landed in 'flow', and that
        is a fact about the interaction, not about the model.
        """
        main(["gate", str(make_run(tmp_path, p95_ms=400.0))])
        out = capsys.readouterr().out
        assert "Landed in: 'flow'" in out
        assert "declared 'instant'" in out

    def test_refuses_to_invent_the_design_checks(self, tmp_path: Path, capsys) -> None:
        """Nothing in a manifest encodes whether a wrong answer is survivable."""
        main(["gate", str(make_run(tmp_path))])
        out = capsys.readouterr().out
        assert "not computable" in out
        assert "design-eval" in out

    def test_says_nothing_about_promote_iterate_stop(self, tmp_path: Path, capsys) -> None:
        main(["gate", str(make_run(tmp_path))])
        out = capsys.readouterr().out
        assert "judgement" in out


class TestBandLandedIn:
    @pytest.mark.parametrize(
        ("p95", "band"),
        [(0.0, "instant"), (100.0, "instant"), (101.0, "flow"),
         (1000.0, "flow"), (1001.0, "attention"), (10000.0, "attention")],
    )
    def test_narrowest_band_that_fits(self, p95: float, band: str) -> None:
        assert band_landed_in(p95) == band

    def test_past_every_band_is_not_an_interaction(self) -> None:
        assert band_landed_in(10_001.0) is None


class TestLoadRun:
    def test_missing_manifest_names_the_directory(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="run directory"):
            load_run(tmp_path)

    def test_missing_gate_metric_is_named(self, tmp_path: Path) -> None:
        """record_eval takes any keyword, so the runner has to supply these.

        A bare KeyError from improvised loading code is the failure this
        replaces — it tells you a dict lookup failed, not which metric is absent.
        """
        run_dir = make_run(tmp_path)
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["evals"][0]["p95_ms"]
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(KeyError, match="p95_ms"):
            load_run(run_dir)

    def test_gate_run_refuses_a_run_with_no_evals(self, tmp_path: Path) -> None:
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        run_dir = start_run(exp, runs_dir=tmp_path)
        with pytest.raises(ValueError, match="nothing to gate"):
            gate_run(run_dir)


class TestExperimentRoundTrip:
    def test_from_dict_is_lossless(self) -> None:
        """The manifest is the only record that survives the session.

        evaluate_promotion used to rebuild the Experiment field by field and
        drop kill_criteria, so an evaluator checking them saw an empty list at
        exactly the moment the answer should have been 'stop the project'.
        """
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        assert Experiment.from_dict(exp.to_dict()) == exp

    def test_kill_criteria_survive_a_run(self, tmp_path: Path) -> None:
        run_dir = make_run(tmp_path)
        _, rebuilt = load_run(run_dir)
        assert rebuilt.kill_criteria
        assert rebuilt.tags == ["example", "tutorial"]


def test_module_entry_point_is_wired_up(tmp_path: Path) -> None:
    """One subprocess test that `python -m harness` actually runs.

    Everything else calls main() in-process; this pins the __main__ wiring and
    that no import-order warning leaks onto the stream an agent reads.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "harness", "gate", str(make_run(tmp_path))],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ALL GATES PASS" in proc.stdout
    assert "RuntimeWarning" not in proc.stderr
