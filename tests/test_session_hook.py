"""The SessionEnd hook writes a tracked ledger, so its noise is everyone's.

`runs/SESSIONS.md` exists to answer "what did I actually try in March?". It
could not: the hook appended unconditionally and one working session left ten
entries inside four seconds, identical apart from the timestamp (#13).

The cause of the repeated firing is still unknown — #13 guessed subagents and
the docs rule that out, since a subagent finishing fires SubagentStop, not
SessionEnd. So these tests pin the property that holds regardless of cause: a
fire that learned nothing writes nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "log-run.sh"

# See tests/test_guard_hook.py — the Windows skip is deliberate, not incidental.
pytestmark = [
    pytest.mark.skipif(shutil.which("bash") is None, reason="the session log is a bash hook"),
    pytest.mark.skipif(os.name == "nt", reason="bash-only workflow layer; see #11"),
]

PAYLOAD = {"session_id": "a3f9c2d1-1111-2222", "reason": "prompt_input_exit"}


def fire(project_dir: Path, payload: dict | str | None = None) -> str:
    """Run the hook once. Returns stdout, which Claude Code parses as JSON."""
    if payload is None:
        payload = PAYLOAD
    body = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=body,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(project_dir)},
        check=False,
    )
    assert proc.returncode == 0, f"hook crashed: {proc.stderr}"
    return proc.stdout


def entries(project_dir: Path) -> list[str]:
    """Just the ledger lines, without the header."""
    text = (project_dir / "runs" / "SESSIONS.md").read_text()
    return [ln for ln in text.splitlines() if ln.startswith("- `")]


class TestItWritesSomething:
    def test_first_fire_creates_the_file_with_a_header(self, tmp_path: Path) -> None:
        fire(tmp_path)
        text = (tmp_path / "runs" / "SESSIONS.md").read_text()
        assert text.startswith("# Session log")
        assert "no conversation content" in text
        assert len(entries(tmp_path)) == 1

    def test_it_returns_valid_json(self, tmp_path: Path) -> None:
        """Claude Code parses stdout. A hook that prints prose is a broken hook."""
        assert json.loads(fire(tmp_path)) == {}

    def test_the_entry_names_the_session_and_the_reason(self, tmp_path: Path) -> None:
        """What actually distinguishes one line from the next.

        `runs` and `champion` are near-constant early on, which is exactly why
        the burst in #13 looked like one line repeated.
        """
        fire(tmp_path)
        line = entries(tmp_path)[0]
        assert "session a3f9c2d1" in line
        assert "prompt_input_exit" in line

    def test_it_names_the_most_recent_run(self, tmp_path: Path) -> None:
        (tmp_path / "runs" / "20260101T000000Z--older").mkdir(parents=True)
        (tmp_path / "runs" / "20260919T013000Z--config-lexer").mkdir(parents=True)
        fire(tmp_path)
        line = entries(tmp_path)[0]
        assert "runs: 2" in line
        assert "latest 20260919T013000Z--config-lexer" in line


class TestItStaysQuiet:
    def test_a_repeat_that_learned_nothing_writes_nothing(self, tmp_path: Path) -> None:
        fire(tmp_path)
        fire(tmp_path)
        assert len(entries(tmp_path)) == 1

    def test_ten_fires_leave_one_entry(self, tmp_path: Path) -> None:
        """The shape #13 actually reported: ten in four seconds."""
        for _ in range(10):
            fire(tmp_path)
        assert len(entries(tmp_path)) == 1


class TestItStillRecordsRealHistory:
    """The dedupe must not be so eager that the ledger stops being one."""

    def test_a_new_run_appends(self, tmp_path: Path) -> None:
        fire(tmp_path)
        (tmp_path / "runs" / "20260919T013000Z--config-lexer").mkdir(parents=True)
        fire(tmp_path)
        assert len(entries(tmp_path)) == 2

    def test_a_different_session_appends(self, tmp_path: Path) -> None:
        fire(tmp_path)
        fire(tmp_path, {"session_id": "beef0000-9999", "reason": "clear"})
        assert len(entries(tmp_path)) == 2

    def test_a_promoted_champion_appends(self, tmp_path: Path) -> None:
        fire(tmp_path)
        (tmp_path / "champion").mkdir()
        (tmp_path / "champion" / "champion.json").write_text(json.dumps({"task": "lex configs"}))
        fire(tmp_path)
        assert "champion: lex configs" in entries(tmp_path)[-1]


class TestItNeverBreaksTheSession:
    """A logging hook that fails a session is worse than no log at all."""

    @pytest.mark.parametrize(
        "payload",
        ["", "not json at all", "{", "[]", "null", '{"reason": "logout"}', "{}"],
        ids=["empty", "prose", "truncated", "array", "null", "no-session-id", "no-fields"],
    )
    def test_bad_input_still_exits_zero_and_records(self, tmp_path: Path, payload: str) -> None:
        assert json.loads(fire(tmp_path, payload)) == {}
        assert len(entries(tmp_path)) == 1

    def test_an_unreadable_champion_card_does_not_crash(self, tmp_path: Path) -> None:
        (tmp_path / "champion").mkdir()
        (tmp_path / "champion" / "champion.json").write_text("{ not json")
        fire(tmp_path)
        assert "champion: unreadable" in entries(tmp_path)[0]
