"""The PreToolUse guard is a claim the README makes. Test it like one.

The guard's whole job is to refuse a training command when no experiment file
exists. That job is easy to break silently: the patterns are shell globs in a
file nothing imports, so a typo in them fails open and nobody notices until a
run happens without a contract.

These tests also pin the *false positives*. An earlier version matched any
command mentioning a training path, which blocked `git commit` on a message
discussing train.py and blocked editing the guard itself. A guard that fires on
prose gets switched off, and a switched-off guard protects nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "guard-experiment.sh"
SPEC_DIR = REPO_ROOT / "experiments"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="guard is a bash hook"
)


def run_guard(command: str, project_dir: Path) -> bool:
    """Return True if the guard blocks `command`."""
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(project_dir)},
        check=False,
    )
    assert proc.returncode == 0, f"guard crashed: {proc.stderr}"
    return '"decision":"block"' in proc.stdout.replace(" ", "")


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """A project directory with no experiment file."""
    return tmp_path


@pytest.fixture
def scoped_project(tmp_path: Path) -> Path:
    """A project directory that has been through /scope."""
    (tmp_path / SPEC_DIR.name).mkdir()
    (tmp_path / SPEC_DIR.name / "tagger.yaml").write_text("task: t\n")
    return tmp_path


BLOCKED_WITHOUT_A_SPEC = [
    "python train.py",
    "python my_train.py",
    "python3 -m harness.train",
    f"python {SPEC_DIR.name}/tagger.py",
    "uv run my_train.py",
    "./do_train.py",
    "cd src && python train.py",
]

# Commands that merely *mention* training, or that the repo itself depends on.
ALWAYS_ALLOWED = [
    "python examples/01-hello-tiny/run.py",  # CI and the README's one-second promise
    "pytest -q",
    "ruff check .",
    "git commit -m 'fix train.py guard'",
    f"grep -rn foo {SPEC_DIR.name}/",
    "cat .claude/hooks/guard-experiment.sh",
    "ls -la",
]


@pytest.mark.parametrize("command", BLOCKED_WITHOUT_A_SPEC)
def test_blocks_training_without_an_experiment_file(command: str, empty_project: Path) -> None:
    assert run_guard(command, empty_project), f"should have blocked: {command}"


@pytest.mark.parametrize("command", BLOCKED_WITHOUT_A_SPEC)
def test_allows_the_same_command_once_scoped(command: str, scoped_project: Path) -> None:
    assert not run_guard(command, scoped_project), f"should have allowed: {command}"


@pytest.mark.parametrize("command", ALWAYS_ALLOWED)
def test_never_blocks_these(command: str, empty_project: Path) -> None:
    assert not run_guard(command, empty_project), f"should never block: {command}"


def test_worked_example_runs_even_when_scoped(scoped_project: Path) -> None:
    """The exemption is by path, so it must hold in both states."""
    assert not run_guard("python examples/01-hello-tiny/run.py", scoped_project)
