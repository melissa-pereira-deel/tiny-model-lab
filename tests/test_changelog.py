"""Tests for CHANGELOG.md.

A changelog nobody is required to update is a guide, not a sensor — and the
last thing fixed in this repo was a documented rule with nothing enforcing it
(`split_by`, #15). These are the enforcement: the version cannot move without
an entry, and the category the changelog exists for cannot be quietly dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import harness

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# The Keep a Changelog six, plus the one deliberate addition. `Gate semantics`
# is separate because a gate that gets stricter invalidates a run that *passed*,
# which is not the same event as "Changed".
ALLOWED_SECTIONS = frozenset(
    {
        "Gate semantics",
        "Added",
        "Changed",
        "Deprecated",
        "Removed",
        "Fixed",
        "Security",
    }
)


@pytest.fixture(scope="module")
def text() -> str:
    return CHANGELOG.read_text(encoding="utf-8")


def released_versions(text: str) -> list[str]:
    """Every `## [x.y.z]` heading, newest first. `[Unreleased]` is not one."""
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, flags=re.MULTILINE)


class TestItExists:
    def test_the_file_is_there(self) -> None:
        assert CHANGELOG.exists()

    def test_it_has_an_unreleased_section(self, text: str) -> None:
        """Where the next rule change goes. Without it, the next person has to
        decide where to put their entry, and the usual decision is nowhere."""
        assert re.search(r"^## \[Unreleased\]", text, flags=re.MULTILINE)


class TestItTracksTheVersion:
    def test_the_current_version_is_recorded(self, text: str) -> None:
        """The load-bearing one.

        Bumping `harness.__version__` without writing a changelog entry fails
        here rather than shipping a release nobody can read the diff of.
        """
        assert harness.__version__ in released_versions(text), (
            f"harness.__version__ is {harness.__version__!r} but CHANGELOG.md has no "
            f"## [{harness.__version__}] heading. Add the release section."
        )

    def test_versions_are_newest_first(self, text: str) -> None:
        versions = [tuple(int(p) for p in v.split(".")) for v in released_versions(text)]
        assert versions == sorted(versions, reverse=True)


class TestCategoriesDoNotDrift:
    def test_every_section_is_a_known_one(self, text: str) -> None:
        """Including `Gate semantics`, which is the category this file was
        asked for. An invented heading is how a changelog stops being
        skimmable, and a dropped one is how the asked-for category vanishes."""
        found = set(re.findall(r"^### (.+)$", text, flags=re.MULTILINE))
        assert found <= ALLOWED_SECTIONS, f"unknown section(s): {sorted(found - ALLOWED_SECTIONS)}"

    def test_gate_semantics_is_still_a_category(self, text: str) -> None:
        assert "### Gate semantics" in text
