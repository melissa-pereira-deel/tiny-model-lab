"""Tests for the git provenance a run manifest records.

`git_sha` names the last commit. The claim that leans on it -- *the contract
predates the run* -- also needs to know whether the tree that ran was that
commit, and nothing recorded that (#38). A run with an uncommitted edit to its
contract produced a manifest identical to one from a clean tree.

These ask a real git about real repositories in `tmp_path`, rather than mocking
the subprocess: what is being pinned is what `git status --porcelain` says, and
a mock would only pin what the mock says.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from harness.experiment import Experiment, _git_dirty, _git_sha, record_eval, start_run
from harness.promote import promote

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_SPEC = REPO_ROOT / "examples" / "01-hello-tiny" / "experiment.yaml"

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="asks a real git")


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the machine's git config out of the answer.

    A global `status.showUntrackedFiles=no` or a system `core.autocrlf` would
    change what `git status --porcelain` prints, and with it these results.
    The harness inherits the same environment, so this isolates both sides.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    # Stop discovery at tmp_path, so a directory in here is never mistaken for
    # part of whatever repository the temp dir happens to live inside.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve()))


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c", "user.name=tiny-model-lab tests",
            "-c", "user.email=tests@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def clean_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real repository with one committed file and nothing else, as the project root."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    # Bytes with no newline, so no line-ending conversion can enter into it.
    (repo / "contract.yaml").write_bytes(b"task: signed before the run")
    git(repo, "add", "contract.yaml")
    git(repo, "commit", "-q", "-m", "sign the contract")
    monkeypatch.setenv("TINY_MODEL_LAB_ROOT", str(repo))
    return repo


@pytest.fixture
def not_a_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    monkeypatch.setenv("TINY_MODEL_LAB_ROOT", str(outside))
    return outside


@needs_git
class TestGitDirty:
    def test_a_clean_repo_is_false(self, clean_repo: Path) -> None:
        assert _git_dirty() is False

    def test_a_modified_tracked_file_is_true(self, clean_repo: Path) -> None:
        """The case in the issue: the contract edited after it was committed."""
        (clean_repo / "contract.yaml").write_bytes(b"task: edited after signing")
        assert _git_dirty() is True

    def test_a_staged_change_is_true(self, clean_repo: Path) -> None:
        (clean_repo / "contract.yaml").write_bytes(b"task: edited and staged")
        git(clean_repo, "add", "contract.yaml")
        assert _git_dirty() is True

    def test_an_untracked_file_is_true(self, clean_repo: Path) -> None:
        """A new runner nobody committed ran just as much as an edited one did."""
        (clean_repo / "train_v2.py").write_bytes(b"print('not in HEAD')")
        assert _git_dirty() is True

    def test_it_asks_the_same_tree_as_git_sha(
        self, clean_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both go through `project_root()`, found here by its `experiments/`
        marker rather than the env var. A dirty flag about one tree beside a
        sha from another would be worse than no flag."""
        (clean_repo / "experiments").mkdir()  # empty, so git does not see it
        monkeypatch.delenv("TINY_MODEL_LAB_ROOT")
        monkeypatch.chdir(clean_repo / "experiments")

        assert _git_sha() == git(clean_repo, "rev-parse", "--short", "HEAD").strip()
        assert _git_dirty() is False
        (clean_repo / "contract.yaml").write_bytes(b"task: edited")
        assert _git_dirty() is True


class TestGitDirtyCannotTell:
    """Every way of not knowing is `None`, and none of them is `False`."""

    def test_a_directory_that_is_not_a_repo_is_none(self, not_a_repo: Path) -> None:
        assert _git_dirty() is None

    @needs_git  # to build the clean repo; the call under test then cannot find it
    def test_no_git_on_path_is_none_even_for_a_clean_repo(
        self, clean_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The tree really is clean here, and the answer is still `None`.

        Git is not mocked away; it is genuinely unfindable, the way it is on a
        machine without it. If this returned `False` the function would be
        guessing, and happening to guess right.
        """
        assert _git_dirty() is False  # git can see it is clean...
        empty = tmp_path / "empty-path"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
        assert shutil.which("git") is None
        assert _git_dirty() is None


class TestTheManifestRecordsIt:
    def manifest(self, run_dir: Path) -> dict:
        return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    @needs_git
    def test_it_sits_beside_git_sha(self, clean_repo: Path, tmp_path: Path) -> None:
        manifest = self.manifest(start_run(Experiment.from_yaml(EXAMPLE_SPEC), tmp_path / "runs"))
        keys = list(manifest)
        assert "git_dirty" in keys
        assert keys.index("git_dirty") == keys.index("git_sha") + 1
        assert manifest["git_dirty"] is False

    @needs_git
    def test_a_dirty_tree_is_recorded_as_true(self, clean_repo: Path, tmp_path: Path) -> None:
        (clean_repo / "contract.yaml").write_bytes(b"task: edited after signing")
        manifest = self.manifest(start_run(Experiment.from_yaml(EXAMPLE_SPEC), tmp_path / "runs"))
        assert manifest["git_dirty"] is True

    @needs_git
    def test_starting_a_run_does_not_dirty_its_own_record(self, clean_repo: Path) -> None:
        """The run directory is created inside the repo before the manifest is
        written. It is empty at the moment git is asked, so git cannot see it."""
        run_dir = start_run(Experiment.from_yaml(EXAMPLE_SPEC), clean_repo / "runs")
        assert self.manifest(run_dir)["git_dirty"] is False

    def test_outside_a_repo_it_is_null_not_false(self, not_a_repo: Path, tmp_path: Path) -> None:
        run_dir = start_run(Experiment.from_yaml(EXAMPLE_SPEC), tmp_path / "runs")
        assert '"git_dirty": null' in (run_dir / "manifest.json").read_text(encoding="utf-8")
        assert self.manifest(run_dir)["git_dirty"] is None


class TestTheChampionCardCarriesIt:
    """The card copies `git_sha` from the manifest, so it copies this beside it."""

    def promoted_card(self, tmp_path: Path, *, drop_field: bool = False) -> dict:
        exp = Experiment.from_yaml(EXAMPLE_SPEC)
        exp.baseline.value = 0.50
        exp.budgets.max_size_kb = 1000
        run_dir = start_run(exp, runs_dir=tmp_path / "runs")
        record_eval(
            run_dir, variant="v1", metric_value=0.91,
            size_kb=1.0, p95_ms=2.0, elapsed_minutes=0.2,
        )
        if drop_field:  # a manifest written before #38
            path = run_dir / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            del manifest["git_dirty"]
            path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        artifact = tmp_path / "model.onnx"
        artifact.write_bytes(b"x")
        champion = tmp_path / "champion"
        result = promote(run_dir, artifact, champion_dir=champion, ledger=tmp_path / "L.md")
        assert result.startswith("PROMOTED"), result
        return json.loads((champion / "champion.json").read_text(encoding="utf-8"))

    @needs_git
    def test_the_card_copies_it_beside_git_sha(self, clean_repo: Path, tmp_path: Path) -> None:
        card = self.promoted_card(tmp_path)
        keys = list(card)
        assert keys.index("git_dirty") == keys.index("git_sha") + 1
        assert card["git_dirty"] is False

    def test_an_older_manifest_promotes_as_unknown(self, not_a_repo: Path, tmp_path: Path) -> None:
        """Nothing refuses on this field yet, so a manifest without it still
        promotes -- and the card says null, because that manifest cannot say."""
        card = self.promoted_card(tmp_path, drop_field=True)
        assert card["git_dirty"] is None
