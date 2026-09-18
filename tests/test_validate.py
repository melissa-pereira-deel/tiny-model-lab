"""Tests for the experiment-file validator.

`validate.py` had no coverage at all, which is how it came to reject the repo's
own worked example while its error message cited that example as the correct
pattern. The first test here is the regression test for exactly that.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.validate import validate

REPO_ROOT = Path(__file__).resolve().parent.parent

MINIMAL = {
    "task": "Classify a short string as word / number / symbol",
    "hypothesis": "a learned lookup can beat the rule classifier on unseen formats",
    "baseline": {
        "kind": "deterministic",
        "name": "regex tagger",
        "metric": "accuracy",
        "value": 0.90,
        "notes": "",
    },
    "budgets": {"max_size_kb": 50, "latency_band": "instant", "patience_evals": 3},
    "kill_criteria": ["Baseline still wins after two structural changes"],
}


def write_experiment(tmp_path: Path, **overrides) -> Path:
    """Render a minimal *valid* spec, with `baseline__value`-style overrides."""
    spec = {k: (dict(v) if isinstance(v, dict) else v) for k, v in MINIMAL.items()}
    for key, value in overrides.items():
        section, _, field = key.partition("__")
        if field:
            spec[section][field] = value
        else:
            spec[section] = value
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(spec))
    return path


class TestShippedFiles:
    def test_worked_example_validates(self) -> None:
        """The regression test: the validator must accept the example it cites.

        `.claude/commands/experiment.md` makes `harness.validate` step 1 of
        /experiment, so an example that fails it blocks the documented flow.
        """
        problems = validate(REPO_ROOT / "examples" / "01-hello-tiny" / "experiment.yaml")
        assert problems == []

    def test_template_is_deliberately_invalid(self) -> None:
        """The template is a blank form, not an experiment.

        Making it validate would mean shipping a fake baseline name, which is
        the habit the validator exists to break. Pinned so nobody "fixes" it.
        """
        problems = validate(REPO_ROOT / "harness" / "templates" / "experiment.yaml")
        assert any("baseline.name" in p for p in problems)


class TestBaselineValue:
    def test_zero_without_the_flag_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, baseline__value=0.0))
        assert any("baseline.value is 0.0" in p for p in problems)

    def test_zero_with_the_flag_is_accepted(self, tmp_path: Path) -> None:
        path = write_experiment(
            tmp_path, baseline__value=0.0, baseline__measured_at_runtime=True
        )
        assert validate(path) == []

    def test_measured_value_is_accepted_either_way(self, tmp_path: Path) -> None:
        assert validate(write_experiment(tmp_path, baseline__value=0.9)) == []
        path = write_experiment(
            tmp_path, baseline__value=0.9, baseline__measured_at_runtime=True
        )
        assert validate(path) == []

    def test_message_names_the_flag(self, tmp_path: Path) -> None:
        """The message's job is to teach the escape, so a reword must not drop it."""
        problems = validate(write_experiment(tmp_path, baseline__value=0.0))
        assert any("measured_at_runtime" in p for p in problems)


class TestOtherRules:
    def test_empty_baseline_name_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, baseline__name="  "))
        assert any("baseline.name" in p for p in problems)

    def test_empty_kill_criteria_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, kill_criteria=[]))
        assert any("kill_criteria" in p for p in problems)

    def test_vague_hypothesis_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, hypothesis="it might help"))
        assert any("hypothesis" in p for p in problems)

    def test_non_positive_size_budget_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, budgets__max_size_kb=0))
        assert any("max_size_kb" in p for p in problems)

    def test_unknown_latency_band_is_rejected(self, tmp_path: Path) -> None:
        problems = validate(write_experiment(tmp_path, budgets__latency_band="snappy"))
        assert problems  # Budgets.__post_init__ raises, surfaced as a parse failure

    def test_unparseable_file_reports_why(self, tmp_path: Path) -> None:
        path = tmp_path / "experiment.yaml"
        path.write_text("task: [unclosed\n")
        problems = validate(path)
        assert len(problems) == 1
        assert problems[0].startswith("could not parse:")

    def test_a_valid_file_has_no_problems(self, tmp_path: Path) -> None:
        assert validate(write_experiment(tmp_path)) == []


@pytest.mark.parametrize("kind", ["deterministic", "classical", "existing_tool", "previous_run"])
def test_every_valid_baseline_kind_passes(tmp_path: Path, kind: str) -> None:
    assert validate(write_experiment(tmp_path, baseline__kind=kind)) == []
