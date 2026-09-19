"""The harness command line — one front door, mirroring the slash commands.

Usage:
  python -m harness init     [directory]
  python -m harness validate <experiment.yaml> [more.yaml ...]
  python -m harness gate     <run-dir>
  python -m harness ship     <run-dir> <artifact>
                             [--champion-dir DIR] [--ledger PATH]

`ship` writes promotion state into this project by default: `champion/` and
`runs/LEDGER.md`. `--champion-dir` moves both somewhere else, which is how
you try promotion without leaving files in a clone you did not intend to change.

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


def use_utf8_stdout() -> None:
    """Say what encoding this program's output is in, rather than inheriting.

    Python falls back to the locale encoding, and these commands print em
    dashes. Measured, not assumed: running the worked example under cp932,
    koi8-r or ascii raises UnicodeEncodeError before it prints a single gate.
    cp1252 survives the em dash and dies on the arrow that used to be in
    `GateResult.__str__` — which is how #11's Windows CI leg found this.

    Only programs call this. A library that reconfigures its caller's stdout
    is a library that has overstepped, which is why `gates.py` was made ASCII
    instead.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # Not a real stream, or already wrapped. Nothing to do.


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


SHIP_FLAGS = ("--champion-dir", "--ledger")


def take_flags(
    argv: list[str], names: tuple[str, ...]
) -> tuple[dict[str, str], list[str]] | None:
    """Split `--name value` / `--name=value` off argv, leaving the positionals.

    Hand-rolled rather than argparse because the other three subcommands parse
    their own argv and print this module's docstring as usage; one optional flag
    does not earn two parsing styles in one file.

    Returns None on anything malformed — an unknown flag, a flag with no value,
    a flag whose value is the next flag. A parser that quietly files a typo as a
    positional is worse than no parser, because the run still happens and writes
    somewhere you did not ask for.
    """
    flags: dict[str, str] = {}
    positional: list[str] = []
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if not item.startswith("--"):
            positional.append(item)
            continue
        name, sep, value = item.partition("=")
        if name not in names:
            print(f"unknown option {name} — this command takes {', '.join(names)}")
            return None
        if not sep:
            if not rest or rest[0].startswith("--"):
                print(f"{name} needs a value")
                return None
            value = rest.pop(0)
        if not value:
            print(f"{name} needs a value")
            return None
        flags[name] = value
    return flags, positional


def cmd_ship(argv: list[str]) -> int:
    parsed = take_flags(argv, SHIP_FLAGS)
    if parsed is None:
        print(__doc__)
        return 2
    flags, positional = parsed
    if len(positional) != 2:
        print(__doc__)
        return 2

    run_dir, artifact = Path(positional[0]), Path(positional[1])
    if not artifact.exists():
        print(f"REFUSED — no artifact at {artifact}")
        return 2

    champion_dir = Path(flags["--champion-dir"]) if "--champion-dir" in flags else None
    # The ledger follows the champion directory. Moving the card out of a clone
    # while still appending to its `runs/LEDGER.md` would only half-answer the
    # reason this flag exists — `--ledger` is there to split them again.
    if "--ledger" in flags:
        ledger = Path(flags["--ledger"])
    elif champion_dir is not None:
        ledger = champion_dir / "LEDGER.md"
    else:
        ledger = None

    result = promote(run_dir, artifact, champion_dir=champion_dir, ledger=ledger)
    print(result)
    return 0 if result.startswith("PROMOTED") else 1


COMMANDS = {
    "init": cmd_init,
    "validate": cmd_validate,
    "gate": cmd_gate,
    "ship": cmd_ship,
}


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
