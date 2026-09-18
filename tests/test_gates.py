"""Tests for the gates. These encode the rules the harness is actually for."""

import pytest

from harness.experiment import Baseline, Budgets, Experiment
from harness.gates import (
    baseline_gate,
    latency_gate,
    patience_gate,
    run_all,
    size_gate,
    wallclock_gate,
)


def make_experiment(**overrides) -> Experiment:
    budgets = Budgets(
        max_size_kb=overrides.pop("max_size_kb", 50),
        latency_band=overrides.pop("latency_band", "instant"),
        patience_evals=overrides.pop("patience_evals", 3),
        max_wallclock_minutes=overrides.pop("max_wallclock_minutes", 60),
    )
    baseline = Baseline(
        kind="deterministic",
        name="regex tagger",
        metric="accuracy",
        value=overrides.pop("baseline_value", 0.90),
    )
    return Experiment(
        task="test task",
        hypothesis="a tiny model can beat the regex tagger on unseen formats",
        baseline=baseline,
        budgets=budgets,
    )


class TestBaselineGate:
    def test_strict_improvement_passes(self):
        assert baseline_gate(make_experiment(), 0.91).passed

    def test_tie_fails(self):
        """The rule that matters: a tie goes to the baseline.

        The baseline ships without weights, without a training pipeline, and
        without silent failure modes. Matching it is not beating it.
        """
        assert not baseline_gate(make_experiment(), 0.90).passed

    def test_worse_fails(self):
        assert not baseline_gate(make_experiment(), 0.89).passed

    def test_lower_is_better_inverts(self):
        exp = make_experiment(baseline_value=0.10)  # e.g. error rate
        assert baseline_gate(exp, 0.05, higher_is_better=False).passed
        assert not baseline_gate(exp, 0.15, higher_is_better=False).passed

    def test_failure_carries_remediation(self):
        result = baseline_gate(make_experiment(), 0.5)
        assert result.remediation
        # The remediation must steer away from the expensive wrong move.
        assert "representation" in result.remediation


class TestSizeGate:
    def test_under_budget_passes(self):
        assert size_gate(make_experiment(max_size_kb=50), 27.5).passed

    def test_exactly_at_budget_passes(self):
        assert size_gate(make_experiment(max_size_kb=50), 50.0).passed

    def test_over_budget_fails(self):
        assert not size_gate(make_experiment(max_size_kb=50), 50.1).passed


class TestLatencyGate:
    def test_instant_band_ceiling_is_100ms(self):
        exp = make_experiment(latency_band="instant")
        assert latency_gate(exp, 99.0).passed
        assert not latency_gate(exp, 101.0).passed

    def test_flow_band_ceiling_is_1s(self):
        exp = make_experiment(latency_band="flow")
        assert latency_gate(exp, 900.0).passed
        assert not latency_gate(exp, 1100.0).passed

    def test_unknown_band_rejected(self):
        with pytest.raises(ValueError):
            Budgets(max_size_kb=10, latency_band="snappy")

    def test_explicit_override_beats_band_default(self):
        b = Budgets(max_size_kb=10, latency_band="instant", max_latency_ms=16.0)
        assert b.max_latency_ms == 16.0


class TestPatienceGate:
    def test_not_tested_before_patience_exhausted(self):
        exp = make_experiment(patience_evals=3)
        assert patience_gate(exp, [0.1, 0.2]).passed

    def test_plateau_fails(self):
        exp = make_experiment(patience_evals=3)
        assert not patience_gate(exp, [0.80, 0.80, 0.80, 0.80]).passed

    def test_improvement_within_window_passes(self):
        exp = make_experiment(patience_evals=3)
        assert patience_gate(exp, [0.80, 0.80, 0.80, 0.85]).passed

    def test_regression_after_peak_fails(self):
        exp = make_experiment(patience_evals=2)
        assert not patience_gate(exp, [0.90, 0.85, 0.84]).passed


class TestWallclockGate:
    def test_under_cap_passes(self):
        assert wallclock_gate(make_experiment(max_wallclock_minutes=600), 480).passed

    def test_over_cap_fails(self):
        assert not wallclock_gate(make_experiment(max_wallclock_minutes=600), 601).passed


class TestRunAll:
    def test_all_pass(self):
        ok, results = run_all(
            make_experiment(),
            candidate_value=0.95,
            size_kb=20.0,
            p95_ms=40.0,
            eval_history=[0.90, 0.95],
            elapsed_minutes=10.0,
        )
        assert ok
        assert len(results) == 5

    def test_single_failure_fails_the_whole(self):
        """A model can pass every technical budget and still not be shippable."""
        ok, results = run_all(
            make_experiment(),
            candidate_value=0.80,  # loses to baseline
            size_kb=1.0,           # tiny
            p95_ms=1.0,            # instant
            eval_history=[0.80],
            elapsed_minutes=1.0,
        )
        assert not ok
        failed = [r.name for r in results if not r.passed]
        assert failed == ["baseline"]


class TestBaselineValidation:
    def test_kind_must_be_known(self):
        with pytest.raises(ValueError):
            Baseline(kind="vibes", name="x", metric="accuracy", value=0.5)

    def test_there_is_no_none_kind(self):
        """If you cannot name something simpler, the task is not scoped yet."""
        with pytest.raises(ValueError):
            Baseline(kind="none", name="", metric="accuracy", value=0.0)
