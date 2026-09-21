"""The promotion gate: the one place a model is allowed to become 'the' model.

Modelled on gpu-lexer's rule — promote only a run that *strictly* improves
untouched verification accuracy and passes the guards. Everything else stays a
run. This is what keeps `runs/` full of honest history instead of a graveyard of
things that were briefly called best.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .experiment import eval_history, load_run, project_root
from .gates import run_all


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
    return json.loads(card.read_text()) if card.exists() else None


def evaluate_promotion(
    run_dir: Path, *, higher_is_better: bool | None = None, champion_dir: Path | None = None
) -> tuple[bool, str]:
    """Decide whether a finished run should become the champion.

    Two conditions, both required:
      1. every gate passes (baseline, size, latency, patience, wallclock)
      2. it strictly improves on the current champion's held-out metric

    `higher_is_better=None` reads the direction off the run's own contract,
    which is what `python -m harness ship` relies on. Getting this wrong is
    worse here than in a single gate: each promotion would install an
    incumbent worse than the last, and the ledger would record every one of
    them as an improvement.
    """
    manifest, exp = load_run(run_dir)

    evals = manifest.get("evals", [])
    if not evals:
        return False, "no evaluations recorded — nothing to promote"

    final = evals[-1]
    history = eval_history(manifest)

    passed, results = run_all(
        exp,
        candidate_value=final["metric_value"],
        size_kb=final["size_kb"],
        p95_ms=final["p95_ms"],
        eval_history=history,
        elapsed_minutes=final.get("elapsed_minutes", 0.0),
        higher_is_better=higher_is_better,
    )
    report = "\n".join(str(r) for r in results)
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
        run_dir, higher_is_better=higher_is_better, champion_dir=champion_dir
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
        "metric": manifest["experiment"]["baseline"]["metric"],
        "metric_value": final["metric_value"],
        "size_kb": final["size_kb"],
        "p95_ms": final["p95_ms"],
        "beats_baseline": manifest["experiment"]["baseline"]["name"],
    }
    (champ_dir / "champion.json").write_text(json.dumps(card, indent=2))

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.write_text(
            "# Promotion ledger\n\nAppend-only. Every champion, in order.\n\n"
        )
    with ledger_path.open("a") as fh:
        fh.write(
            f"- `{card['promoted_at']}` **{card['task']}** — "
            f"{card['metric']}={card['metric_value']:.4f}, "
            f"{card['size_kb']:.1f} KB, p95 {card['p95_ms']:.1f} ms "
            f"(run `{card['run_id']}`, sha `{card['git_sha']}`)\n"
        )
    return f"PROMOTED — {reason}"
