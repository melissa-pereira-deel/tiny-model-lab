"""Two input representations, which is the whole experiment.

`architecture-selection` says the representation is the product — that most of
the win in a tiny model comes from framing the input so the task becomes easy,
not from the network. Example 01 taught that in the negative: it sees only the
first character, and no amount of extra data moves it off that ceiling.

This is the positive version. Same model, same data, same budget; the only thing
that changes between the first two variants is what the model is allowed to see.

- `raw` encodes literal characters. It can memorise that `=` means assignment.
- `classes` encodes character *classes* and a few facts a deterministic pass can
  compute for free. It never learns which byte is the separator, only that there
  is one and whether anything follows it.

The bet is that `classes` transfers to a dialect whose separator it has never
seen, and `raw` does not.
"""

from __future__ import annotations

MAX_LEN = 48

# raw: a small byte-ish vocabulary, everything else folded into one bucket.
_RAW_VOCAB = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=:;#[]-_./\"'"
_RAW_INDEX = {c: i + 1 for i, c in enumerate(_RAW_VOCAB)}
RAW_VOCAB_SIZE = len(_RAW_VOCAB) + 2  # 0 = pad, last = unknown

# classes: letter, digit, space, separator-ish, bracket, comment-marker, other.
_CLASSES = ("pad", "alpha", "digit", "space", "sep", "bracket", "comment", "quote", "other")
CLASS_VOCAB_SIZE = len(_CLASSES)
_CLASS_INDEX = {name: i for i, name in enumerate(_CLASSES)}


def _class_of(ch: str) -> int:
    if ch.isalpha():
        return _CLASS_INDEX["alpha"]
    if ch.isdigit():
        return _CLASS_INDEX["digit"]
    if ch.isspace():
        return _CLASS_INDEX["space"]
    if ch in "=:":
        return _CLASS_INDEX["sep"]
    if ch in "[]{}()":
        return _CLASS_INDEX["bracket"]
    if ch in "#;":
        return _CLASS_INDEX["comment"]
    if ch in "\"'":
        return _CLASS_INDEX["quote"]
    return _CLASS_INDEX["other"]


def encode_raw(line: str) -> list[int]:
    ids = [_RAW_INDEX.get(c, RAW_VOCAB_SIZE - 1) for c in line[:MAX_LEN]]
    return ids + [0] * (MAX_LEN - len(ids))


def encode_classes(line: str) -> list[int]:
    ids = [_class_of(c) for c in line[:MAX_LEN]]
    return ids + [0] * (MAX_LEN - len(ids))


def scalars(line: str) -> list[float]:
    """What a deterministic pass can compute for free, so the model need not learn it.

    Deliberately says nothing about *which* character separates. A rule set that
    hard-codes `=` cannot answer these for a dialect that uses `:`; these can.
    """
    s = line.strip()
    if not s:
        return [0.0] * 6
    sep_at = min((s.find(c) for c in "=:" if c in s), default=-1)
    after = s[sep_at + 1:].strip() if sep_at >= 0 else ""
    return [
        1.0 if sep_at >= 0 else 0.0,                      # is there a separator
        1.0 if after else 0.0,                            # anything after it
        sep_at / MAX_LEN if sep_at >= 0 else 0.0,         # where it sits
        1.0 if s[0] in "#;" else 0.0,                     # opens like a comment
        1.0 if s[0] in "[" else 0.0,                      # opens like a section
        min(len(line) - len(line.lstrip()), 8) / 8.0,     # indent depth
    ]


ENCODERS = {"raw": (encode_raw, RAW_VOCAB_SIZE), "classes": (encode_classes, CLASS_VOCAB_SIZE)}
