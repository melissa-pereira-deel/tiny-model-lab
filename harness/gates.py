"""Gates: the computational sensors that decide stop / continue / promote.

Böckeler's distinction is the design here. A *guide* steers the agent before it
acts (the skills, AGENTS.md). A *sensor* checks after it acts. Sensors that are
deterministic and fast are worth far more than clever ones, because the agent
can run them every loop and trust the answer.

Every gate returns a GateResult whose `remediation` field is written to be read
by an agent. When a gate fails, that text lands in the agent's context and tells
it what to do instead of guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .experiment import Experiment


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str
    remediation: str = ""

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        out = f"[{mark}] {self.name}: {self.detail}"
        if not self.passed and self.remediation:
            out += f"\n       → {self.remediation}"
        return out


def baseline_gate(
    experiment: Experiment, candidate_value: float, higher_is_better: bool = True
) -> GateResult:
    """Did the model beat the thing that already works?

    Strict inequality on purpose. A tie means the simpler thing wins, because
    the simpler thing has no training pipeline, no weights to ship, and no
    silent failure modes.
    """
    b = experiment.baseline
    if b.measured_at_runtime and b.value == 0.0:
        return GateResult(
            name="baseline",
            passed=False,
            detail=(
                f"{b.kind} baseline '{b.name}' is declared measured-at-runtime but "
                f"{b.metric} is still 0.0"
            ),
            remediation=(
                "The number never arrived, so there is nothing to beat and every "
                "candidate 'wins' — the exact comparison this harness exists to "
                "prevent. Measure the baseline on the held-out split and assign it "
                "to experiment.baseline.value before start_run(), the way "
                "examples/01-hello-tiny/run.py does. If the measurement genuinely is "
                "0.0, state the metric in the direction where it is not — accuracy "
                "1.0, not error 0.0 — so the gate has something to compare."
            ),
        )
    beat = candidate_value > b.value if higher_is_better else candidate_value < b.value
    direction = "higher" if higher_is_better else "lower"
    detail = (
        f"candidate {b.metric}={candidate_value:.4f} vs "
        f"{b.kind} baseline '{b.name}'={b.value:.4f} ({direction} is better)"
    )
    return GateResult(
        name="baseline",
        passed=beat,
        detail=detail,
        remediation=(
            "The baseline still wins. Do NOT tune hyperparameters yet — that is "
            "the expensive way to discover a scoping error. In order: (1) improve "
            "the input representation, which is where most tiny-model gains live; "
            "(2) check label quality on 20 disagreements by hand; (3) if neither "
            "moves it, write this up as a negative result and ship the baseline."
        ),
    )


def size_gate(experiment: Experiment, actual_kb: float) -> GateResult:
    cap = experiment.budgets.max_size_kb
    return GateResult(
        name="size",
        passed=actual_kb <= cap,
        detail=f"artifact {actual_kb:.1f} KB vs budget {cap:.1f} KB",
        remediation=(
            f"Over budget by {actual_kb - cap:.1f} KB. Try in order: "
            "quantization-aware training at lower bit width (int8 → int6 → int4), "
            "then width reduction, then pruning. Re-run the baseline gate after "
            "each — compression that breaks accuracy is not a win."
        ),
    )


def latency_gate(experiment: Experiment, p95_ms: float) -> GateResult:
    """Measure p95, not mean. Users feel the slow tail, not the average.

    Measure warm, then measure cold separately: first-interaction latency is a
    different UX problem and needs a different fix (preload, warm-up, skeleton).
    """
    cap = experiment.budgets.max_latency_ms
    band = experiment.budgets.latency_band
    return GateResult(
        name="latency",
        passed=p95_ms <= cap,
        detail=f"p95 {p95_ms:.1f} ms vs '{band}' band ceiling {cap:.0f} ms",
        remediation=(
            f"Too slow for the '{band}' band, so the interaction you designed "
            "will not feel the way you designed it. Options: batch across the "
            "visible window, move to a Web Worker so the main thread stays free, "
            "quantize further, or honestly re-target a slower band and add "
            "progressive feedback to the UI."
        ),
    )


def patience_gate(experiment: Experiment, eval_history: Sequence[float],
                  higher_is_better: bool = True) -> GateResult:
    """Stop when N consecutive evals fail to strictly improve on the best so far.

    This is the gate that prevents the most common and most expensive failure
    mode of agent-run ML: a plausible-looking loop that burns a night of compute
    going nowhere.
    """
    patience = experiment.budgets.patience_evals
    if len(eval_history) <= patience:
        return GateResult(
            name="patience",
            passed=True,
            detail=f"{len(eval_history)} eval(s), patience {patience} not yet tested",
        )

    best_before = (
        max(eval_history[:-patience]) if higher_is_better else min(eval_history[:-patience])
    )
    recent = eval_history[-patience:]
    improved = any(
        (v > best_before) if higher_is_better else (v < best_before) for v in recent
    )
    return GateResult(
        name="patience",
        passed=improved,
        detail=(
            f"last {patience} evals {[f'{v:.4f}' for v in recent]} vs "
            f"best-before {best_before:.4f}"
        ),
        remediation=(
            "No strict improvement within patience. Stop this run. Write what you "
            "learned into the run manifest and change something structural — the "
            "representation, the architecture family, or the task definition. "
            "Another seed is not a change."
        ),
    )


def wallclock_gate(experiment: Experiment, elapsed_minutes: float) -> GateResult:
    cap = experiment.budgets.max_wallclock_minutes
    return GateResult(
        name="wallclock",
        passed=elapsed_minutes <= cap,
        detail=f"{elapsed_minutes:.1f} min elapsed vs cap {cap} min",
        remediation=(
            "Wall-clock cap hit. Stop and report. If the curve was still climbing, "
            "that is a finding worth recording — raise the cap deliberately in the "
            "experiment file rather than letting a run drift past it."
        ),
    )


def run_all(
    experiment: Experiment,
    *,
    candidate_value: float,
    size_kb: float,
    p95_ms: float,
    eval_history: Sequence[float],
    elapsed_minutes: float,
    higher_is_better: bool = True,
) -> tuple[bool, list[GateResult]]:
    """Run every gate. Returns (all_passed, results).

    Order matters for reading, not for logic: baseline first because it is the
    one that most often should stop the work entirely.
    """
    results = [
        baseline_gate(experiment, candidate_value, higher_is_better),
        size_gate(experiment, size_kb),
        latency_gate(experiment, p95_ms),
        patience_gate(experiment, eval_history, higher_is_better),
        wallclock_gate(experiment, elapsed_minutes),
    ]
    return all(r.passed for r in results), results
