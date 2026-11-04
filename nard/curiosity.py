"""Budget-aware exploration scoring. Offline-only policy; it cannot fetch URLs.

Values are estimates, not verified expected economic returns. Never evaluate
a target outside the human-approved source registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt


@dataclass(frozen=True)
class SourceStats:
    source_id: str
    approved: bool
    pulls: int
    useful_observations: int
    freshness_hours: float
    estimated_cost_usd: float
    novelty: float

    def __post_init__(self):
        if self.pulls < 0 or self.useful_observations < 0 or self.useful_observations > self.pulls:
            raise ValueError("Inconsistent pulls")
        if self.estimated_cost_usd < 0 or self.freshness_hours < 0:
            raise ValueError("Costs and age must be nonnegative")
        if not 0 <= self.novelty <= 1:
            raise ValueError("Novelty must be [0,1]")


def voi_score(source: SourceStats, *, total_pulls: int, exploration: float = 0.25,
              dollar_penalty: float = 1.0) -> float:
    if not source.approved:
        return float("-inf")
    if total_pulls < source.pulls or total_pulls < 0:
        raise ValueError("Invalid total pulls")
    hit_rate = (source.useful_observations + 1) / (source.pulls + 2)  # Smoothed estimate
    bonus = exploration * sqrt(2 * log(total_pulls + 2) / (source.pulls + 1))
    staleness = min(source.freshness_hours / 168, 1.0) * 0.15
    return hit_rate + bonus + 0.35 * source.novelty + staleness - dollar_penalty * source.estimated_cost_usd


def choose_sources(sources: list[SourceStats], *, total_pulls: int, budget_usd: float,
                   max_sources: int = 5) -> list[SourceStats]:
    if budget_usd < 0 or max_sources < 0:
        raise ValueError("Budget and count must be nonnegative")
    ranked = sorted(sources, key=lambda s: (-voi_score(s, total_pulls=total_pulls), s.source_id))
    chosen = []
    remaining = budget_usd
    for s in ranked:
        if not s.approved:
            continue
        if len(chosen) == max_sources:
            break
        if s.estimated_cost_usd <= remaining:
            chosen.append(s)
            remaining -= s.estimated_cost_usd
    return chosen
