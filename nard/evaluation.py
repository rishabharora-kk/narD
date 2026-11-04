"""Point-in-time evaluation primitives; test with genuinely archived snapshots.

available_at is the earliest verifiable publication timestamp, not an
original document's claimed publication date or a retrospective scrape date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import log
from statistics import mean


@dataclass(frozen=True)
class HistoricalSignal:
    signal_id: str
    available_at: datetime
    observed_at: datetime
    source_family: str
    evidence_hash: str

    def __post_init__(self):
        if self.available_at.tzinfo is None or self.observed_at.tzinfo is None:
            raise ValueError("Historical timestamps must include timezones")
        if not self.evidence_hash:
            raise ValueError("Historical evidence hash is required")


def observable_as_of(signal: HistoricalSignal, decision_at: datetime) -> bool:
    if decision_at.tzinfo is None:
        raise ValueError("Decision timestamp must include timezone")
    return max(signal.available_at, signal.observed_at) <= decision_at


def visible_signals(signals: list[HistoricalSignal], decision_at: datetime) -> list[HistoricalSignal]:
    return [s for s in signals if observable_as_of(s, decision_at)]


def brier_score(probability: float, outcome: int) -> float:
    if not 0 <= probability <= 1 or outcome not in (0, 1):
        raise ValueError("Probability in [0,1], binary outcome required")
    return (probability - outcome) ** 2


def log_score(probability: float, outcome: int, epsilon: float = 1e-12) -> float:
    if not 0 <= probability <= 1 or outcome not in (0, 1):
        raise ValueError("Probability in [0,1], binary outcome required")
    p = min(max(probability, epsilon), 1 - epsilon)
    return -(outcome * log(p) + (1 - outcome) * log(1 - p))


def detection_metrics(predicted: set[str], actual: set[str], *, costs: dict[str, float] | None = None) -> dict:
    """Closed-world evaluation; actual must include known misses for valid recall."""
    true_positives = predicted & actual
    false_positives = predicted - actual
    false_negatives = actual - predicted
    cost = sum((costs or {}).get(x, 0.0) for x in predicted)
    return {
        "true_positives": len(true_positives),
        "false_positives": len(false_positives),
        "false_negatives": len(false_negatives),
        "precision": len(true_positives) / len(predicted) if predicted else None,
        "recall": len(true_positives) / len(actual) if actual else None,
        "cost_per_true_catch": cost / len(true_positives) if true_positives else None,
    }


def forecast_metrics(forecasts: list[tuple[float, int]]) -> dict:
    if not forecasts:
        return {"n": 0, "mean_brier": None, "mean_log_loss": None}
    return {
        "n": len(forecasts),
        "mean_brier": mean(brier_score(p, y) for p, y in forecasts),
        "mean_log_loss": mean(log_score(p, y) for p, y in forecasts),
    }
