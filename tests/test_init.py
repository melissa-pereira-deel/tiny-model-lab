"""Tests for `harness init`.

There were none. The command that decides what every adopted project starts
with — the one place the harness gets to set someone's defaults — had no
coverage at all, and both of the bugs these pin (#21, #30) were about what it
hands you rather than about anything it computes.

The ignore rules it writes are tested against a real repository in
`tests/test_gitignore.py::TestWhatInitScaffolds`; this file is about the
scaffolding itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.init import SPEC_TEMPLATE, scaffold

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_TEMPLATE = REPO_ROOT / "harness" / "templates" / "experiment.yaml"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    scaffold(tmp_path)
    return tmp_path


class TestItScaffolds:
    def test_the_two_directories(self, project: Path) -> None:
        assert (project / "experiments").is_dir()
        assert (project / "runs").is_dir()

    def test_the_marker_project_root_looks_for(self, project: Path) -> None:
        """`experiments/` is what `project_root()` walks up to find, so an
        empty one still earns its place — it is what stops a pip-installed
        harness writing run history into site-packages."""
        assert (project / "experiments").is_dir()

    def test_the_blank_contract(self, project: Path) -> None:
        assert (project / "experiments" / SPEC_TEMPLATE).is_file()

    def test_the_copy_is_the_shipped_template_byte_for_byte(self, project: Path) -> None:
        """Not a paraphrase kept in step by hand. One blank form, one file."""
        written = (project / "experiments" / SPEC_TEMPLATE).read_bytes()
        assert written == SHIPPED_TEMPLATE.read_bytes()

    def test_the_gitignore(self, project: Path) -> None:
        assert (project / ".gitignore").is_file()


class TestItDoesNotArmTheProject:
    """#21. The guard's own regression test lives in tests/test_guard_hook.py,
    where the bash machinery is; this is the same property stated where
    somebody editing `init` will see it."""

    def test_nothing_it_writes_is_a_dot_yaml(self, project: Path) -> None:
        """The guard globs `experiments/*.yaml` and never reads the file, so
        a blank contract written under that name unlocked training on every
        scaffolded project — using the one file the validator pins as invalid.
        """
        assert list((project / "experiments").glob("*.yaml")) == []

    def test_the_template_is_still_the_invalid_one(self, project: Path) -> None:
        """Renaming it must not have quietly swapped in a form that passes.

        `tests/test_validate.py::test_template_is_deliberately_invalid` pins
        the shipped file; this pins that the scaffolded copy is that file's
        twin, so a future "let us ship a valid starter contract" has to break
        one of the two on its way past.
        """
        from harness.validate import validate

        problems = validate(project / "experiments" / SPEC_TEMPLATE)
        assert any("baseline.name" in p for p in problems)


class TestItIsIdempotent:
    def test_a_second_run_creates_nothing(self, project: Path) -> None:
        actions = scaffold(project)
        assert all("created" not in line for line in actions), actions

    def test_a_second_run_changes_no_bytes(self, project: Path) -> None:
        before = {
            p: p.read_bytes()
            for p in sorted(project.rglob("*"))
            if p.is_file()
        }
        scaffold(project)
        after = {p: p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}
        assert after == before

    def test_it_reports_what_was_already_there(self, project: Path) -> None:
        actions = scaffold(project)
        joined = "\n".join(actions)
        assert "exists   experiments/" in joined
        assert "exists   runs/" in joined
        assert f"exists   experiments/{SPEC_TEMPLATE}" in joined
        assert "exists   .gitignore" in joined


class TestTheLegacyContract:
    """Every project scaffolded before #21 has `experiments/experiment.yaml`,
    and renaming what `init` writes from here on does nothing for any of them.
    Re-running `init` is the only moment the harness gets to say so."""

    def test_it_names_a_blank_contract_left_by_the_old_init(self, project: Path) -> None:
        legacy = project / "experiments" / "experiment.yaml"
        legacy.write_bytes(SHIPPED_TEMPLATE.read_bytes())

        actions = "\n".join(scaffold(project))

        assert "WARNING" in actions
        assert "experiments/experiment.yaml is the blank form" in actions
        assert "#21" in actions

    def test_it_does_not_delete_it(self, project: Path) -> None:
        """Reporting is the whole job. Deleting a file in someone's project
        because it looks unused is not something a scaffolder gets to do."""
        legacy = project / "experiments" / "experiment.yaml"
        legacy.write_bytes(SHIPPED_TEMPLATE.read_bytes())
        scaffold(project)
        assert legacy.is_file()

    def test_a_filled_contract_is_left_unmentioned(self, project: Path) -> None:
        """Byte comparison, not validation. Somebody part way through filling
        the form in is having a different conversation, and `validate` is
        where it belongs."""
        legacy = project / "experiments" / "experiment.yaml"
        legacy.write_text(
            SHIPPED_TEMPLATE.read_text(encoding="utf-8") + "\n# mine now\n",
            encoding="utf-8",
        )

        actions = "\n".join(scaffold(project))

        assert "WARNING" not in actions

    def test_nothing_is_said_when_there_is_no_legacy_file(self, project: Path) -> None:
        assert "WARNING" not in "\n".join(scaffold(project))
