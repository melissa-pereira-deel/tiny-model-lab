"""Scaffold a project so the harness has somewhere to put its history.

Usage:  python -m harness init [directory]

Creates `experiments/` and `runs/`, and drops a blank `experiment.yaml` next to
them. `experiments/` is also the marker `project_root()` looks for, so running
this is what tells the harness which directory is yours.

It does not install the Claude Code layer. `.claude/` is copied, not packaged —
see the README. The gates work without it; the subagents do not exist without it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "templates"


def scaffold(root: str | Path | None = None) -> list[str]:
    """Create the project skeleton. Returns a line per action, for printing."""
    root = Path(root) if root else Path.cwd()
    actions: list[str] = []

    for name in ("experiments", "runs"):
        target = root / name
        if target.is_dir():
            actions.append(f"  exists   {name}/")
        else:
            target.mkdir(parents=True)
            actions.append(f"  created  {name}/")

    spec = root / "experiments" / "experiment.yaml"
    if spec.exists():
        actions.append("  exists   experiments/experiment.yaml (left alone)")
    else:
        shutil.copy2(TEMPLATES / "experiment.yaml", spec)
        actions.append("  created  experiments/experiment.yaml")

    return actions
