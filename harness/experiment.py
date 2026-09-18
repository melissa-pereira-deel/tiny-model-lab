"""Experiment specs and run directories.

An Experiment is a contract you sign *before* training. It names the baseline
you must beat and the budgets you must respect. The harness refuses to start a
run without one, which is the whole point: it makes "I'll just try one more
thing" cost you an explicit edit to a file.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"

# Nielsen's response-time limits (Miller 1968; Nielsen, Usability Engineering,
# 1993). These are perceptual facts about humans, not engineering targets, which
# is why they belong in the harness rather than in a config someone can tune.
LATENCY_BANDS_MS = {
    "instant": 100,      # feels like direct manipulation; no spinner needed
    "flow": 1000,        # thought stays unbroken; no feedback needed
    "attention": 10000,  # upper limit of held attention; needs progress UI
}


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

    VALID_KINDS = ("deterministic", "classical", "existing_tool", "previous_run")

    def __post_init__(self) -> None:
        if self.kind not in self.VALID_KINDS:
            raise ValueError(
                f"baseline.kind must be one of {self.VALID_KINDS}, got {self.kind!r}"
            )


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
    def from_yaml(cls, path: str | Path) -> "Experiment":
        raw = yaml.safe_load(Path(path).read_text())
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def start_run(experiment: Experiment, runs_dir: Path | None = None) -> Path:
    """Create a timestamped run directory with a provenance manifest.

    Corpora and checkpoints are gitignored; the manifest is not. What gets
    committed is the decision trail, not the artifacts.
    """
    runs_dir = runs_dir or RUNS_DIR
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
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return run_dir


def record_eval(run_dir: Path, **metrics: Any) -> dict[str, Any]:
    """Append one evaluation to the run manifest and return the updated manifest."""
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    metrics["at"] = datetime.now(timezone.utc).isoformat()
    manifest["evals"].append(metrics)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def finish_run(run_dir: Path, status: str, reason: str = "") -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["status"] = status
    manifest["stopped_reason"] = reason
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2))
