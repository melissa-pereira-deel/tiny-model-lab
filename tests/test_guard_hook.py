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
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "guard-experiment.sh"
SPEC_DIR = REPO_ROOT / "experiments"

# Skipped on Windows on purpose, not by accident. A Windows runner has Git Bash
# on PATH, so `shutil.which("bash")` alone would let these run against a POSIX
# PATH that means nothing there. The workflow layer is bash-only and the README
# says so; this is that decision written down where it is enforced (#11).
pytestmark = [
    pytest.mark.skipif(shutil.which("bash") is None, reason="guard is a bash hook"),
    pytest.mark.skipif(os.name == "nt", reason="bash-only workflow layer; see #11"),
]


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
    (tmp_path / SPEC_DIR.name / "tagger.yaml").write_text("task: t\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def scaffolded_project(tmp_path: Path) -> Path:
    """A project straight out of `python -m harness init`, untouched.

    The real thing, not an imitation: this calls `scaffold()` so the test
    breaks if init ever goes back to writing a `.yaml`.
    """
    from harness.init import scaffold

    scaffold(tmp_path)
    return tmp_path


@pytest.fixture
def spiked_project(tmp_path: Path) -> Path:
    """A project holding a spike record and nothing else.

    A spike record is `experiments/<slug>.spike.md`. The guard globs
    `experiments/*.yaml`, so it must not count — see the tests below.
    """
    (tmp_path / SPEC_DIR.name).mkdir()
    (tmp_path / SPEC_DIR.name / "tagger.spike.md").write_text(
        "---\nquestion: q\ninforms: scope\n---\n", encoding="utf-8"
    )
    return tmp_path


BLOCKED_WITHOUT_A_SPEC = [
    "python train.py",
    "python my_train.py",
    "python3 -m harness.train",
    f"python {SPEC_DIR.name}/tagger.py",
    "uv run my_train.py",
    "./do_train.py",
    "cd src && python train.py",
    # A spike script that trains is not a spike. The record does not change
    # that, and neither does living outside experiments/.
    "python spikes/train_probe.py",
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
    # Spike code is meant to be cheap and to run without ceremony. It lives
    # outside experiments/ precisely because the pattern above blocks scripts
    # run from there while no contract exists.
    "python spikes/bench.py",
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


@pytest.mark.parametrize("command", BLOCKED_WITHOUT_A_SPEC)
def test_a_spike_record_does_not_unlock_training(command: str, spiked_project: Path) -> None:
    """The test that makes the file format a decision rather than an accident.

    A spike is a measurement, not a contract. If `experiments/<slug>.spike.md`
    counted towards the guard's unlock, writing one would authorise a training
    run without a named baseline, a size budget or a kill criterion -- a way
    around /scope wearing the clothes of a step before it.

    Nothing in `guard-experiment.sh` mentions spikes; it globs `*.yaml` and a
    spike record is `.md`. That is the safest version of this -- no new
    pattern to get wrong -- but it means the property is a coincidence of two
    files unless something pins it. This is that something.
    """
    assert run_guard(command, spiked_project), f"a spike record must not unlock: {command}"


def test_a_spike_record_alongside_a_contract_changes_nothing(
    scoped_project: Path,
) -> None:
    """The other direction: it does not *lock* anything either."""
    (scoped_project / SPEC_DIR.name / "tagger.spike.md").write_text("---\nquestion: q\n---\n", encoding="utf-8")
    assert not run_guard(TRAINING_COMMAND, scoped_project)


@pytest.mark.parametrize("command", BLOCKED_WITHOUT_A_SPEC)
def test_scaffolding_a_project_does_not_unlock_training(
    command: str, scaffolded_project: Path
) -> None:
    """#21, and the one the guard exists for.

    `init` used to copy the blank contract to `experiments/experiment.yaml`.
    The guard asks whether any `experiments/*.yaml` exists and never reads it,
    so every scaffolded project had training unlocked from minute one -- by
    the single file `tests/test_validate.py::test_template_is_deliberately_invalid`
    pins as invalid. The harness disarmed its own tripwire during setup, at
    exactly the moment the tripwire is for: the first run in a fresh repo.

    It writes `experiment.yaml.template` now. Nothing in the guard knows that;
    the property is again a coincidence of two filenames, so this pins it the
    way `spiked_project` above pins the `.md` one.
    """
    assert run_guard(command, scaffolded_project), f"a fresh scaffold must not unlock: {command}"


def test_the_scaffolded_form_unlocks_once_you_choose_to_copy_it(
    scaffolded_project: Path,
) -> None:
    """The hole this deliberately leaves, pinned so it stays deliberate.

    Copying the blank form to `<task>.yaml` without filling it in still
    unlocks training -- the guard reads no files, by design, and teaching it
    to parse YAML would cost the no-interpreter degradation that
    `TestWithoutPython3` covers. The difference from #21 is that this is now
    something somebody did, rather than something setup did for them.
    """
    spec_dir = scaffolded_project / SPEC_DIR.name
    shutil.copy2(spec_dir / "experiment.yaml.template", spec_dir / "tagger.yaml")
    assert not run_guard(TRAINING_COMMAND, scaffolded_project)


def test_worked_example_runs_even_when_scoped(scoped_project: Path) -> None:
    """The exemption is by path, so it must hold in both states."""
    assert not run_guard("python examples/01-hello-tiny/run.py", scoped_project)


TRAINING_COMMAND = BLOCKED_WITHOUT_A_SPEC[0]


class TestWithoutPython3:
    """The guard parses its payload with an interpreter, and used to hardcode
    `python3` behind `|| echo ""`.

    Git Bash on Windows generally has `python`, not `python3` — so on the one
    platform where the guard is most likely to be quietly missing, a missing
    interpreter produced an empty command, matched nothing, and let the run
    through without a word. Failing open is the one failure mode a guard may
    not have (#11).
    """

    @staticmethod
    def fake_bin(tmp_path: Path, interpreter_named: str | None = None) -> Path:
        """A PATH with the tools the hook needs and no `python3`.

        The interpreter is exposed under whatever name the test asks for, or
        not at all — which is the point. Symlinked from `sys.executable` rather
        than `which("python")`, since a machine with only `python3` installed
        would otherwise skip the case this class exists for.
        """
        binned = tmp_path / "bin"
        binned.mkdir()
        for tool in ("bash", "cat", "printf"):
            real = shutil.which(tool)
            if real:
                (binned / tool).symlink_to(real)
        if interpreter_named:
            (binned / interpreter_named).symlink_to(sys.executable)
        return binned

    def run(self, command: str, project_dir: Path, path: Path) -> str:
        proc = subprocess.run(
            [shutil.which("bash") or "bash", str(HOOK)],
            input=json.dumps({"tool_input": {"command": command}}),
            capture_output=True,
            text=True,
            env={"PATH": str(path), "CLAUDE_PROJECT_DIR": str(project_dir)},
            check=False,
        )
        assert proc.returncode == 0, f"guard crashed: {proc.stderr}"
        json.loads(proc.stdout)  # Claude Code parses this; it must stay JSON.
        return proc.stdout

    def test_python_without_python3_still_guards(self, tmp_path: Path) -> None:
        """The Windows case: Git Bash carries `python`, not `python3`."""
        path = self.fake_bin(tmp_path, interpreter_named="python")
        out = self.run(TRAINING_COMMAND, tmp_path / "unscoped", path)
        assert '"decision":"block"' in out.replace(" ", "")
        assert "No Python interpreter" not in out, "it found one; do not claim otherwise"

    def test_no_interpreter_still_blocks_training(self, tmp_path: Path) -> None:
        """It matches the raw payload instead. Cruder, and not silent."""
        path = self.fake_bin(tmp_path)
        out = self.run(TRAINING_COMMAND, tmp_path / "unscoped", path)
        assert '"decision":"block"' in out.replace(" ", "")
        assert "No Python interpreter on PATH" in out, "the degradation must be stated"

    def test_no_interpreter_does_not_block_everything(self, tmp_path: Path) -> None:
        """The counterweight. Refusing every Bash call because python is
        missing would be a guard nobody keeps switched on."""
        path = self.fake_bin(tmp_path)
        assert self.run("ls -la", tmp_path / "unscoped", path).strip() == "{}"

    def test_no_interpreter_still_allows_a_scoped_project(
        self, tmp_path: Path, scoped_project: Path
    ) -> None:
        path = self.fake_bin(tmp_path)
        assert self.run(TRAINING_COMMAND, scoped_project, path).strip() == "{}"
