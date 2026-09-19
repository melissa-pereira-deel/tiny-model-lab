"""The thing to beat: a hand-written rule classifier.

Written against `ini`, `env` and `make` — the three training dialects — and
written as well as I could make it for those three. That matters. A baseline
chosen to be weak makes the whole comparison decoration, which is the failure
this repo exists to prevent.

It is then scored on two dialects it was never shown. Nothing here was adjusted
afterwards. What it gets wrong on the held-out split is what a rule set honestly
gets wrong when it meets a format its author did not have in front of them.
"""

from __future__ import annotations

import re

# A bracketed name is an ini section header.
_SECTION_BRACKET = re.compile(r"^\[.*\]$")
# env has no real section marker, so files use a decorated comment.
_SECTION_COMMENT = re.compile(r"^[#;]\s*-{2,}.*-{2,}\s*$")
# A bare name followed by a colon is a make target.
_SECTION_COLON = re.compile(r"^[A-Za-z0-9_.-]+:$")
# `=` and make's `:=`. Capture whatever follows so we can tell key from value.
_ASSIGN = re.compile(r"^[^=:]*:?=(?P<rhs>.*)$")


def classify(line: str) -> str:
    """One of: comment, section, key, value."""
    s = line.strip()
    if not s:
        return "comment"

    # Order matters: env's section marker is also a comment, so it goes first.
    if _SECTION_COMMENT.match(s):
        return "section"
    if s[0] in "#;":
        return "comment"
    if _SECTION_BRACKET.match(s):
        return "section"
    if _SECTION_COLON.match(s):
        return "section"

    m = _ASSIGN.match(s)
    if m:
        return "value" if m.group("rhs").strip() else "key"

    # Nothing matched. In the training dialects every remaining line was a
    # continuation of a value, so that is the honest default.
    return "value"
