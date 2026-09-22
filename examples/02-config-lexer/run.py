"""A worked example that trains a real model and exports it.

Example 01 is dependency-free and stops at the gate. This one goes the rest of
the way: PyTorch → ONNX → onnxruntime, with the artifact measured in bytes on
disk, the conversion verified numerically, and a model card written at the end.

The export happens *inside* the eval loop, not after promotion, because the
size budget is about exported bytes rather than a parameter count. So the export
path is exercised whichever way the baseline gate goes -- `artifact_size_kb`
measures each one here, and `promote()` measures again whatever it is handed.

Needs the heavier extras:

    pip install -e ".[train]" onnx onnxruntime
    python examples/02-config-lexer/run.py
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baseline import classify as baseline_classify
from dialects import HELDOUT_DIALECTS, LABELS, TRAIN_DIALECTS, make_rows
from features import ENCODERS, MAX_LEN, scalars

from harness.__main__ import use_utf8_stdout
from harness.experiment import Experiment, finish_run, record_eval, start_run
from harness.gates import run_all
from harness.profile import artifact_size_kb, latency_ms, summarize, tradeoff_row
from harness.promote import promote

# This prints em dashes, and Python otherwise inherits the locale encoding —
# which raises UnicodeEncodeError under cp932, koi8-r or ascii. See #11.
use_utf8_stdout()

HERE = Path(__file__).parent
random.seed(0)
torch.manual_seed(0)

# Chosen, not prescribed. Nothing in this repo specifies an opset, so it is
# pinned here and named in the model card rather than left to the default.
ONNX_OPSET = 17

LABEL_INDEX = {name: i for i, name in enumerate(LABELS)}


class Lexer(nn.Module):
    """A small conv over the encoded line, plus the free scalar features.

    Convolution because the structure is local and position-shifted: a separator
    means the same thing wherever it appears. That is the weakest inductive bias
    that fits, which is what architecture-selection asks for.
    """

    def __init__(self, vocab: int, embed: int = 12, width: int = 24) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab, embed, padding_idx=0)
        self.conv = nn.Conv1d(embed, width, kernel_size=3, padding=1)
        self.head = nn.Linear(width + 6, len(LABELS))

    def forward(self, ids: torch.Tensor, feats: torch.Tensor) -> torch.Tensor:
        x = self.embed(ids).transpose(1, 2)
        x = torch.relu(self.conv(x)).amax(dim=2)
        return self.head(torch.cat([x, feats], dim=1))


def encode_batch(rows, encoder):
    ids = torch.tensor([encoder(line) for line, _, _ in rows], dtype=torch.long)
    feats = torch.tensor([scalars(line) for line, _, _ in rows], dtype=torch.float32)
    labels = torch.tensor([LABEL_INDEX[y] for _, y, _ in rows], dtype=torch.long)
    return ids, feats, labels


def train(model, rows, encoder, epochs: int = 12) -> None:
    ids, feats, labels = encode_batch(rows, encoder)
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for i in range(0, len(ids), 256):
            opt.zero_grad()
            loss = loss_fn(model(ids[i:i + 256], feats[i:i + 256]), labels[i:i + 256])
            loss.backward()
            opt.step()
    model.eval()


def export_onnx(model, path: Path) -> None:
    dummy_ids = torch.zeros(1, MAX_LEN, dtype=torch.long)
    dummy_feats = torch.zeros(1, 6, dtype=torch.float32)
    torch.onnx.export(
        model,
        (dummy_ids, dummy_feats),
        str(path),
        input_names=["ids", "feats"],
        output_names=["logits"],
        dynamic_axes={"ids": {0: "n"}, "feats": {0: "n"}, "logits": {0: "n"}},
        opset_version=ONNX_OPSET,
        dynamo=False,
    )


def onnx_predict(session, ids, feats) -> np.ndarray:
    out = session.run(None, {"ids": ids.numpy(), "feats": feats.numpy()})[0]
    return out.argmax(axis=1)


def accuracy(preds: np.ndarray, labels: torch.Tensor) -> float:
    return float((preds == labels.numpy()).mean())


def disagreement(a: np.ndarray, b: np.ndarray) -> float:
    """Share of held-out rows where two implementations pick different labels.

    export-pipeline, quantization-strategy and embedder.md all demand this as a
    number. None of them names an acceptable value, so it is reported rather
    than judged, and no gate is invented for it here.
    """
    return float((a != b).mean())


def main() -> int:
    # Held-out is two dialects the baseline was never written against, built
    # first and not inspected while iterating. Same generator, fresh seed.
    train_rows = make_rows(4800, TRAIN_DIALECTS, seed=1)
    holdout = make_rows(2400, HELDOUT_DIALECTS, seed=2)

    exp = Experiment.from_yaml(HERE / "experiment.yaml")

    # Step 1: measure the baseline. Always first.
    base_acc = sum(baseline_classify(line) == y for line, y, _ in holdout) / len(holdout)
    exp.baseline.value = base_acc
    on_train = sum(baseline_classify(t) == y for t, y, _ in train_rows) / len(train_rows)
    print(f"baseline '{exp.baseline.name}'")
    print(f"  {on_train:.4f} on the dialects it was written for {TRAIN_DIALECTS}")
    print(f"  {base_acc:.4f} on the held-out dialects {HELDOUT_DIALECTS}\n")

    run_dir = start_run(exp, runs_dir=HERE / "runs")
    artifacts = run_dir / "artifacts"
    print(f"run: {run_dir.name}\n")

    ho_ids_cache = {}
    history: list[float] = []
    rows = []
    best: tuple[float, Path, str] | None = None
    started = time.perf_counter()

    # Step 2: one structural change at a time. The only difference between these
    # two is the representation.
    for variant, encoder_name in (("conv-raw-chars", "raw"), ("conv-char-classes", "classes")):
        encoder, vocab = ENCODERS[encoder_name]
        model = Lexer(vocab)
        train(model, train_rows, encoder)

        ho = ho_ids_cache.setdefault(encoder_name, encode_batch(holdout, encoder))
        ho_ids, ho_feats, ho_labels = ho

        with torch.no_grad():
            torch_preds = model(ho_ids, ho_feats).argmax(dim=1).numpy()

        onnx_path = artifacts / f"{variant}.onnx"
        export_onnx(model, onnx_path)
        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        onnx_preds = onnx_predict(session, ho_ids, ho_feats)

        acc = accuracy(onnx_preds, ho_labels)
        disagree = disagreement(torch_preds, onnx_preds)
        size_kb = artifact_size_kb(onnx_path)
        one = (ho_ids[:1], ho_feats[:1])
        timing = latency_ms(
            lambda s=session, o=one: onnx_predict(s, *o), warmup=50, iterations=200
        )
        history.append(acc)

        record_eval(
            run_dir,
            variant=variant,
            metric_value=acc,
            size_kb=size_kb,
            p95_ms=timing["p95_ms"],
            elapsed_minutes=(time.perf_counter() - started) / 60.0,
            cold_ms=timing["cold_ms"],
            disagreement_vs_torch=disagree,
            representation=encoder_name,
        )
        rows.append(tradeoff_row(variant, acc, size_kb, timing["p95_ms"]))

        passed, results = run_all(
            exp,
            candidate_value=acc,
            size_kb=size_kb,
            p95_ms=timing["p95_ms"],
            eval_history=history,
            elapsed_minutes=(time.perf_counter() - started) / 60.0,
        )
        print(f"--- eval: {variant} (representation: {encoder_name}) ---")
        for r in results:
            print(r)
        print(f"       torch vs onnx disagreement: {disagree:.4f}")
        print(f"       cold start: {timing['cold_ms']:.1f} ms\n")

        if best is None or acc > best[0]:
            best = (acc, onnx_path, variant)
        if not passed:
            finish_run(run_dir, "stopped", "gate failure")

    # Step 3: quantization. The size gate already passed, so this is not a
    # rescue — it is the cheap first step quantization-strategy names, measured
    # rather than assumed, and it costs a disagreement rate to find out.
    assert best is not None
    _, best_path, best_variant = best
    int8_path = artifacts / f"{best_variant}-int8.onnx"
    quantize_dynamic(best_path, int8_path, weight_type=QuantType.QUInt8)

    encoder_name = "classes" if "classes" in best_variant else "raw"
    ho_ids, ho_feats, ho_labels = ho_ids_cache[encoder_name]
    fp32_session = ort.InferenceSession(str(best_path), providers=["CPUExecutionProvider"])
    int8_session = ort.InferenceSession(str(int8_path), providers=["CPUExecutionProvider"])
    fp32_preds = onnx_predict(fp32_session, ho_ids, ho_feats)
    int8_preds = onnx_predict(int8_session, ho_ids, ho_feats)

    int8_acc = accuracy(int8_preds, ho_labels)
    int8_disagree = disagreement(fp32_preds, int8_preds)
    int8_size = artifact_size_kb(int8_path)
    one = (ho_ids[:1], ho_feats[:1])
    int8_timing = latency_ms(
        lambda s=int8_session, o=one: onnx_predict(s, *o), warmup=50, iterations=200
    )
    history.append(int8_acc)

    record_eval(
        run_dir,
        variant=f"{best_variant}-int8",
        metric_value=int8_acc,
        size_kb=int8_size,
        p95_ms=int8_timing["p95_ms"],
        elapsed_minutes=(time.perf_counter() - started) / 60.0,
        cold_ms=int8_timing["cold_ms"],
        disagreement_vs_fp32=int8_disagree,
        quantization="dynamic QUInt8 (post-training)",
    )
    rows.append(tradeoff_row(f"{best_variant}-int8", int8_acc, int8_size, int8_timing["p95_ms"]))

    passed, results = run_all(
        exp,
        candidate_value=int8_acc,
        size_kb=int8_size,
        p95_ms=int8_timing["p95_ms"],
        eval_history=history,
        elapsed_minutes=(time.perf_counter() - started) / 60.0,
    )
    print(f"--- eval: {best_variant}-int8 (post-training dynamic quantization) ---")
    for r in results:
        print(r)
    print(f"       fp32 vs int8 disagreement: {int8_disagree:.4f}")
    print(f"       size: {artifact_size_kb(best_path):.1f} KB -> {int8_size:.1f} KB\n")
    if not passed:
        finish_run(run_dir, "stopped", "gate failure")

    print("accuracy / size / latency curve:")
    print(summarize(rows))

    # Step 4: promotion, into this example's own champion directory rather than
    # the repo root, so running the example does not leave files in a clone.
    # Calling promote() directly is the right thing from inside a Python program
    # — `python -m harness ship` calls the same function, and would reprint the
    # whole gate report this script has already printed.
    # The int8 file, not `best_path`. `promote()` takes the *last* eval as the
    # candidate, and the last eval here is the int8 one — handing it the fp32
    # file put an 8.4 KB artifact in champion/ under a 4.9 KB eval (#27). int8
    # is also simply the better ship: same held-out accuracy as the fp32 it
    # came from, at 42% of the bytes.
    champion = HERE / "champion"
    verdict = promote(
        run_dir,
        int8_path,
        champion_dir=champion,
        ledger=champion / "LEDGER.md",
    )
    print(f"\npromotion: {verdict.splitlines()[0]}")
    print(
        "the same call from a shell:\n"
        "  python -m harness ship \\\n"
        f"    {os.path.relpath(run_dir)} \\\n"
        f"    {os.path.relpath(int8_path)} \\\n"
        f"    --champion-dir {os.path.relpath(champion)}"
    )

    write_model_card(run_dir, exp, int8_disagree)
    print(f"model card: {run_dir / 'MODEL_CARD.md'}")

    beat = max(history) > exp.baseline.value
    print(
        f"\nOutcome: the best variant scored {max(history):.4f} against a baseline of "
        f"{exp.baseline.value:.4f} on dialects neither had seen.\n"
        + (
            "The model wins, so it is promotable and the export is worth shipping."
            if beat
            else "The baseline wins again, so the baseline ships. The export, the size\n"
            "gate on real bytes and both disagreement rates are still measured — that\n"
            "machinery is what this example exists to exercise."
        )
    )
    return 0


def write_model_card(run_dir: Path, exp: Experiment, int8_disagree: float) -> None:
    # Every number comes from `final`, the eval that describes the artifact
    # that shipped. It used to take the accuracy from max(rows), which is the
    # best row across all variants -- so the moment quantization cost any
    # accuracy, the card paired one model's score with another's bytes. The
    # figure does not move today, because int8 ties fp32 here and max() returns
    # the first of equals; it is now read from the row it claims to describe.
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    final = manifest["evals"][-1]
    template = (Path(__file__).resolve().parents[2] / "harness/templates/MODEL_CARD.md").read_text(encoding="utf-8")
    card = template.replace("# Model card: <name>", "# Model card: config-lexer (example 02)")
    card += f"""

---

*Generated by `examples/02-config-lexer/run.py` for run `{manifest["run_id"]}`.*

| | |
|---|---|
| Variant shipped | {final.get("variant", "unnamed")} |
| Size (shipped bytes) | {final["size_kb"] * 1024:.0f} |
| p95 latency (warm, this machine) | {final["p95_ms"]:.3f} ms |
| Cold start | {final.get("cold_ms", float("nan")):.1f} ms |
| Metric vs baseline | {final["metric_value"]:.4f} vs {exp.baseline.value:.4f} |
| Baseline it must beat | {exp.baseline.name} |
| Disagreement (fp32 vs int8) | {int8_disagree:.4f} |

**What the metric actually measures.** Agreement with a synthetic generator, on
two config dialects held out from training. The generator is the ground truth by
construction, so there is no label noise — and equally, this is a demonstration
of the mechanism rather than evidence about real config files.

**What a headless example cannot answer.** The export-pipeline skill also asks
for a Web Worker, the WebGPU backend verified against WASM, and measurement on
target hardware; the five design-eval checks are all about a user interface.
A `run.py` answers none of those. They are not covered here.
"""
    (run_dir / "MODEL_CARD.md").write_text(card, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
