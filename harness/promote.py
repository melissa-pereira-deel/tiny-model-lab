"""The promotion gate: the one place a model is allowed to become 'the' model.

Modelled on gpu-lexer's rule — promote only a run that *strictly* improves
untouched verification accuracy and passes the guards. Everything else stays a
run. This is what keeps `runs/` full of honest history instead of a graveyard of
things that were briefly called best.

It is also the only place in the harness that can check a number against the
world rather than against another number. Accuracy and p95 are gone by the time
a run is over; the artifact is still there. So the size gate is measured here,
on the bytes about to be copied, and not taken from the manifest (#24).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .experiment import eval_history, load_run, project_root
from .gates import run_all
from .profile import artifact_size_kb


def champion_dir_for(champion_dir: Path | None = None) -> Path:
    """`champion/` in this project, unless a caller names somewhere else.

    The override exists so a test can exercise promotion without writing into
    the working tree. Before it, the only branch a test could reach was the
    refusal — the code that actually mutates champion/ and the ledger had never
    once been executed.
    """
    return Path(champion_dir) if champion_dir else project_root() / "champion"


def ledger_for(ledger: Path | None = None) -> Path:
    return Path(ledger) if ledger else project_root() / "runs" / "LEDGER.md"


def _load_champion(champion_dir: Path | None = None) -> dict | None:
    card = champion_dir_for(champion_dir) / "champion.json"
    return json.loads(card.read_text(encoding="utf-8")) if card.exists() else None


def gated_size_kb(artifact: Path | None, reported_kb: float) -> float:
    """The number the size gate should see.

    The artifact's bytes when there is an artifact, the manifest's claim when
    there is not. One owner on purpose: `evaluate_promotion` decides on this
    number and `promote` writes it into the champion card, and two callers each
    stat-ing the file their own way is exactly how a card comes to disagree
    with the gate that let it through.

    Raises OSError for a path that is gone or unreadable. The caller turns that
    into a refusal rather than a traceback.
    """
    return reported_kb if artifact is None else artifact_size_kb(artifact)


def size_provenance(artifact: Path | None, size_kb: float, reported_kb: float) -> str:
    """One line saying where the number the size gate just used came from.

    Printed whether the gate passed or failed, and never a comparison. Two
    facts side by side need no threshold to be worth reading; deciding that the
    gap between them is *too large* would need one, and an unmeasured tolerance
    is the thing spike records exist to prevent. The budget is the only number
    here anyone argued for, so the budget is the only thing that refuses.

    Both numbers print even when they agree. A line that appears only on a
    mismatch is a line a reader can conclude nothing from when it is absent.
    """
    if artifact is None:
        return (
            f"measured: nothing — gated on the manifest's {reported_kb:.1f} KB, "
            "which nothing has checked against a file"
        )
    return (
        f"measured: artifact {size_kb:.1f} KB on disk; "
        f"the manifest recorded {reported_kb:.1f} KB"
    )


def candidate_line(final: dict, artifact: Path | None, eval_count: int) -> str:
    """Which eval is being promoted, and which file is going with it.

    `promote()` takes the *last* eval as the candidate, so the artifact handed
    to it has to be the one that eval describes. Nothing here can check that:
    an eval records numbers, not a path, and a path it did record would not
    survive a move between machines or a re-gate a year later — it would be as
    trustworthy as `size_kb` was before #24, with nothing physical to check it
    against. So this refuses nothing. It prints both names and lets a reader
    see a variant called `conv-raw-chars-int8` shipping as a file called
    `conv-raw-chars.onnx`, which is #27 and took reading the source to find.
    """
    variant = final.get("variant", "unnamed")
    where = f"the last of {eval_count} eval(s)"
    if artifact is None:
        return f"candidate: {where}, variant {variant!r} — no file named"
    return f"candidate: {where}, variant {variant!r} — shipping file {Path(artifact).name!r}"


def evaluate_promotion(
    run_dir: Path,
    *,
    artifact: Path | None = None,
    higher_is_better: bool | None = None,
    champion_dir: Path | None = None,
) -> tuple[bool, str]:
    """Decide whether a finished run should become the champion.

    Three conditions, all required:
      1. the artifact is measurable and has bytes in it
      2. every gate passes (baseline, size, latency, patience, wallclock), with
         the size gate reading the artifact rather than the manifest
      3. it strictly improves on the current champion's held-out metric

    `artifact=None` answers from the manifest alone. That is the same partial
    answer the `gate` subcommand can give, and for the same reason: mid-run
    there is usually no export yet, so there is nothing to measure. It is not a
    way around the check — `promote()` always passes the artifact and
    `cmd_ship` always goes through `promote()`, so nothing reaches `champion/`
    unmeasured. What `None` buys is the ability to ask "would this promote?"
    before the export exists.

    `higher_is_better=None` reads the direction off the run's own contract,
    which is what the `ship` subcommand relies on. Getting this wrong is worse
    here than in a single gate: each promotion would install an incumbent worse
    than the last, and the ledger would record every one of them as an
    improvement.
    """
    manifest, exp = load_run(run_dir)

    evals = manifest.get("evals", [])
    if not evals:
        return False, "no evaluations recorded — nothing to promote"

    final = evals[-1]
    history = eval_history(manifest)

    reported_kb = final["size_kb"]
    try:
        size_kb = gated_size_kb(artifact, reported_kb)
    except OSError as err:
        return False, (
            f"cannot measure the artifact at {artifact} — {err}. The size gate "
            "compares the bytes you are about to ship, so an artifact it cannot "
            "read is not a run it can judge."
        )

    if artifact is not None and size_kb == 0.0:
        return False, (
            f"the artifact at {artifact} measures 0.0 KB. An artifact with no "
            "bytes is an export that failed, not a model that compressed well — "
            "and it would clear any size budget, because zero is under every "
            "number. Check the export step actually wrote something, then gate "
            "the run again."
        )

    passed, results = run_all(
        exp,
        candidate_value=final["metric_value"],
        size_kb=size_kb,
        p95_ms=final["p95_ms"],
        eval_history=history,
        elapsed_minutes=final.get("elapsed_minutes", 0.0),
        higher_is_better=higher_is_better,
    )
    report = "\n".join(
        [
            candidate_line(final, artifact, len(evals)),
            size_provenance(artifact, size_kb, reported_kb),
            *(str(r) for r in results),
        ]
    )
    if not passed:
        return False, f"gates failed:\n{report}"

    champ = _load_champion(champion_dir)
    if champ is not None:
        # Shipping the same run twice is not a tie between two models, and the
        # strict-improvement message reads as though one lost. Same refusal,
        # different reason: the information is already in hand.
        if champ.get("run_id") == manifest["run_id"]:
            return False, (
                f"run {manifest['run_id']} is already the champion — nothing to "
                "promote. Strict improvement is measured against the incumbent, "
                "and a run cannot strictly improve on itself."
            )
        prev = champ["metric_value"]
        # Resolved here rather than at the top because the gates above take
        # None deliberately -- it is how they consult the contract.
        prefers_higher = (
            exp.baseline.prefers_higher() if higher_is_better is None else higher_is_better
        )
        better = final["metric_value"] > prev if prefers_higher else final["metric_value"] < prev
        if not better:
            return False, (
                f"gates passed but champion not beaten "
                f"({final['metric_value']:.4f} vs {prev:.4f}). Strict improvement "
                "is required — a tie keeps the incumbent."
            )
    return True, f"promotable:\n{report}"


def promote(
    run_dir: Path,
    artifact: Path,
    *,
    higher_is_better: bool | None = None,
    champion_dir: Path | None = None,
    ledger: Path | None = None,
) -> str:
    ok, reason = evaluate_promotion(
        run_dir,
        artifact=artifact,
        higher_is_better=higher_is_better,
        champion_dir=champion_dir,
    )
    if not ok:
        return f"REFUSED — {reason}"

    champ_dir = champion_dir_for(champion_dir)
    ledger_path = ledger_for(ledger)

    manifest, _ = load_run(run_dir)
    final = manifest["evals"][-1]
    champ_dir.mkdir(parents=True, exist_ok=True)
    dest = champ_dir / artifact.name
    if artifact.is_dir():
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(artifact, dest)
    else:
        shutil.copy2(artifact, dest)

    card = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "git_sha": manifest["git_sha"],
        "task": manifest["experiment"]["task"],
        "artifact": dest.name,
        # Beside the filename on purpose. The card is the only surviving record
        # of which eval this file was supposed to be, and the two disagreeing
        # is #27 -- which nothing detected, because nothing wrote them down
        # together.
        "variant": final.get("variant", "unnamed"),
        "metric": manifest["experiment"]["baseline"]["metric"],
        "metric_value": final["metric_value"],
        # Measured, not claimed. A second stat() of a path `evaluate_promotion`
        # has just read successfully, through the same one owner, so the card
        # and the gate cannot end up describing different numbers.
        "size_kb": gated_size_kb(artifact, final["size_kb"]),
        # Kept beside it rather than discarded: a card where the two disagree is
        # the only surviving evidence that a runner estimated where it should
        # have measured. Always written, so its absence never has to be read.
        "size_kb_reported": final["size_kb"],
        "p95_ms": final["p95_ms"],
        "beats_baseline": manifest["experiment"]["baseline"]["name"],
    }
    (champ_dir / "champion.json").write_text(json.dumps(card, indent=2), encoding="utf-8")

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.write_text(
            "# Promotion ledger\n\nAppend-only. Every champion, in order.\n\n",
            encoding="utf-8",
        )
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"- `{card['promoted_at']}` **{card['task']}** — "
            f"{card['metric']}={card['metric_value']:.4f}, "
            f"{card['size_kb']:.1f} KB, p95 {card['p95_ms']:.1f} ms "
            f"(run `{card['run_id']}`, sha `{card['git_sha']}`)\n"
        )
    return f"PROMOTED — {reason}"
