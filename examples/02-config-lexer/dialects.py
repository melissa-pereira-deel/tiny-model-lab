"""Synthetic config-file lines, labelled by construction.

The generator is the deterministic teacher — the top of the source hierarchy in
the dataset-synthesis skill. It knows each line's label because it built the
line from that label, so there is no labelling noise to estimate.

That honesty cuts both ways, and the README says so: because the generator is
synthetic, the accuracy numbers demonstrate the mechanism. They are not evidence
about real config files.

Five dialects. Three are `TRAIN_DIALECTS`, and the baseline regexes in
`baseline.py` were written against those three only. Two are `HELDOUT_DIALECTS`
and are the split the experiment is scored on — the unit generalisation has to
cross, which is what the dataset-synthesis skill means by splitting by something
that is not random.
"""

from __future__ import annotations

import random

LABELS = ("comment", "section", "key", "value")

TRAIN_DIALECTS = ("ini", "env", "make")
HELDOUT_DIALECTS = ("toml_ish", "yaml_ish")

_WORDS = (
    "host port user timeout retries verbose cache region bucket token secret "
    "endpoint workers backlog level path root name debug locale shard replica"
).split()

_VALUES = (
    "8080 localhost true false 30s /var/log/app 0.5 v2 none auto utf-8 3 "
    "production us-east-1 /tmp/cache 1024 yes no 127.0.0.1 debug"
).split()

_COMMENTS = (
    "set by the deploy script",
    "do not edit",
    "see docs/config.md",
    "TODO: move this to the vault",
    "overridden in staging",
    "legacy, kept for the old client",
)


def _word(rng: random.Random) -> str:
    return rng.choice(_WORDS)


def _value(rng: random.Random) -> str:
    return rng.choice(_VALUES)


def _line(rng: random.Random, dialect: str, label: str) -> str:
    """One line of `dialect` that genuinely is a `label`.

    Each dialect differs in its comment marker, its assignment character, and
    how it marks a section. Those three axes are what the baseline regexes
    encode for the training dialects and what they get wrong on the held-out
    ones.
    """
    indent = " " * rng.choice((0, 0, 0, 2, 4))

    if dialect == "ini":
        if label == "comment":
            return f"{indent}; {rng.choice(_COMMENTS)}"
        if label == "section":
            return f"{indent}[{_word(rng)}]"
        if label == "key":
            return f"{indent}{_word(rng)} = "
        return f"{indent}{_word(rng)} = {_value(rng)}"

    if dialect == "env":
        if label == "comment":
            return f"{indent}# {rng.choice(_COMMENTS)}"
        if label == "section":
            return f"{indent}#--- {_word(rng).upper()} ---"
        if label == "key":
            return f"{indent}{_word(rng).upper()}="
        return f"{indent}{_word(rng).upper()}={_value(rng)}"

    if dialect == "make":
        if label == "comment":
            return f"{indent}# {rng.choice(_COMMENTS)}"
        if label == "section":
            return f"{_word(rng)}:"
        if label == "key":
            return f"{indent}{_word(rng).upper()} :="
        return f"{indent}{_word(rng).upper()} := {_value(rng)}"

    if dialect == "toml_ish":
        # Comment marker matches ini's cousin, but sections are doubled and
        # values are quoted — neither of which the training dialects show.
        if label == "comment":
            return f"{indent}# {rng.choice(_COMMENTS)}"
        if label == "section":
            return f"{indent}[[{_word(rng)}.{_word(rng)}]]"
        if label == "key":
            return f"{indent}{_word(rng)} ="
        return f'{indent}{_word(rng)} = "{_value(rng)}"'

    if dialect == "yaml_ish":
        # Assignment is a colon, and a section is a bare key with nothing after
        # it — which collides head-on with how make marks a target.
        if label == "comment":
            return f"{indent}# {rng.choice(_COMMENTS)}"
        if label == "section":
            return f"{indent}{_word(rng)}:"
        if label == "key":
            return f"{indent}- {_word(rng)}:"
        return f"{indent}{_word(rng)}: {_value(rng)}"

    raise ValueError(f"unknown dialect {dialect!r}")


def make_rows(
    n: int, dialects: tuple[str, ...], seed: int
) -> list[tuple[str, str, str]]:
    """`n` rows of (line, label, dialect), balanced over every combination.

    Walks the cartesian product rather than indexing each axis by `i`. Doing it
    the obvious way — `dialects[i % len(dialects)]` alongside
    `LABELS[i % len(LABELS)]` — silently correlates the two whenever one length
    divides the other: with two dialects and four labels each dialect only ever
    receives half the labels, and the combinations that never appear are exactly
    the hard ones. It cost the baseline a free 1.0000 before I caught it.
    """
    rng = random.Random(seed)
    combos = [(d, lab) for d in dialects for lab in LABELS]
    rows: list[tuple[str, str, str]] = []
    for i in range(n):
        dialect, label = combos[i % len(combos)]
        rows.append((_line(rng, dialect, label), label, dialect))
    rng.shuffle(rows)
    return rows
