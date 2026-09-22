"""A spike is a measurement, not a run.

A spike answers one cheap question so that a contract field can carry a number
somebody actually measured -- or so you can decide whether a contract is worth
writing at all. Its output is a finding. It never produces a run directory,
never a manifest, and never anything promotable: `start_run()` exists to record
a *comparison*, and a spike has one measurement against one threshold.

The record is `experiments/<slug>.spike.md` -- Markdown with YAML frontmatter,
beside the contracts and the refusals, because that is where somebody looking
for the reasoning already goes. It is `.md` on purpose. The PreToolUse guard
and CI both glob `experiments/*.yaml`, so a spike record unlocks neither
training nor the build, and `tests/test_guard_hook.py` pins that rather than
leaving it as a happy accident.

`informs` is checked against the flattened keys of
`harness/templates/experiment.yaml`, read at runtime. So the kinds of spike
fall out of the contract instead of being a taxonomy somebody has to keep in
step with it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .experiment import project_root

TEMPLATES = Path(__file__).resolve().parent / "templates"
CONTRACT_TEMPLATE = TEMPLATES / "experiment.yaml"

SPEC_DIR = "experiments"
SPIKE_GLOB = "*.spike.md"

# One working day, and this is a judgement call rather than a fact. Unlike
# LATENCY_BANDS_MS -- which is Miller and Nielsen measuring people, and which
# is why that constant lives in code instead of config -- there is no
# literature behind this number, and a project whose questions are all
# data-crunching may want a different one.
#
# The argument for it: the README's ladder says three of its four rungs cost
# minutes and the tiny-model rung costs days, and `.claude/commands/data.md`
# prices a scoping error caught early at "an afternoon instead of three days".
# A day is where a measurement stops being obviously cheaper than the work it
# was meant to de-risk. Past that, you are not de-risking a contract any more,
# you are running one: write it, and let `budgets.max_wallclock_minutes` cap
# the thing it was always capping.
MAX_SPIKE_MINUTES = 480

STATUSES = ("open", "answered", "abandoned")
CLOSED_STATUSES = ("answered", "abandoned")

# What `informs` may say when the answer decides whether to write a contract at
# all, rather than filling a field in one. The fourth kind of spike, and the
# only one the contract template cannot name, because at that point there is no
# contract.
SCOPE = "scope"

MIN_WORDS = 5

FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def _flatten(node: dict[str, Any], prefix: str = "") -> list[str]:
    """Every key in a nested mapping as a dotted path, containers included."""
    paths: list[str] = []
    for key, value in node.items():
        path = f"{prefix}{key}"
        paths.append(path)
        if isinstance(value, dict):
            paths.extend(_flatten(value, f"{path}."))
    return paths


def contract_fields() -> tuple[str, ...]:
    """The field paths a spike may claim to inform, read from the template.

    Computed at runtime rather than written out here. A hardcoded list is a
    second copy of the contract's shape, and the second copy is the one that
    goes stale -- which is the failure this repo has already had once, in
    three files stating the same audit rule three different ways.
    """
    raw = yaml.safe_load(CONTRACT_TEMPLATE.read_text(encoding="utf-8")) or {}
    return tuple(sorted(_flatten(raw)))


def load_spike(path: str | Path) -> dict[str, Any]:
    """Read the YAML frontmatter of a spike record.

    Raises ValueError with the reason when there is no frontmatter or it is not
    a mapping, so the caller has one thing to catch and one thing to print.
    """
    text = Path(path).read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError(
            "no YAML frontmatter -- a spike record starts with a line of three "
            "dashes, the fields, and another line of three dashes. Copy "
            "harness/templates/spike.md and fill it in; the prose below the "
            "frontmatter is yours and is never parsed."
        )
    try:
        raw = yaml.safe_load(match.group(1))
    except yaml.YAMLError as err:
        raise ValueError(f"could not parse the frontmatter: {err}") from err
    if not isinstance(raw, dict):
        raise ValueError(
            "the frontmatter is not a mapping of fields -- copy "
            "harness/templates/spike.md and fill it in"
        )
    return raw


def _words(value: Any) -> int:
    return len(str(value or "").split())


def _as_paths(value: Any) -> list[str]:
    """`informs` accepts one path or several. Normalise to a list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    return [str(value or "").strip()]


def _informs_problems(value: Any) -> list[str]:
    known = contract_fields()
    paths = [p for p in _as_paths(value) if p]
    if not paths:
        return [
            "informs is empty -- name the contract field this measurement gives "
            f"a value to (dataset.teacher, budgets.max_size_kb, ...), or the "
            f"literal {SCOPE!r} when what it decides is whether a contract gets "
            "written at all. A list is fine when one measurement fills two fields."
        ]
    problems = []
    for path in paths:
        if path != SCOPE and path not in known:
            problems.append(
                f"informs {path!r} is not a field of the experiment contract -- "
                f"name the field this measurement gives a value to, or the "
                f"literal {SCOPE!r} when it decides whether to write a contract "
                f"at all. The paths come from harness/templates/experiment.yaml: "
                f"{', '.join(known)}."
            )
    return problems


