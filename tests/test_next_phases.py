from datetime import datetime, timedelta, timezone

import pytest

from nard.curiosity import SourceStats, choose_sources, voi_score
from nard.evaluation import (
    HistoricalSignal, brier_score, detection_metrics, forecast_metrics,
    log_score, visible_signals,
)
from nard.identities import compatible_join, extract_identifiers


def test_identifiers_exact_match_and_unsupported_company_name():
    a = extract_identifiers("Patent WO 2024/123456 and DOI 10.1234/ABC and CIN U12345PB2020PLC123456")
    b = extract_identifiers("WO2024123456; 10.1234/abc; U12345PB2020PLC123456")
    assert ("patent_wo", "WO2024123456") in compatible_join(a, b)
    assert ("cin", "U12345PB2020PLC123456") in compatible_join(a, b)
    assert ("doi", "10.1234/abc") in compatible_join(a, b)
    assert compatible_join(extract_identifiers("Acme Robotics"), extract_identifiers("Acme Robotics")) == []


def test_point_in_time_replay_requires_observation_and_publication():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    good = HistoricalSignal("x", now - timedelta(days=3), now - timedelta(days=1), "patent", "sha")
    late = HistoricalSignal("y", now - timedelta(days=3), now + timedelta(days=1), "grant", "sha")
    unpublished = HistoricalSignal("z", now + timedelta(days=1), now - timedelta(days=1), "grant", "sha")
    assert visible_signals([good, late, unpublished], now) == [good]
    with pytest.raises(ValueError):
        visible_signals([good], datetime(2026, 1, 10))


def test_forecast_metrics_and_no_divide_by_zero():
    assert brier_score(0.8, 1) == pytest.approx(0.04)
    assert log_score(1, 0) > 20
    assert forecast_metrics([])["mean_brier"] is None
    assert forecast_metrics([(0.8, 1), (0.2, 0)])["mean_brier"] == pytest.approx(0.04)
    metrics = detection_metrics({"hit", "false"}, {"hit", "miss"}, costs={"hit": 2, "false": 3})
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["cost_per_true_catch"] == 5
    assert detection_metrics(set(), set())["precision"] is None


def test_curiosity_is_budgeted_and_denies_unapproved():
    safe = SourceStats("safe", True, 10, 5, 24, 0.1, 0.9)
    blocked = SourceStats("blocked", False, 0, 0, 100, 0.0, 1.0)
    expensive = SourceStats("expensive", True, 3, 2, 12, 5.0, 0.5)
    assert voi_score(blocked, total_pulls=10) == float("-inf")
    assert choose_sources([blocked, expensive, safe], total_pulls=13, budget_usd=0.1) == [safe]
    with pytest.raises(ValueError):
        SourceStats("bad", True, 1, 2, 0, 0, 0)
