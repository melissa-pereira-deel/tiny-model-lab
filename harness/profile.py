"""Measure the two numbers the design gates need: size on disk and p95 latency.

Deliberately dependency-light. If you cannot measure it with the standard
library plus whatever runtime you already have, the measurement is probably too
clever to trust.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Callable, Sequence


def artifact_size_kb(path: str | Path) -> float:
    """Size of the thing you actually ship.

    For a directory (a .mlpackage, a split ONNX model) this sums the tree.
    Report this number, not the parameter count: users download bytes.
    """
    p = Path(path)
    if p.is_dir():
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    else:
        total = p.stat().st_size
    return total / 1024.0


def latency_ms(
    fn: Callable[[], object],
    *,
    warmup: int = 10,
    iterations: int = 100,
) -> dict[str, float]:
    """Time a callable, separating warm from cold.

    The warmup runs are discarded from the main stats but the very first call is
    reported as `cold_ms`, because first-interaction latency is its own UX
    problem — it is what the user feels once, and judges you on.
    """
    t0 = time.perf_counter()
    fn()
    cold = (time.perf_counter() - t0) * 1000.0

    for _ in range(max(0, warmup - 1)):
        fn()

    samples: list[float] = []
    for _ in range(iterations):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000.0)

    samples.sort()
    return {
        "cold_ms": cold,
        "mean_ms": statistics.fmean(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": samples[min(len(samples) - 1, int(0.95 * len(samples)))],
        "p99_ms": samples[min(len(samples) - 1, int(0.99 * len(samples)))],
        "iterations": float(iterations),
    }


def tradeoff_row(name: str, accuracy: float, size_kb: float, p95: float) -> dict:
    """One point on the accuracy-size-latency curve.

    Collect these across runs and plot them. The curve is the real deliverable of
    a tiny-model project; a single "best" number hides the decision you are
    actually making.
    """
    return {
        "variant": name,
        "accuracy": accuracy,
        "size_kb": size_kb,
        "p95_ms": p95,
        "accuracy_per_kb": accuracy / size_kb if size_kb else float("nan"),
    }


def summarize(rows: Sequence[dict]) -> str:
    if not rows:
        return "(no variants measured)"
    w = max(len(str(r["variant"])) for r in rows)
    lines = [f"{'variant'.ljust(w)}  {'acc':>8}  {'size KB':>9}  {'p95 ms':>8}"]
    for r in rows:
        lines.append(
            f"{str(r['variant']).ljust(w)}  {r['accuracy']:>8.4f}  "
            f"{r['size_kb']:>9.1f}  {r['p95_ms']:>8.1f}"
        )
    return "\n".join(lines)
