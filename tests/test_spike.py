"""Tests for the spike record.

Shaped after `tests/test_validate.py`, because a spike record is the same kind
of object as an experiment file: a form whose refusals are the product. Every
refusal here has a test, and every refusal that names an escape has a test that
the escape is still named -- the convention
`tests/test_validate.py::TestBaselineValue::test_message_names_the_flag` set,
and the one that stops a reword quietly deleting the way out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from harness.__main__ import main
from harness.spike import (
    MAX_SPIKE_MINUTES,
    SCOPE,
    STATUSES,
    contract_fields,
    find_spikes,
    load_spike,
    spike_problems,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "harness" / "templates" / "spike.md"

DROP = object()  # an override that removes the field entirely

# The PRD assumption this whole idea came from, written out as a record.
VALID: dict[str, Any] = {
    "question": "Do at least 90% of Chordonomicon chord symbols parse with chords_mapping.csv?",
    "informs": "dataset.teacher",
    "threshold": ">= 0.90 on the first 10k rows",
    "if_not": "hand-write the fifty commonest symbols and drop the published mapping",
    "budget_minutes": 120,
    "status": "open",
    "finding": "",
    "measured": None,
    "elapsed_minutes": 0,
}


def write_spike(tmp_path: Path, **overrides: Any) -> Path:
    """Render a *valid* record, with per-field overrides. DROP removes a field."""
    fields = {**VALID, **overrides}
    fields = {k: v for k, v in fields.items() if v is not DROP}
    path = tmp_path / "tagger.spike.md"
    body = yaml.safe_dump(fields, sort_keys=False, allow_unicode=False)
    path.write_text(f"---\n{body}---\n\n# tagger\n\nProse nobody parses.\n")
    return path


class TestShippedFiles:
    def test_template_is_deliberately_invalid(self) -> None:
        """The template is a blank form, not a spike.

        Same decision as `harness/templates/experiment.yaml`: making it pass
        would mean shipping a fake question and a fake threshold, which is the
        habit this exists to break. Pinned so nobody "fixes" it.
        """
        problems = spike_problems(TEMPLATE)
        for field in ("question", "informs", "threshold", "if_not", "budget_minutes"):
            assert any(field in p for p in problems), f"{field} should be refused"

    def test_a_valid_record_has_no_problems(self, tmp_path: Path) -> None:
        assert spike_problems(write_spike(tmp_path)) == []


class TestTheFrontmatter:
    def test_a_file_with_no_frontmatter_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "tagger.spike.md"
        path.write_text("# tagger\n\nI measured a thing once.\n")
        problems = spike_problems(path)
        assert any("no YAML frontmatter" in p for p in problems)

    def test_unparseable_frontmatter_reports_why(self, tmp_path: Path) -> None:
        path = tmp_path / "tagger.spike.md"
        path.write_text("---\nquestion: [unclosed\n---\n")
        problems = spike_problems(path)
        assert len(problems) == 1
        assert problems[0].startswith("could not parse the frontmatter:")

    def test_frontmatter_that_is_not_a_mapping_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "tagger.spike.md"
        path.write_text("---\n- just\n- a list\n---\n")
        assert any("not a mapping" in p for p in spike_problems(path))

    def test_the_prose_below_is_not_parsed(self, tmp_path: Path) -> None:
        """The body is where the working goes; only the form is checked."""
        path = write_spike(tmp_path)
        path.write_text(path.read_text() + "\n---\n\nquestion: not this one\n")
        assert spike_problems(path) == []

    def test_load_spike_returns_the_fields(self, tmp_path: Path) -> None:
        assert load_spike(write_spike(tmp_path))["informs"] == "dataset.teacher"


class TestTheQuestion:
    @pytest.mark.parametrize("question", ["", "chords", "check the mapping", DROP])
    def test_a_question_under_five_words_is_refused(
        self, tmp_path: Path, question: Any
    ) -> None:
        problems = spike_problems(write_spike(tmp_path, question=question))
        assert any("question is under" in p for p in problems)


class TestInforms:
    @pytest.mark.parametrize("field", contract_fields())
    def test_informs_accepts_every_template_field(self, tmp_path: Path, field: str) -> None:
        """The list is the contract's own shape, read at runtime.

        A hardcoded list would be a second copy of the template, and the second
        copy is the one that rots -- which is exactly the failure that had one
        rule stated three different ways in three files.
        """
        assert spike_problems(write_spike(tmp_path, informs=field)) == []

    def test_scope_is_accepted(self, tmp_path: Path) -> None:
        """The fourth kind of spike: the one deciding whether to write a
        contract at all, where there is no field to point at yet."""
        assert spike_problems(write_spike(tmp_path, informs=SCOPE)) == []

    def test_a_list_is_accepted(self, tmp_path: Path) -> None:
        path = write_spike(tmp_path, informs=["dataset.teacher", "budgets.max_size_kb"])
        assert spike_problems(path) == []

    def test_one_bad_entry_in_a_list_is_refused(self, tmp_path: Path) -> None:
        path = write_spike(tmp_path, informs=["dataset.teacher", "dataset.vibes"])
        assert any("dataset.vibes" in p for p in spike_problems(path))

    @pytest.mark.parametrize("bad", ["", "notes", "budgets.notes", "dataset.split", DROP])
    def test_an_unknown_field_is_refused(self, tmp_path: Path, bad: Any) -> None:
        assert any("informs" in p for p in spike_problems(write_spike(tmp_path, informs=bad)))

    def test_the_message_lists_the_valid_paths(self, tmp_path: Path) -> None:
        problems = spike_problems(write_spike(tmp_path, informs="budgets.notes"))
        message = next(p for p in problems if "informs" in p)
        assert "dataset.teacher" in message
        assert "budgets.max_size_kb" in message
        assert SCOPE in message


class TestThreshold:
    @pytest.mark.parametrize("bad", ["", "   ", DROP])
    def test_an_empty_threshold_is_refused(self, tmp_path: Path, bad: Any) -> None:
        problems = spike_problems(write_spike(tmp_path, threshold=bad))
        assert any("threshold is empty" in p for p in problems)

    def test_the_check_admits_it_reads_labels(self, tmp_path: Path) -> None:
        """Nothing compares the finding to the threshold, and the message says
        so rather than implying the number was checked. Same honesty as
        `dataset.split_rationale`: pretending the hole is closed is worse than
        leaving it open where a reader can see it."""
        problems = spike_problems(write_spike(tmp_path, threshold=""))
        assert any("reads a label, not a measurement" in p for p in problems)


class TestIfNot:
    @pytest.mark.parametrize("bad", ["", "nothing", "we would be sad", DROP])
    def test_a_consequence_under_five_words_is_refused(
        self, tmp_path: Path, bad: Any
    ) -> None:
        problems = spike_problems(write_spike(tmp_path, if_not=bad))
        assert any("if_not is under" in p for p in problems)


class TestBudget:
    @pytest.mark.parametrize("bad", [0, -1, MAX_SPIKE_MINUTES + 1, 5000, "soon", None, True])
    def test_a_budget_outside_the_box_is_refused(self, tmp_path: Path, bad: Any) -> None:
        problems = spike_problems(write_spike(tmp_path, budget_minutes=bad))
        assert any("budget_minutes" in p for p in problems)

    @pytest.mark.parametrize("good", [1, 30, 120.5, MAX_SPIKE_MINUTES])
    def test_a_budget_inside_the_box_is_accepted(self, tmp_path: Path, good: Any) -> None:
        assert spike_problems(write_spike(tmp_path, budget_minutes=good)) == []

    def test_the_ceiling_is_one_working_day(self) -> None:
        """Pinned because the docs call it a judgement call and say what the
        judgement was. A silent change would leave the argument behind."""
        assert MAX_SPIKE_MINUTES == 480


class TestStatus:
    @pytest.mark.parametrize("bad", ["", "pending", "done", "OPEN", DROP])
    def test_an_unknown_status_is_refused(self, tmp_path: Path, bad: Any) -> None:
        problems = spike_problems(write_spike(tmp_path, status=bad))
        assert any("status" in p for p in problems)

    @pytest.mark.parametrize("status", STATUSES)
    def test_every_known_status_is_spelled_the_same_way(self, status: str) -> None:
        assert status == status.lower()

    def test_answered_without_a_finding_is_refused(self, tmp_path: Path) -> None:
        path = write_spike(tmp_path, status="answered", elapsed_minutes=45)
        assert any("finding is under" in p for p in spike_problems(path))

    def test_abandoned_without_a_finding_is_refused(self, tmp_path: Path) -> None:
        """This is the whole reason `abandoned` earns its place. Without the
        finding it is an `open` nobody closed, and should have been cut."""
        path = write_spike(tmp_path, status="abandoned", elapsed_minutes=45)
        assert any("finding is under" in p for p in spike_problems(path))

    def test_answered_with_a_finding_is_accepted(self, tmp_path: Path) -> None:
        path = write_spike(
            tmp_path,
            status="answered",
            finding="94% of the symbols parse, so the mapping stands",
            measured=0.94,
            elapsed_minutes=45,
        )
        assert spike_problems(path) == []

    def test_answered_in_no_time_at_all_is_refused(self, tmp_path: Path) -> None:
        path = write_spike(
            tmp_path,
            status="answered",
            finding="94% of the symbols parse, so the mapping stands",
            elapsed_minutes=0,
        )
        assert any("elapsed_minutes is 0" in p for p in spike_problems(path))


class TestTheTimeBox:
    def test_over_budget_and_still_open_is_refused(self, tmp_path: Path) -> None:
        path = write_spike(tmp_path, budget_minutes=60, elapsed_minutes=200)
        assert any("past budget_minutes" in p for p in spike_problems(path))

    def test_over_budget_and_answered_is_refused_too(self, tmp_path: Path) -> None:
        """Answering it late is still overrunning the box. The record says what
        you agreed to spend; editing that afterwards makes it say what it
        cost, which is a different and much less useful sentence."""
        path = write_spike(
            tmp_path,
            budget_minutes=60,
            elapsed_minutes=200,
            status="answered",
            finding="94% of the symbols parse, so the mapping stands",
        )
        assert any("past budget_minutes" in p for p in spike_problems(path))

    def test_abandoned_is_the_way_to_close_an_overrun(self, tmp_path: Path) -> None:
        path = write_spike(
            tmp_path,
            budget_minutes=60,
            elapsed_minutes=200,
            status="abandoned",
            finding="the mapping file is undocumented and this needs a human",
        )
        assert spike_problems(path) == []

    def test_negative_elapsed_is_refused(self, tmp_path: Path) -> None:
        assert any("negative" in p for p in spike_problems(write_spike(tmp_path, elapsed_minutes=-1)))


# Each refusal that offers a way out has to keep naming it. A reword is the
# usual way an escape disappears, and an escape nobody can find is the same as
# no escape -- `tests/test_validate.py` pins its two the same way.
ESCAPES = [
    ({"question": "chords"}, "/scope"),
    ({"informs": "budgets.notes"}, SCOPE),
    ({"threshold": ""}, "reads a label"),
    ({"if_not": "nope"}, "status: abandoned"),
    ({"budget_minutes": 5000}, "max_wallclock_minutes"),
    ({"status": "pending"}, "abandoned"),
    ({"status": "answered", "elapsed_minutes": 30}, "status: open"),
    ({"budget_minutes": 60, "elapsed_minutes": 200}, "status: abandoned"),
]


@pytest.mark.parametrize(("overrides", "escape"), ESCAPES, ids=[e for _, e in ESCAPES])
def test_message_names_the_escape(tmp_path: Path, overrides: dict, escape: str) -> None:
    problems = spike_problems(write_spike(tmp_path, **overrides))
    assert any(escape in p for p in problems), f"no refusal named {escape!r}: {problems}"


class TestFindSpikes:
    def test_finds_records_in_the_spec_directory(self, tmp_path: Path) -> None:
        (tmp_path / "experiments").mkdir()
        for name in ("a.spike.md", "b.spike.md"):
            (tmp_path / "experiments" / name).write_text("---\nquestion: q\n---\n")
        assert [p.name for p in find_spikes(tmp_path)] == ["a.spike.md", "b.spike.md"]

    def test_ignores_contracts_and_refusals(self, tmp_path: Path) -> None:
        """A spike record is not a contract and not a refusal. The suffix is
        what keeps the three apart in one directory."""
        (tmp_path / "experiments").mkdir()
        (tmp_path / "experiments" / "tagger.yaml").write_text("task: t\n")
        (tmp_path / "experiments" / "tagger-refused.md").write_text("no\n")
        assert find_spikes(tmp_path) == []

    def test_a_project_with_no_spec_directory_is_not_an_error(self, tmp_path: Path) -> None:
        assert find_spikes(tmp_path) == []


def test_a_spike_path_is_ungateable(tmp_path: Path) -> None:
    """A spike is never a run, and the gates already know it.

    `load_run` raises FileNotFoundError without a manifest.json, so `gate`
    exits 2 on a spike path without anything new being written. Pinned anyway:
    the whole safety argument for a record in `experiments/` is that nothing
    downstream can mistake it for a run.
    """
    assert main(["gate", str(write_spike(tmp_path))]) == 2
