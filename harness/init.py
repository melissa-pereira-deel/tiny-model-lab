"""Scaffold a project so the harness has somewhere to put its history.

Usage:  python -m harness init [directory]

Creates `experiments/` and `runs/`, drops the blank contract next to them as
`experiment.yaml.template`, and writes a `.gitignore` if the project has none.
`experiments/` is also the marker `project_root()` looks for, so running this is
what tells the harness which directory is yours.

The template is written as `.template` rather than `.yaml` on purpose (#21). The
training guard asks whether any `experiments/*.yaml` exists and never reads it,
so copying a blank contract into place under that name unlocked training on
every freshly scaffolded project — using the one file in this repo that exists
in order to be invalid. Scaffolding is the wrong moment to answer a question the
guard is there to ask. Copy it to `experiments/<task>.yaml` when you have
something to put in it; doing that with the form still blank is then a decision
somebody made, rather than the default the harness handed them.

It does not install the Claude Code layer. `.claude/` is copied, not packaged —
see the README. The gates work without it; the subagents do not exist without it.
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "templates"

# The name the contract is scaffolded under. Anything not ending in `.yaml`
# would do; this one says what it is.
SPEC_TEMPLATE = "experiment.yaml.template"


def scaffold(root: str | Path | None = None) -> list[str]:
    """Create the project skeleton. Returns a line per action, for printing.

    Idempotent, and never edits a file it did not write. Re-running it on a
    project reports what is already there and changes nothing.
    """
    root = Path(root) if root else Path.cwd()
    actions: list[str] = []

    for name in ("experiments", "runs"):
        target = root / name
        if target.is_dir():
            actions.append(f"  exists   {name}/")
        else:
            target.mkdir(parents=True)
            actions.append(f"  created  {name}/")

    spec = root / "experiments" / SPEC_TEMPLATE
    if spec.exists():
        actions.append(f"  exists   experiments/{SPEC_TEMPLATE} (left alone)")
    else:
        shutil.copy2(TEMPLATES / "experiment.yaml", spec)
        actions.append(f"  created  experiments/{SPEC_TEMPLATE}")

    actions.extend(_gitignore(root))
    actions.extend(_unlocked_by_a_blank_contract(root))
    return actions


def _gitignore(root: Path) -> list[str]:
    """Write a .gitignore when the project has none (#30).

    Without one, the first `git add -A` commits the weights — the harness
    writes exports into runs/<id>/artifacts/ and `promote()` copies them again
    into champion/, so nothing warns you until the repository is too big to
    clone.

    An existing file is left exactly as it is. Appending to a file the user
    wrote is the one stateful edit worth refusing here: it cannot be done twice
    safely, and someone who already has a .gitignore has opinions about it.
    """
    target = root / ".gitignore"
    if target.exists():
        return [
            "  exists   .gitignore (left alone) -- check it covers "
            "runs/*/artifacts/ and champion/"
        ]
    shutil.copy2(TEMPLATES / "gitignore", target)
    return ["  created  .gitignore"]


def _unlocked_by_a_blank_contract(root: Path) -> list[str]:
    """Say so if `experiments/experiment.yaml` is the blank form, unchanged.

    Every project scaffolded before #21 has exactly this file, and renaming
    what `init` writes from here on does nothing for any of them. Re-running
    `init` is the only moment the harness gets to mention it.

    Byte comparison, not validation: a half-filled contract is somebody part
    way through a decision, and `validate` is where that conversation belongs.
    This reports and deletes nothing.
    """
    legacy = root / "experiments" / "experiment.yaml"
    if not legacy.is_file():
        return []
    if not filecmp.cmp(legacy, TEMPLATES / "experiment.yaml", shallow=False):
        return []
    return [
        "  WARNING  experiments/experiment.yaml is the blank form, unchanged. "
        "The training guard asks only whether some experiments/*.yaml exists, "
        f"so this unlocks training while saying nothing (#21). Rename it to "
        f"experiments/<task>.yaml and fill it in, or delete it -- the blank "
        f"form is at experiments/{SPEC_TEMPLATE}."
    ]
