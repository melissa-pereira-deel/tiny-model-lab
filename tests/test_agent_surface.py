"""The agent surface is a claim the docs make. Check it against the files.

`data-builder` went without a slash command while the other four subagents had
one, and nothing noticed (#8). It was step 2 of five in `AGENTS.md` — on the
main path — and the one step you had to know to invoke by name.

That is the kind of drift no runtime test catches, because none of this is
imported by anything. So it is checked structurally: every subagent is reachable
by a command, and every command is documented.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS = REPO_ROOT / ".claude" / "agents"
COMMANDS = REPO_ROOT / ".claude" / "commands"
PROMPTING_GUIDE = REPO_ROOT / "docs" / "prompting-guide.md"

# A subagent may go without a command, but saying so costs a sentence — the
# same device as `measured_at_runtime` and `dataset.split_rationale`. Empty
# on purpose: if you add the sixth subagent and leave it unreachable, this
# test fails until you make #8's decision again, out loud.
WITHOUT_A_COMMAND: dict[str, str] = {}


def names(directory: Path) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.md"))


def test_the_agent_directories_are_not_empty() -> None:
    """Guards the rest of this file: globs that match nothing pass vacuously."""
    assert names(AGENTS)
    assert names(COMMANDS)


@pytest.mark.parametrize("subagent", names(AGENTS))
def test_every_subagent_is_reachable_by_a_command(subagent: str) -> None:
    if subagent in WITHOUT_A_COMMAND:
        pytest.skip(f"deliberately has no command: {WITHOUT_A_COMMAND[subagent]}")
    delegating = [c.name for c in COMMANDS.glob("*.md") if subagent in c.read_text()]
    assert delegating, (
        f"`{subagent}` has no command naming it. Either add one under "
        f".claude/commands/, or add it to WITHOUT_A_COMMAND with the reason — "
        f"which is the decision #8 asked for."
    )


@pytest.mark.parametrize("command", names(COMMANDS))
def test_every_command_is_in_the_prompting_guide(command: str) -> None:
    """The guide is where the surface is advertised.

    It described the gap in #8 as a fact rather than as a defect, which is what
    made it read as intentional for as long as it did.
    """
    assert f"`/{command} " in PROMPTING_GUIDE.read_text(), (
        f"/{command} is not in the table in docs/prompting-guide.md"
    )


@pytest.mark.parametrize("command", names(COMMANDS))
def test_every_command_has_a_description(command: str) -> None:
    """Claude Code shows the frontmatter `description` in its command list."""
    text = (COMMANDS / f"{command}.md").read_text()
    match = re.search(r"^description:\s*(\S.*)$", text, flags=re.MULTILINE)
    assert match, f"/{command} has no frontmatter description"
    assert len(match.group(1).split()) >= 5, f"/{command}'s description is too terse to pick from"
