"""Output has to survive a console that is not UTF-8.

Found by adding `windows-latest` to CI (#11). The worked example died with
`UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'` before
printing a single gate — a real bug for a Windows user, not a CI artefact.

Two separate fixes, because they are two separate mistakes:

- `gates.py` returned a U+2192 arrow. That is a *library* handing its caller a
  string the caller may not be able to print. It is ASCII now.
- The programs inherited the locale encoding. They declare UTF-8 now. Measured:
  before that, the em dashes alone broke cp932, koi8-r and ascii.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = REPO_ROOT / "examples" / "01-hello-tiny" / "run.py"

# cp1252 is what a default Windows console uses and is where this was found.
# The others are legacy encodings that the em dash alone was enough to break.
HOSTILE_ENCODINGS = ["cp1252", "cp932", "koi8-r", "ascii"]


def run(args: list[str], encoding: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("encoding", HOSTILE_ENCODINGS)
def test_the_worked_example_runs(encoding: str) -> None:
    """The README promises this takes a second and works. On any console."""
    proc = run([str(EXAMPLE)], encoding)
    assert proc.returncode == 0, f"{encoding}: {proc.stderr.strip().splitlines()[-1:]}"
    assert "UnicodeEncodeError" not in proc.stderr


# One invocation per subcommand that prints prose rather than arithmetic.
# `spikes` joined the list the day it was added: its refusals are long English
# sentences, which is exactly the shape of output that broke cp932 before.
CLI_INVOCATIONS = {
    "validate": ["-m", "harness", "validate", "examples/01-hello-tiny/experiment.yaml"],
    "spikes": ["-m", "harness", "spikes"],
}


@pytest.mark.parametrize("encoding", HOSTILE_ENCODINGS)
@pytest.mark.parametrize("args", CLI_INVOCATIONS.values(), ids=list(CLI_INVOCATIONS))
def test_the_cli_runs(encoding: str, args: list[str]) -> None:
    proc = run(args, encoding)
    assert proc.returncode == 0, f"{encoding}: {proc.stderr.strip().splitlines()[-1:]}"
    assert "UnicodeEncodeError" not in proc.stderr


def test_gate_output_is_ascii() -> None:
    """The library half, checked at the source rather than through a console.

    A failing gate is the case that matters: the arrow only appeared in the
    remediation line, so a suite that never failed a gate would never see it.
    """
    from harness.experiment import Baseline, Budgets, Experiment
    from harness.gates import run_all

    exp = Experiment(
        task="t",
        hypothesis="a tiny model can beat the regex tagger on unseen formats",
        baseline=Baseline(kind="deterministic", name="regex", metric="accuracy", value=0.9),
        budgets=Budgets(max_size_kb=1, latency_band="instant"),
    )
    passed, results = run_all(
        exp,
        candidate_value=0.1,   # loses, so every remediation is rendered
        size_kb=999.0,
        p95_ms=9999.0,
        eval_history=[0.1],
        elapsed_minutes=99999.0,
    )
    assert not passed, "this fixture is meant to fail every gate"
    rendered = "\n".join(str(r) for r in results)
    offenders = sorted({c for c in rendered if ord(c) > 127})
    assert not offenders, f"gate output must be ASCII, found {offenders}"


# --- The input side (#34) ------------------------------------------------
#
# #11 fixed output and stopped there. Reading has the same defect and is
# worse, because it fails on files a *user* wrote rather than on this repo's
# own prose.


TEXT_IO = frozenset({"read_text", "write_text", "open"})

SCANNED = ("harness", "tests", "examples")


def python_files() -> list[Path]:
    found: list[Path] = []
    for directory in SCANNED:
        found.extend(sorted((REPO_ROOT / directory).rglob("*.py")))
    # build/ holds a stale copy of harness/ from a local `pip install`, and
    # .venv/ is not ours. Neither is under the directories above, but rglob
    # would follow them in a differently-arranged checkout.
    return [p for p in found if "build" not in p.parts and ".venv" not in p.parts]


def opens_in_binary_mode(call: ast.Call) -> bool:
    """`open(p, "rb")` and friends must NOT be given an encoding."""
    modes = [a for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    modes += [
        k.value
        for k in call.keywords
        if k.arg == "mode" and isinstance(k.value, ast.Constant)
    ]
    return any("b" in m.value for m in modes if isinstance(m.value, str))


def unencoded_text_io(path: Path) -> list[str]:
    """Every text read/write in `path` that does not say what encoding it means.

    Parsed rather than grepped. A regex cannot see that
    `harness/promote.py`'s ledger write spans three lines with its
    `encoding=` on the second, and would either miss multi-line calls or
    fire on the word appearing in a comment.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else None
        )
        if name not in TEXT_IO:
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue
        if opens_in_binary_mode(node):
            continue
        where = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path.name
        problems.append(f"{where}:{node.lineno} {name}()")
    return problems


class TestEveryReadSaysWhatItMeans:
    """#34. `read_text()` with no encoding uses the locale's, which is cp1252
    on a default Windows install — and cp1252 has no mapping for five byte
    values, so a UTF-8 file containing one raises rather than mis-decoding.

    The failure mode is nastier than a crash, though. Most non-ASCII decodes
    *fine* under cp1252 and simply decodes wrong: an em dash is `E2 80 94`
    and cp1252 maps all three bytes, so `CHANGELOG.md` came back as mojibake
    and nothing raised. You get silent corruption where it decodes and an
    exception where it does not, and which one depends on whether the file
    happens to contain an emoji.
    """

    def test_nothing_reads_or_writes_text_without_saying_so(self) -> None:
        problems = [p for f in python_files() for p in unencoded_text_io(f)]
        assert not problems, (
            "these inherit the locale encoding, which is cp1252 on Windows:\n  "
            + "\n  ".join(problems)
            + "\n\nPass encoding=\"utf-8\". For binary, use read_bytes/write_bytes "
            'or a mode containing "b", which this check skips.'
        )

    def test_the_check_can_actually_see_a_bare_call(self, tmp_path: Path) -> None:
        """Guards the test above, which is a scan and would pass vacuously if
        the AST walk were looking for the wrong thing."""
        sample = tmp_path / "sample.py"
        sample.write_text(
            "from pathlib import Path\n"
            "Path('a').read_text()\n"
            "Path('b').read_text(encoding='utf-8')\n"
            "Path('c').open('rb')\n",
            encoding="utf-8",
        )
        found = unencoded_text_io(sample)
        assert len(found) == 1, found
        assert "sample.py:2 read_text()" in found[0]

    def test_the_repo_files_it_reads_are_actually_utf8(self) -> None:
        """The other half: declaring UTF-8 is only right if the files are.

        README.md is the one that broke CI — U+26A0 U+FE0F, whose last byte
        is 0x8F, one of the five cp1252 leaves undefined.
        """
        for name in ("README.md", "CHANGELOG.md", "LICENSE", "AGENTS.md"):
            (REPO_ROOT / name).read_text(encoding="utf-8")
