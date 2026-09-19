"""The harness command line — one front door, mirroring the slash commands.

Usage:
  python -m harness init     [directory]
  python -m harness validate <experiment.yaml>
  python -m harness gate     <run-dir>
  python -m harness ship     <run-dir> <artifact>

`/gate` and `/ship` previously had no entry point at all, so every invocation
re-improvised the manifest loading. Two callers improvising separately can
disagree about which eval is 'the' candidate, and the gates are the part that is
supposed to be worth trusting every loop.

What this prints is arithmetic. The design checks and the final
promote / iterate / stop call stay with the agent, because nothing in a run
manifest encodes whether a wrong answer has a designed failure state.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .experiment import LATENCY_BANDS_MS, project_root
from .gates import gate_run
from .init import scaffold
from .promote import promote
from .validate import validate

DESIGN_CHECKS_NOTE = (
    "Design checks are not computable from a manifest — failure state, "
    "uncertainty legibility, user override, privacy legibility, first-run cost. "
    "Run them from .claude/skills/design-eval/, then make the "
    "promote / iterate / stop call yourself. This reports gates, not judgement."
)


def cmd_init(argv: list[str]) -> int:
    if len(argv) > 1:
        print(__doc__)
        return 2
    root = Path(argv[0]) if argv else Path.cwd()
    print(f"scaffolding {root.resolve()}")
    for line in scaffold(root):
        print(line)
    print(f"\nproject root is now {project_root()}")
    print("next: fill in the spec it wrote, then `python -m harness validate` it")
    return 0


def cmd_validate(argv: list[str]) -> int:
    """Validate one or more experiment files.

    Takes several because a shell glob is the natural way to check them all, and
    a command that accepts exactly one would start failing the moment this repo
    grows a second example. Reports every file rather than stopping at the first
    bad one: you want the whole list, not the first item on it.
    """
    if not argv:
        print(__doc__)
        return 2
    status = 0
    for path in argv:
        problems = validate(path)
        if problems:
            print(f"INVALID — {path}")
            for p in problems:
                print(f"  - {p}")
            status = 1
        else:
            print(f"VALID — {path}")
    return status


def cmd_gate(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    run_dir = argv[0]
    try:
        passed, results, ctx = gate_run(run_dir)
    except (FileNotFoundError, KeyError, ValueError) as err:
        print(f"UNGATEABLE — {run_dir}")
        print(f"  - {err}")
        return 2

    print(f"run {ctx['run_id']} — {ctx['task']}")
    print(f"{ctx['evals']} eval(s), gating the last: {ctx['variant']}\n")
    for r in results:
        print(r)

    landed, declared = ctx["landed_band"], ctx["declared_band"]
    print()
    if landed is None:
        print(
            f"Landed in: no band. p95 {ctx['p95_ms']:.1f} ms is past 'attention' "
            f"({LATENCY_BANDS_MS['attention']} ms) — this is not an interaction yet."
        )
    elif landed == declared:
        print(f"Landed in: '{landed}' ({LATENCY_BANDS_MS[landed]} ms ceiling), as declared.")
    else:
        print(
            f"Landed in: '{landed}' ({LATENCY_BANDS_MS[landed]} ms ceiling), "
            f"declared '{declared}'. The interaction you designed is not the one "
            "this latency supports — change the UI, not only the model."
        )

    print(f"\n{DESIGN_CHECKS_NOTE}")
    print(f"\n{'ALL GATES PASS' if passed else 'GATES FAIL'} — {run_dir}")
    return 0 if passed else 1


def cmd_ship(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    run_dir, artifact = Path(argv[0]), Path(argv[1])
    if not artifact.exists():
        print(f"REFUSED — no artifact at {artifact}")
        return 2
    result = promote(run_dir, artifact)
    print(result)
    return 0 if result.startswith("PROMOTED") else 1


COMMANDS = {
    "init": cmd_init,
    "validate": cmd_validate,
    "gate": cmd_gate,
    "ship": cmd_ship,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
