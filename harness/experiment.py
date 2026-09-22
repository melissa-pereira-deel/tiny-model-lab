"""Experiment specs and run directories.

An Experiment is a contract you sign *before* training. It names the baseline
you must beat and the budgets you must respect. The harness refuses to start a
run without one, which is the whole point: it makes "I'll just try one more
thing" cost you an explicit edit to a file.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """Where this project's `runs/`, `champion/` and ledger live.

    Resolved per call rather than at import, because the old constant was
    `Path(__file__).parent.parent` — the *installed package's* parent. Under a
    normal `pip install` that is site-packages, so the harness wrote your run
    history into site-packages and the only adoption model that worked was
    cloning the repo and living inside it.

    Order: an explicit argument wherever one is offered, then
    TINY_MODEL_LAB_ROOT, then the nearest ancestor of the working directory
    holding an `experiments/` directory — the thing `/scope` creates — then the
    working directory itself. Inside a clone every route lands on the clone, so
    nothing about the existing repo changes.
    """
    env = os.environ.get("TINY_MODEL_LAB_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    start = Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "experiments").is_dir():
            return candidate
    return start


def runs_root() -> Path:
    return project_root() / "runs"


# Nielsen's response-time limits (Miller 1968; Nielsen, Usability Engineering,
# 1993). These are perceptual facts about humans, not engineering targets, which
# is why they belong in the harness rather than in a config someone can tune.
LATENCY_BANDS_MS = {
    "instant": 100,      # feels like direct manipulation; no spinner needed
    "flow": 1000,        # thought stays unbroken; no feedback needed
    "attention": 10000,  # upper limit of held attention; needs progress UI
}


# Fragments that mean "lower is better", however the metric is spelled.
# Deliberately short and openly incomplete, in the same spirit as
# RANDOM_SPLIT_NAMES in validate.py: this reads a name, not a metric, so it can
# never catch every loss and it can be fooled by anyone determined. Its job is
# to make the honest answer cost one line instead of costing a silent promotion
# of the worse model.
#
# Substrings rather than whole words, so `val_loss`, `word error rate` and
# `test_rmse` are all caught.
LOSS_SHAPED_METRICS = frozenset(
    {
        "loss",
        "error",
        "perplexity",
        "ppl",
        "wer",
        "cer",
        "rmse",
        "mse",
        "mae",
        "nll",
        "entropy",
        "distance",
        "latency",
        "regret",
    }
)


def reads_as_a_loss(metric: str) -> bool:
    """Does this metric's *name* suggest lower is better?

    Name only. Nothing here inspects a number, and `accuracy_loss_delta` would
    fool it. See LOSS_SHAPED_METRICS.
    """
    normalised = metric.strip().lower()
    return any(fragment in normalised for fragment in LOSS_SHAPED_METRICS)


@dataclass
class Budgets:
    """Hard limits. Exceeding any one of these fails the run."""

    max_size_kb: float
    latency_band: str = "instant"
    max_latency_ms: float | None = None  # defaults to the band's ceiling
    max_wallclock_minutes: int = 600     # an overnight run, roughly
    patience_evals: int = 5              # stop after N evals with no strict gain

    def __post_init__(self) -> None:
        if self.latency_band not in LATENCY_BANDS_MS:
            raise ValueError(
                f"latency_band must be one of {sorted(LATENCY_BANDS_MS)}, "
                f"got {self.latency_band!r}"
            )
        if self.max_latency_ms is None:
            self.max_latency_ms = float(LATENCY_BANDS_MS[self.latency_band])


@dataclass
class Baseline:
    """The thing you have to beat.

    `kind` is deliberately constrained. "none" is not an option: if you cannot
    name something simpler that already does this job, you have not scoped the
    task yet, and a model is the wrong next step.
    """

    kind: str  # deterministic | classical | existing_tool | previous_run
    name: str
    metric: str
    value: float
    notes: str = ""
    # A runner may measure the baseline and assign `value` before start_run().
    # Saying so here is a declaration, not an exemption: baseline_gate refuses a
    # run whose number never arrived, so the flag cannot manufacture a zero
    # baseline that everything beats.
    measured_at_runtime: bool = False
    # Which way the metric runs. `None` means nobody said, and every gate then
    # assumes higher is better, which is what they have always assumed.
    #
    # Declaring it is only mandatory when the metric's name reads like a loss
    # -- see `direction_is_ambiguous`. That is the same device as
    # `measured_at_runtime`: the cost of the honest answer is one line, and
    # the gate refuses the case where the answer is missing and matters.
    #
    # It lives in the contract rather than in a call argument because a
    # manifest has to be re-gateable later, and an argument is not written
    # down anywhere.
    higher_is_better: bool | None = None

    VALID_KINDS = ("deterministic", "classical", "existing_tool", "previous_run")

    def __post_init__(self) -> None:
        if self.kind not in self.VALID_KINDS:
            raise ValueError(
                f"baseline.kind must be one of {self.VALID_KINDS}, got {self.kind!r}"
            )

    def prefers_higher(self) -> bool:
        """Resolve the direction. Undeclared is higher, as it always has been."""
        return True if self.higher_is_better is None else self.higher_is_better

    def direction_is_ambiguous(self) -> bool:
        """Undeclared, on a metric whose *name* reads like something to minimise.

        The two halves both matter. Undeclared alone is fine -- `accuracy` has
        meant higher-is-better since the first commit and nobody should have to
        restate it. A loss-shaped name alone is fine too: say
        `higher_is_better: false` and the gates obey you.

        It is the combination that is almost always an accident, and it is the
        expensive kind: the gate passes a model that is worse than the
        baseline, prints PASS, and promotes it.
        """
        return self.higher_is_better is None and reads_as_a_loss(self.metric)


@dataclass
class Experiment:
    task: str
    hypothesis: str
    baseline: Baseline
    budgets: Budgets
    target: str = "onnx-web"  # onnx-web | coreml | tflite | wgsl | mlx-local
    dataset: dict[str, Any] = field(default_factory=dict)
    architecture: dict[str, Any] = field(default_factory=dict)
    kill_criteria: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Experiment:
        """The inverse of `to_dict`. Lossless on purpose.

        A run manifest is the only record that survives the session, so reading
        one back has to return the whole contract — including `kill_criteria`,
        which is what tells you a project should end rather than a run.
        """
        return cls(
            task=raw["task"],
            hypothesis=raw["hypothesis"],
            baseline=Baseline(**raw["baseline"]),
            budgets=Budgets(**raw["budgets"]),
            target=raw.get("target", "onnx-web"),
            dataset=raw.get("dataset", {}),
            architecture=raw.get("architecture", {}),
            kill_criteria=raw.get("kill_criteria", []),
            tags=raw.get("tags", []),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> Experiment:
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root(),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001 - no git, no repo, shallow checkout: all fine
        return "unknown"


def start_run(experiment: Experiment, runs_dir: Path | None = None) -> Path:
    """Create a timestamped run directory with a provenance manifest.

    Corpora and checkpoints are gitignored; the manifest is not. What gets
    committed is the decision trail, not the artifacts.
    """
    runs_dir = Path(runs_dir) if runs_dir else runs_root()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in experiment.task)[:48]
    run_dir = runs_dir / f"{stamp}--{slug}"
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_dir.name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "experiment": experiment.to_dict(),
        "status": "running",
        "evals": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def record_eval(run_dir: Path, **metrics: Any) -> dict[str, Any]:
    """Append one evaluation to the run manifest and return the updated manifest."""
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics["at"] = datetime.now(timezone.utc).isoformat()
    manifest["evals"].append(metrics)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def finish_run(run_dir: Path, status: str, reason: str = "") -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest["stopped_reason"] = reason
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# Gate metrics every eval must carry. `record_eval` takes **metrics and validates
# nothing, so a runner that forgets one of these writes a manifest that only
# fails later, inside whatever code improvised its own reading.
REQUIRED_EVAL_KEYS = ("metric_value", "size_kb", "p95_ms")


def load_run(run_dir: str | Path) -> tuple[dict[str, Any], Experiment]:
    """Read a run manifest back into (manifest, Experiment).

    The reader lives beside the writers — `start_run`, `record_eval` and
    `finish_run` — because the format has exactly one owner. Every caller that
    loads a run by hand is a chance for two callers to disagree about which eval
    is "the" candidate, and the gates are supposed to be the part you can trust.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest.json in {run_dir} — is that a run directory?")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for eval_index, ev in enumerate(manifest.get("evals", [])):
        missing = [k for k in REQUIRED_EVAL_KEYS if k not in ev]
        if missing:
            raise KeyError(
                f"{manifest_path}: eval {eval_index} is missing {', '.join(missing)}. "
                "record_eval() accepts any keyword, so a runner has to pass every "
                f"gate metric itself: {', '.join(REQUIRED_EVAL_KEYS)}."
            )
    return manifest, Experiment.from_dict(manifest["experiment"])


def eval_history(manifest: dict[str, Any]) -> list[float]:
    """Every recorded metric value, oldest first — what the patience gate reads."""
    return [ev["metric_value"] for ev in manifest.get("evals", [])]