def _budget_problems(value: Any) -> list[str]:
    ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    if ok and 0 < value <= MAX_SPIKE_MINUTES:
        return []
    return [
        f"budget_minutes must be a number above 0 and at most "
        f"{MAX_SPIKE_MINUTES} -- got {value!r}. The ceiling is one working day, "
        "and it is a judgement call rather than a perceptual fact: a question "
        "that needs longer than a day is not de-risking a contract any more. "
        "Write the contract and let budgets.max_wallclock_minutes cap the run."
    ]


def _status_problems(raw: dict[str, Any]) -> list[str]:
    status = str(raw.get("status") or "").strip()
    if status not in STATUSES:
        return [
            f"status {status!r} is not one of {', '.join(STATUSES)} -- open "
            "while the question is unanswered, answered once the finding is "
            "written, abandoned when you stopped without answering it, which "
            "still costs you a finding sentence."
        ]

    problems: list[str] = []
    if status in CLOSED_STATUSES and _words(raw.get("finding")) < MIN_WORDS:
        problems.append(
            f"status is {status!r} but finding is under {MIN_WORDS} words -- "
            "write what you learned, in the sentence you would say out loud. A "
            "closed spike with no finding is an open one nobody closed: leave "
            "it at status: open instead, and close it when there is something "
            "to close it with."
        )
    if status == "answered" and not raw.get("elapsed_minutes"):
        problems.append(
            "status is 'answered' but elapsed_minutes is 0 -- record what it "
            "actually cost, so the next budget_minutes is an estimate from "
            "evidence rather than from optimism. If it genuinely took under a "
            "minute, write 1 and let that be the finding it is."
        )
    return problems


def _elapsed_problems(raw: dict[str, Any]) -> list[str]:
    elapsed = raw.get("elapsed_minutes", 0)
    budget = raw.get("budget_minutes", 0)
    numbers = all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in (elapsed, budget)
    )
    if not numbers:
        return []
    if elapsed < 0:
        return ["elapsed_minutes cannot be negative -- record what it cost, or leave it 0"]
    status = str(raw.get("status") or "").strip()
    if elapsed > budget and status != "abandoned":
        return [
            f"elapsed_minutes {elapsed} is past budget_minutes {budget} and "
            f"status is {status!r} -- the time box is the point of the record. "
            "Closing an over-budget spike is what status: abandoned is for: set "
            "it and write the finding you have. Raising budget_minutes "
            "afterwards turns the number into what it cost rather than what you "
            "agreed to spend."
        ]
    return []


def spike_problems(path: str | Path) -> list[str]:
    """Every reason this file is not yet a spike record. Empty means it is one."""
    try:
        raw = load_spike(path)
    except (OSError, ValueError) as err:
        return [str(err)]

    problems: list[str] = []
    if _words(raw.get("question")) < MIN_WORDS:
        problems.append(
            f"question is under {MIN_WORDS} words -- write the question you "
            "have to answer before the contract field is worth filling in, the "
            "way a PRD writes an assumption. If it cannot be put as a question "
            "with a cheap test behind it, what you have is a task: run /scope "
            "and write the contract."
        )
    problems.extend(_informs_problems(raw.get("informs")))
    if not str(raw.get("threshold") or "").strip():
        problems.append(
            "threshold is empty -- write what a yes looks like, e.g. "
            "'>= 0.90 on the first 10k rows'. Nothing compares your finding to "
            "it: this check reads a label, not a measurement. The threshold is "
            "for the reader, and for you, while the number does not exist yet "
            "and cannot talk you into a different one."
        )
    if _words(raw.get("if_not")) < MIN_WORDS:
        problems.append(
            f"if_not is under {MIN_WORDS} words -- name what changes when the "
            "answer is no: which contract field moves, which rung of the ladder "
            "you drop to, or that the contract does not get written. Without a "
            "named consequence a spike is a note. If nothing would change "
            "either way, do not run it: close it now with status: abandoned and "
            "a finding saying so."
        )
    problems.extend(_budget_problems(raw.get("budget_minutes")))
    problems.extend(_status_problems(raw))
    problems.extend(_elapsed_problems(raw))
    return problems


def find_spikes(root: str | Path | None = None) -> list[Path]:
    """Every spike record under `<root>/experiments/`, oldest name first."""
    root = Path(root) if root else project_root()
    return sorted((root / SPEC_DIR).glob(SPIKE_GLOB))
