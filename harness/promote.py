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

from .experiment import REPO_ROOT, eval_history, load_run
from .gates import run_all

CHAMPION_DIR = REPO_ROOT / "champion"
LEDGER = REPO_ROOT / "runs" / "LEDGER.md"


def _load_champion() -> dict | None:
    card = CHAMPION_DIR / "champion.json"
    return json.loads(card.read_text()) if card.exists() else None


def evaluate_promotion(run_dir: Path, *, higher_is_better: bool = True) -> tuple[bool, str]:
    """Decide whether a finished run should become the champion.

    Two conditions, both required:
      1. every gate passes (baseline, size, latency, patience, wallclock)
      2. it strictly improves on the current champion's held-out metric
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

    champ = _load_champion()
    if champ is not None:
        prev = champ["metric_value"]
        better = final["metric_value"] > prev if higher_is_better else final["metric_value"] < prev
        if not better:
            return False, (
                f"gates passed but champion not beaten "
                f"({final['metric_value']:.4f} vs {prev:.4f}). Strict improvement "
                "is required — a tie keeps the incumbent."
            )
    return True, f"promotable:\n{report}"


def promote(run_dir: Path, artifact: Path, *, higher_is_better: bool = True) -> str:
    ok, reason = evaluate_promotion(run_dir, higher_is_better=higher_is_better)
    if not ok:
        return f"REFUSED — {reason}"

    manifest = json.loads((run_dir / "manifest.json").read_text())
    final = manifest["evals"][-1]
    CHAMPION_DIR.mkdir(exist_ok=True)
    dest = CHAMPION_DIR / artifact.name
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
    (CHAMPION_DIR / "champion.json").write_text(json.dumps(card, indent=2))

    LEDGER.parent.mkdir(exist_ok=True)
    if not LEDGER.exists():
        LEDGER.write_text("# Promotion ledger\n\nAppend-only. Every champion, in order.\n\n")
    with LEDGER.open("a") as fh:
        fh.write(
            f"- `{card['promoted_at']}` **{card['task']}** — "
            f"{card['metric']}={card['metric_value']:.4f}, "
            f"{card['size_kb']:.1f} KB, p95 {card['p95_ms']:.1f} ms "
            f"(run `{card['run_id']}`, sha `{card['git_sha']}`)\n"
        )
    return f"PROMOTED — {reason}"
