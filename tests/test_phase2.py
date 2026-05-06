"""Phase 2 단위 테스트: 단계 분류 로직 + 6개 역사적 시점."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from classifier import (
    classify_phase,
    _cli_declining, _anfci_turning_positive, _vix_trending_up_or_30plus,
    _cli_rebounding, _anfci_peak_declining, _vix_cooling_from_high, _move_peak_declining,
    _cli_above_100_rising, _anfci_negative, _vix_below_20, _move_below_avg,
    _cli_expanding, _anfci_stable_or_rising, _vix_temp_spike_25_30, _move_short_term_rising,
)

FRED_KEY = os.environ.get("FRED_API_KEY", "")


# ── 헬퍼 ───────────────────────────────────────────────────────

def s(*values) -> pd.Series:
    return pd.Series(list(values), dtype=float)


# ── 회피 조건 ──────────────────────────────────────────────────

class TestAvoidanceConditions:
    def test_cli_declining_true(self):
        assert _cli_declining(s(101, 100, 99, 98)) is True

    def test_cli_declining_false_rising(self):
        assert _cli_declining(s(98, 99, 100, 101)) is False

    def test_anfci_turning_positive_from_negative(self):
        assert _anfci_turning_positive(s(-0.5, -0.3, -0.1, 0.2, 0.5)) is True

    def test_anfci_turning_positive_rising_fast(self):
        assert _anfci_turning_positive(s(0.0, 0.1, 0.2, 0.3, 0.5)) is True

    def test_anfci_not_turning_stable_positive(self):
        # 이미 안정적으로 양수 → 전환 아님
        assert _anfci_turning_positive(s(0.5, 0.5, 0.5, 0.5, 0.5)) is False

    def test_vix_30plus(self):
        assert _vix_trending_up_or_30plus(s(*([20] * 10 + [35]))) is True

    def test_vix_trending_up_15pct(self):
        assert _vix_trending_up_or_30plus(s(*([15] * 10 + [18]))) is True

    def test_vix_stable_no_trend(self):
        assert _vix_trending_up_or_30plus(s(*([18] * 11))) is False


# ── 1단계 조건 ─────────────────────────────────────────────────

class TestPhase1Conditions:
    def test_cli_rebounding(self):
        assert _cli_rebounding(s(96, 95, 96, 97)) is True

    def test_cli_rebounding_false_above_100(self):
        assert _cli_rebounding(s(100, 101, 102, 103)) is False

    def test_anfci_peak_declining(self):
        assert _anfci_peak_declining(s(0.5, 1.5, 1.8, 1.6, 1.2)) is True

    def test_anfci_peak_declining_false_still_rising(self):
        assert _anfci_peak_declining(s(0.5, 0.8, 1.0, 1.3, 1.8)) is False

    def test_vix_cooling(self):
        # 30일 고점 >30, 현재 <80%
        vix = s(*([35] * 30 + [24]))
        assert _vix_cooling_from_high(vix) is True

    def test_vix_cooling_false_not_below_threshold(self):
        vix = s(*([35] * 30 + [29]))
        assert _vix_cooling_from_high(vix) is False

    def test_move_peak_declining(self):
        assert _move_peak_declining(s(*([100] * 5 + [150] + [130, 120, 110, 105, 100]))) is True

    def test_move_peak_declining_false_at_peak(self):
        assert _move_peak_declining(s(*([100] * 10 + [150]))) is False


# ── 2단계 조건 ─────────────────────────────────────────────────

class TestPhase2Conditions:
    def test_cli_above_100_rising(self):
        assert _cli_above_100_rising(s(100.5, 101.0, 101.5, 102.0)) is True

    def test_cli_above_100_rising_false_below_100(self):
        assert _cli_above_100_rising(s(97, 98, 99, 99.5)) is False

    def test_anfci_negative(self):
        assert _anfci_negative(s(-0.3)) is True

    def test_anfci_negative_false(self):
        assert _anfci_negative(s(0.1)) is False

    def test_vix_below_20(self):
        assert _vix_below_20(s(17.0)) is True

    def test_vix_below_20_false(self):
        assert _vix_below_20(s(22.0)) is False

    def test_move_below_avg(self):
        # 평균 100, 현재 80
        assert _move_below_avg(s(*([100] * 19 + [80]))) is True


# ── 3단계 조건 ─────────────────────────────────────────────────

class TestPhase3Conditions:
    def test_cli_expanding(self):
        assert _cli_expanding(s(101.5, 102.0)) is True

    def test_vix_temp_spike(self):
        assert _vix_temp_spike_25_30(s(27.0)) is True

    def test_vix_temp_spike_false_too_high(self):
        assert _vix_temp_spike_25_30(s(32.0)) is False

    def test_move_short_term_rising(self):
        assert _move_short_term_rising(s(90, 91, 92, 93, 94, 96)) is True


# ── 통합 단계 분류 ─────────────────────────────────────────────

class TestClassifyPhase:
    def _make_phase2_data(self):
        cli   = s(100.5, 101.0, 101.5, 102.0, 102.5, 103.0)
        anfci = s(-0.5, -0.4, -0.4, -0.3, -0.3, -0.3, -0.3, -0.2)
        vix   = s(*([17.0] * 40))
        move  = s(*([100.0] * 399 + [85.0]))
        return cli, anfci, vix, move

    def _make_avoidance_data(self):
        cli   = s(101, 100, 99, 98, 97, 96)
        anfci = s(-0.3, -0.1, 0.1, 0.3, 0.6)  # 음→양 전환
        vix   = s(*([20.0] * 10 + [35.0]))
        move  = s(*([100.0] * 400))
        return cli, anfci, vix, move

    def _make_phase1_data(self):
        cli   = s(96.0, 95.0, 95.5, 96.5, 97.0, 97.5)
        anfci = s(0.5, 1.8, 1.6, 1.4, 1.2, 1.0, 0.8, 0.6)
        vix   = s(*([35.0] * 30 + [24.0] * 10))
        move  = s(*([100.0] * 5 + [160.0] + [140.0, 130.0, 120.0, 110.0, 100.0]))
        return cli, anfci, vix, move

    def test_classify_avoidance(self):
        assert classify_phase(*self._make_avoidance_data()) == "회피"

    def test_classify_phase1(self):
        assert classify_phase(*self._make_phase1_data()) == "1단계"

    def test_classify_phase2(self):
        assert classify_phase(*self._make_phase2_data()) == "2단계"

    def test_avoidance_takes_priority_over_phase1(self):
        # 회피 2개 + 1단계 3개 동시 충족 → 회피 우선
        cli   = s(101, 100, 99, 98, 97, 96)   # declining (회피)
        anfci = s(-0.3, -0.1, 0.1, 0.3, 0.6)  # turning positive (회피)
        vix   = s(*([35.0] * 30 + [24.0] * 10))  # cooling (1단계)
        move  = s(*([160.0] + [140.0, 130.0, 120.0, 110.0, 100.0] + [100.0] * 394))
        assert classify_phase(cli, anfci, vix, move) == "회피"


# ── 역사적 시점 통합 테스트 (실 FRED 데이터) ──────────────────────

@pytest.mark.skipif(not FRED_KEY, reason="FRED_API_KEY 미설정")
class TestHistoricalPoints:
    """6개 핵심 시점 분류 검증 (실 FRED 데이터)."""

    def _fetch(self, end_date: str) -> tuple:
        from fetchers import fetch_series, fetch_move_series
        cli   = fetch_series("OECDLOLITOAASTSAM", FRED_KEY, end_date=end_date, n_periods=6)
        anfci = fetch_series("ANFCI",             FRED_KEY, end_date=end_date, n_periods=8)
        vix   = fetch_series("VIXCLS",            FRED_KEY, end_date=end_date, n_periods=40)
        move  = fetch_move_series(n_periods=400,            end_date=end_date)
        assert cli is not None and anfci is not None and vix is not None
        return cli, anfci, vix, move if move is not None else pd.Series(dtype=float)

    def test_2008_10_lehman_avoidance(self):
        assert classify_phase(*self._fetch("2008-10-31")) == "회피"

    def test_2009_08_recovery_phase1(self):
        assert classify_phase(*self._fetch("2009-08-31")) == "1단계"

    def test_2020_03_covid_avoidance(self):
        assert classify_phase(*self._fetch("2020-03-31")) == "회피"

    def test_2022_01_rate_hike_avoidance(self):
        assert classify_phase(*self._fetch("2022-01-31")) == "회피"

    def test_2022_10_bottom_phase1(self):
        assert classify_phase(*self._fetch("2022-10-31")) == "1단계"

    def test_2017_06_goldilocks_phase2(self):
        assert classify_phase(*self._fetch("2017-06-30")) == "2단계"