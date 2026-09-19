"""A worked example of the loop, with no ML dependencies.

The task is deliberately trivial: classify a short string as one of four token
kinds (word / number / symbol / whitespace). The point is not the task. The
point is to show the shape of a gated experiment end to end, in about a second,
so you can see what the harness does before you spend a night training.

It also demonstrates the most important outcome in this repo, which is the one
nobody designs for: the baseline wins, the gate blocks promotion, and the
correct move is to ship the baseline.

    python examples/01-hello-tiny/run.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.__main__ import use_utf8_stdout
from harness.experiment import Experiment, finish_run, record_eval, start_run
from harness.gates import run_all
from harness.profile import latency_ms, summarize, tradeoff_row

# This prints em dashes, and Python otherwise inherits the locale encoding —
# which raises UnicodeEncodeError under cp932, koi8-r or ascii. See #11.
use_utf8_stdout()

HERE = Path(__file__).parent
random.seed(0)

KINDS = ("word", "number", "symbol", "space")


def make_data(n: int) -> list[tuple[str, str]]:
    """Generate labelled examples from a deterministic teacher.

    The 'teacher' here is just Python's own string methods — which is exactly
    the point of the source hierarchy in the dataset-synthesis skill. Your
    teacher does not have to be a neural network. It has to be correct.
    """
    rows = []
    for _ in range(n):
        kind = random.choice(KINDS)
        if kind == "word":
            body = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(1, 8)))
            # A third of words start with a digit ("3rd", "2x", "4chan"). This is
            # what makes first-character lookup insufficient: the same leading
            # character now points at two different labels, and no amount of
            # data resolves it. The ceiling is in the representation.
            s = (random.choice("23456789") + body) if random.random() < 0.34 else body
        elif kind == "number":
            s = "".join(random.choices("0123456789", k=random.randint(1, 5)))
        elif kind == "symbol":
            s = "".join(random.choices("{}[]()<>+-*/=;:,.", k=random.randint(1, 3)))
        else:
            s = " " * random.randint(1, 4)
        rows.append((s, kind))
    return rows


def baseline_classify(s: str) -> str:
    """The deterministic baseline: a few rules, no training, zero bytes shipped.

    Note it looks at the *whole* string. That is the only reason it beats the
    model below — not because rules are smarter, but because it sees more.
    """
    if s.isspace():
        return "space"
    if s.isdigit():
        return "number"
    if s.isalnum():
        return "word"
    return "symbol"


class ToyModel:
    """A stand-in 'learned' model: a lookup table over the first character.

    Stands in for a real trained model so the example runs anywhere. It learns
    something genuinely useful from data and is still worse than four lines of
    rules — which is the realistic outcome the harness exists to catch.
    """

    def __init__(self) -> None:
        self.table: dict[str, str] = {}

    def fit(self, rows: list[tuple[str, str]]) -> ToyModel:
        counts: dict[str, dict[str, int]] = {}
        for s, label in rows:
            key = s[0] if s else ""
            counts.setdefault(key, {}).setdefault(label, 0)
            counts[key][label] += 1
        self.table = {k: max(v, key=v.get) for k, v in counts.items()}
        return self

    def predict(self, s: str) -> str:
        return self.table.get(s[0] if s else "", "word")

    @property
    def size_kb(self) -> float:
        # Rough on-disk estimate: one char key plus a small label index.
        return len(self.table) * 2 / 1024.0


def accuracy(fn, rows) -> float:
    return sum(fn(s) == label for s, label in rows) / len(rows)


def main() -> int:
    train = make_data(4000)
    holdout = make_data(1000)  # built first, never inspected during iteration

    exp = Experiment.from_yaml(HERE / "experiment.yaml")

    # Step 1: measure the baseline. Always first.
    base_acc = accuracy(baseline_classify, holdout)
    exp.baseline.value = base_acc
    print(f"baseline '{exp.baseline.name}': {base_acc:.4f} on held-out\n")

    run_dir = start_run(exp, runs_dir=HERE / "runs")
    print(f"run: {run_dir.name}\n")

    history: list[float] = []
    rows = []

    # Step 2: train on growing data, gating after every eval.
    for n in (250, 1000, 4000):
        model = ToyModel().fit(train[:n])
        acc = accuracy(model.predict, holdout)
        timing = latency_ms(lambda m=model: m.predict("hello"), warmup=5, iterations=200)
        history.append(acc)

        record_eval(
            run_dir,
            variant=f"lookup-{n}",
            metric_value=acc,
            size_kb=model.size_kb,
            p95_ms=timing["p95_ms"],
            elapsed_minutes=0.01,
        )
        rows.append(tradeoff_row(f"lookup-{n}", acc, model.size_kb, timing["p95_ms"]))

        passed, results = run_all(
            exp,
            candidate_value=acc,
            size_kb=model.size_kb,
            p95_ms=timing["p95_ms"],
            eval_history=history,
            elapsed_minutes=0.01,
        )
        print(f"--- eval: n={n} ---")
        for r in results:
            print(r)
        print()

        if not passed:
            finish_run(run_dir, "stopped", "gate failure")

    print("accuracy / size / latency curve:")
    print(summarize(rows))
    print(
        "\nOutcome: the deterministic baseline wins, so the baseline ships.\n"
        "That is a successful run. The harness cost you one second to learn it\n"
        "instead of a week, and the reasoning is now in the run manifest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
