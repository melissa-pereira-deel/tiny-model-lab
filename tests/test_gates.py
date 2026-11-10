"""Tests for the gates. These encode the rules the harness is actually for."""

import re
from dataclasses import asdict

import pytest

from harness.experiment import TARGETS, Baseline, Budgets, Experiment
from harness.gates import (
    TABLE_TARGETS,
    WEIGHT_TARGETS,
    GateResult,
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
        measured_at_runtime=overrides.pop("measured_at_runtime", False),
    )
    return Experiment(
        task="test task",
        hypothesis="a tiny model can beat the regex tagger on unseen formats",
        baseline=baseline,
        budgets=budgets,
        target=overrides.pop("target", "onnx-web"),
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

    def test_unmeasured_runtime_baseline_refuses(self):
        """A declared-but-unmeasured baseline must not let everything through.

        `measured_at_runtime` lets a contract ship without the number so a runner
        can supply it. If the number never arrives the value is still 0.0, and
        every candidate 'beats' it — the comparison this harness exists to
        prevent. The flag is a declaration, not an exemption.
        """
        exp = make_experiment(baseline_value=0.0, measured_at_runtime=True)
        assert not baseline_gate(exp, 0.95).passed

    def test_unmeasured_refusal_explains_itself(self):
        exp = make_experiment(baseline_value=0.0, measured_at_runtime=True)
        result = baseline_gate(exp, 0.95)
        assert "measure" in result.remediation.lower()

    def test_measured_runtime_baseline_gates_normally(self):
        """Once the number arrives the flag changes nothing — including the tie."""
        exp = make_experiment(baseline_value=0.90, measured_at_runtime=True)
        assert not baseline_gate(exp, 0.90).passed
        assert baseline_gate(exp, 0.91).passed


class TestSizeGate:
    def test_under_budget_passes(self):
        assert size_gate(make_experiment(max_size_kb=50), 27.5).passed

    def test_exactly_at_budget_passes(self):
        assert size_gate(make_experiment(max_size_kb=50), 50.0).passed

    def test_over_budget_fails(self):
        assert not size_gate(make_experiment(max_size_kb=50), 50.1).passed

    def test_remediation_tries_ptq_before_qat(self):
        """The regression test for the contradiction in #14.

        `quantization-strategy` says int8 is post-training and the first thing
        to try; this text used to say quantization-aware training *at* int8,
        which costs a retrain to reach a width PTQ reaches in minutes. An agent
        reading the gate contradicted the skill, and the gate is what it reads
        at the moment it is over budget.
        """
        text = size_gate(make_experiment(max_size_kb=50), 90.0).remediation
        assert "post-training" in text
        assert "quantization-aware" in text
        assert text.index("post-training") < text.index("quantization-aware")

    def test_remediation_names_the_target(self):
        """Sub-8-bit is a property of the export path, not of the model.

        The gate deliberately carries no table of which widths each target
        supports — that rots. It names the target so the agent goes and checks
        before spending a retrain on a width its exporter has no format for.
        """
        for target in ("onnx-web", "coreml", "wgsl"):
            text = size_gate(make_experiment(max_size_kb=50, target=target), 90.0).remediation
            assert target in text


def size_gate_before_37(experiment: Experiment, actual_kb: float) -> GateResult:
    """`size_gate` exactly as it was at 1d7042f, before the text branched (#37).

    Frozen here so "identical to before" is a comparison against the old code
    rather than against someone's memory of it. Do not update it to match the
    gate; if the gate's arithmetic has to change, that is a `Gate semantics`
    entry and this reference should be deleted with an explanation, not edited.
    """
    cap = experiment.budgets.max_size_kb
    return GateResult(
        name="size",
        passed=actual_kb <= cap,
        detail=f"artifact {actual_kb:.1f} KB vs budget {cap:.1f} KB",
        remediation=(
            f"Over budget by {actual_kb - cap:.1f} KB. Try in order: "
            "post-training quantization to int8 -- minutes, usually near-lossless, "
            "and the one width every export path supports; then quantization-aware "
            "training below 8 bits, though confirm the target you declared "
            f"({experiment.target}) has a format for that width before you spend a "
            "retrain reaching it; then width reduction; then pruning. Re-run the "
            "baseline gate after each -- compression that breaks accuracy is not a win."
        ),
    )


# (budget, measured) pairs: under, exactly at, a hair over, well over, the
# rounding edges of `.1f`, and #24's 4 MB-against-50 KB.
SIZE_CASES = [
    (50, 27.5), (50, 50.0), (50, 50.04), (50, 50.05), (50, 50.1), (50, 90.0),
    (5, 0.7), (0.5, 0.54), (50, 3906.25), (0, 0.0), (0, 0.01),
]
EVERY_TARGET = (*TARGETS, "rust-wasm")  # plus one `validate` would refuse

OVER_BY = re.compile(r"^Over budget by (-?\d+\.\d) KB\. ")


class TestSizeGateRemediationByArtifact:
    """#37: the remediation branches on what the target ships. Nothing else does."""

    def remediation(self, target: str) -> str:
        return size_gate(make_experiment(max_size_kb=50, target=target), 90.0).remediation

    def test_every_target_has_exactly_one_ladder(self):
        """A new target forces a decision about which advice it gets."""
        assert WEIGHT_TARGETS | TABLE_TARGETS == set(TARGETS)
        assert not WEIGHT_TARGETS & TABLE_TARGETS

    def test_onnx_web_keeps_the_weight_ladder_word_for_word(self):
        assert self.remediation("onnx-web") == (
            "Over budget by 40.0 KB. Try in order: post-training quantization to "
            "int8 -- minutes, usually near-lossless, and the one width every export "
            "path supports; then quantization-aware training below 8 bits, though "
            "confirm the target you declared (onnx-web) has a format for that width "
            "before you spend a retrain reaching it; then width reduction; then "
            "pruning. Re-run the baseline gate after each -- compression that breaks "
            "accuracy is not a win."
        )

    @pytest.mark.parametrize("target", sorted(WEIGHT_TARGETS))
    def test_every_weight_target_is_unchanged(self, target):
        exp = make_experiment(max_size_kb=50, target=target)
        assert size_gate(exp, 90.0) == size_gate_before_37(exp, 90.0)

    def test_json_inline_gets_the_table_ladder_in_order(self):
        text = self.remediation("json-inline")
        steps = ("prune rows", "lower n-gram order", "cap the vocabulary")
        for step in steps:
            assert step in text
        assert [text.index(s) for s in steps] == sorted(text.index(s) for s in steps)
        assert "(json-inline)" in text
        assert "baseline gate" in text

    def test_json_inline_names_no_move_a_table_cannot_make(self):
        """Three of the four weight moves do not exist for a count table."""
        text = self.remediation("json-inline")
        for absent in ("quantization", "int8", "8 bits", "width reduction", "retrain"):
            assert absent not in text

    def test_an_unknown_target_gets_both_ladders_by_kind(self):
        text = self.remediation("rust-wasm")
        assert "(rust-wasm)" in text
        assert "validate" in text
        assert "Exported weights (onnx-web, coreml, tflite, wgsl, mlx-local)" in text
        assert "A table bundled as data (json-inline)" in text
        assert "post-training quantization to int8" in text
        assert "prune rows below a count threshold" in text
        assert "TARGETS" in text

    @pytest.mark.parametrize("target", EVERY_TARGET)
    def test_every_remediation_is_ascii(self, target):
        """Gate output is printed on consoles that cannot take anything else."""
        assert self.remediation(target).isascii()


class TestSizeGateArithmeticIsUnchanged:
    """The text branched; the decision and the number it reports did not."""

    @pytest.mark.parametrize("target", EVERY_TARGET)
    @pytest.mark.parametrize(("budget", "measured"), SIZE_CASES)
    def test_pass_fail_detail_and_overage_match_the_old_gate(self, target, budget, measured):
        exp = make_experiment(max_size_kb=budget, target=target)
        new, old = size_gate(exp, measured), size_gate_before_37(exp, measured)

        assert new.name == old.name
        assert new.passed is old.passed
        assert new.passed is (measured <= budget)
        assert new.detail == old.detail
        assert OVER_BY.match(new.remediation).group(1) == OVER_BY.match(old.remediation).group(1)
        assert OVER_BY.match(new.remediation).group(1) == f"{measured - budget:.1f}"


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

    def test_rehydrates_from_a_manifest_without_the_flag(self):
        """Experiment.from_dict rebuilds a Baseline from manifest JSON.

        Manifests written before `measured_at_runtime` existed have no such key,
        and must keep their original gate behaviour rather than raising.
        """
        old_manifest_baseline = {
            "kind": "deterministic",
            "name": "regex tagger",
            "metric": "accuracy",
            "value": 0.5,
            "notes": "",
        }
        b = Baseline(**old_manifest_baseline)
        assert b.measured_at_runtime is False

    def test_roundtrips_through_asdict(self):
        """Whatever to_dict() writes, Baseline(**...) must accept back."""
        b = Baseline(
            kind="deterministic",
            name="regex tagger",
            metric="accuracy",
            value=0.5,
            measured_at_runtime=True,
        )
        assert Baseline(**asdict(b)) == b


def loss_experiment(**overrides) -> Experiment:
    """A contract whose metric is a loss. `make_experiment` hardcodes accuracy.

    Separate helper rather than a new parameter on that one, so every test
    written before direction existed keeps running against exactly the
    experiment it was written against.
    """
    kw = {}
    if "higher_is_better" in overrides:
        kw["higher_is_better"] = overrides.pop("higher_is_better")
    return Experiment(
        task="test task",
        hypothesis="a bigram beats the unigram on held-out perplexity",
        baseline=Baseline(
            kind="deterministic",
            name="unigram",
            metric=overrides.pop("metric", "perplexity"),
            value=overrides.pop("baseline_value", 2.10),
            **kw,
        ),
        budgets=Budgets(
            max_size_kb=50, latency_band="instant", patience_evals=3,
            max_wallclock_minutes=60,
        ),
    )


class TestMetricDirection:
    """#23. Every gate assumed higher-is-better and no CLI path could say otherwise.

    A model with a *worse* perplexity than the baseline passed, printed PASS,
    and was promoted. The direction now lives in the contract, which is what
    lets `python -m harness gate` get it right with no flag and lets a manifest
    be re-gated correctly later.
    """

    def test_an_undeclared_loss_is_refused_rather_than_guessed(self):
        result = baseline_gate(loss_experiment(), 1.80)
        assert not result.passed
        assert "higher_is_better" in result.detail

    def test_the_refusal_names_the_escape(self):
        """Same obligation as `measured_at_runtime`: the message teaches the way out."""
        result = baseline_gate(loss_experiment(), 1.80)
        assert "higher_is_better: false" in result.remediation

    def test_the_refusal_admits_it_reads_a_name(self):
        """It cannot see the metric, only what the metric is called. Say so.

        Same posture as the split check: pretending the check is stronger than
        it is would be worse than leaving the hole visible.
        """
        assert "name, not the metric" in baseline_gate(loss_experiment(), 1.80).remediation

    def test_declaring_lower_is_better_inverts_the_comparison(self):
        exp = loss_experiment(higher_is_better=False)
        assert baseline_gate(exp, 1.80).passed          # better perplexity
        assert not baseline_gate(exp, 2.40).passed      # worse

    def test_a_declaration_is_obeyed_even_against_the_name(self):
        """`higher_is_better: true` on a loss-shaped name is a choice, not a slip.

        The check exists to make the question unavoidable, not to overrule the
        answer.
        """
        exp = loss_experiment(higher_is_better=True)
        assert not baseline_gate(exp, 1.80).passed
        assert baseline_gate(exp, 2.40).passed

    def test_an_ordinary_metric_still_needs_no_declaration(self):
        """The common case must stay silent or the check becomes noise."""
        assert baseline_gate(make_experiment(baseline_value=0.90), 0.95).passed

    def test_an_explicit_argument_still_overrides_the_contract(self):
        """The parameter outranks the contract, for a caller that means it."""
        exp = loss_experiment(higher_is_better=True)
        assert baseline_gate(exp, 1.80, higher_is_better=False).passed

    def test_patience_reads_the_contract_too(self):
        """With direction wrong, a rising loss reads as progress.

        The one gate whose job is stopping a run that goes nowhere would then
        never fire, which is the expensive half of #23.
        """
        exp = loss_experiment(higher_is_better=False)
        worsening = [1.0, 1.1, 1.2, 1.3, 1.4]
        assert not patience_gate(exp, worsening).passed
        improving = [1.4, 1.3, 1.2, 1.1, 1.0]
        assert patience_gate(exp, improving).passed

    def test_run_all_passes_the_question_down_rather_than_answering_it(self):
        """run_all hands both gates None so each consults the contract."""
        passed, results = run_all(
            loss_experiment(higher_is_better=False),
            candidate_value=1.80,
            size_kb=1.0,
            p95_ms=1.0,
            eval_history=[2.0, 1.9, 1.80],
            elapsed_minutes=1.0,
        )
        assert passed, [str(r) for r in results]

    def test_an_undeclared_loss_fails_the_whole_run(self):
        passed, results = run_all(
            loss_experiment(),
            candidate_value=1.80,
            size_kb=1.0,
            p95_ms=1.0,
            eval_history=[1.80],
            elapsed_minutes=1.0,
        )
        assert not passed
        assert not next(r for r in results if r.name == "baseline").passed


class TestDirectionRehydrates:
    """The same two devices `measured_at_runtime` has, for the same reason."""

    def test_a_manifest_without_the_field_gets_none(self):
        """Manifests written before direction existed must keep their behaviour.

        `None` resolves to higher-is-better, which is what every gate did
        before this field existed, so no historical run changes verdict.
        """
        old = {
            "kind": "deterministic",
            "name": "regex tagger",
            "metric": "accuracy",
            "value": 0.5,
            "notes": "",
            "measured_at_runtime": False,
        }
        b = Baseline(**old)
        assert b.higher_is_better is None
        assert b.prefers_higher() is True

    def test_roundtrips_through_asdict(self):
        b = Baseline(
            kind="deterministic",
            name="unigram",
            metric="perplexity",
            value=2.1,
            higher_is_better=False,
        )
        assert Baseline(**asdict(b)) == b

    @pytest.mark.parametrize(
        "metric", ["perplexity", "val_loss", "Word Error Rate", "test_rmse", "NLL"]
    )
    def test_names_that_read_as_a_loss(self, metric: str) -> None:
        b = Baseline(kind="deterministic", name="x", metric=metric, value=1.0)
        assert b.direction_is_ambiguous()

    @pytest.mark.parametrize("metric", ["accuracy", "f1", "AUC", "recall", "bleu"])
    def test_names_that_do_not(self, metric: str) -> None:
        b = Baseline(kind="deterministic", name="x", metric=metric, value=1.0)
        assert not b.direction_is_ambiguous()
