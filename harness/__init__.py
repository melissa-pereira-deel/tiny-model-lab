"""tiny-model-lab harness: experiment specs, gates, profiling, promotion."""

from .experiment import Experiment, Baseline, Budgets, start_run, record_eval, finish_run
from .gates import run_all, GateResult

__all__ = [
    "Experiment", "Baseline", "Budgets",
    "start_run", "record_eval", "finish_run",
    "run_all", "GateResult",
]
__version__ = "0.1.0"
