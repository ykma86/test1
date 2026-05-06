"""Phase 3 단위 테스트: 4분면 체제 분류."""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from regime import classify_regime, _growth_rising, _inflation_rising

FRED_KEY = os.environ.get("FRED_API_KEY", "")


def s(*values) -> pd.Series:
    return pd.Series(list(values), dtype=float)


# ── 성장축 ─────────────────────────────────────────────────────

class TestGrowthRising:
    def test_rising(self):
        assert _growth_rising(s(99.0, 99.5, 100.0, 100.5)) is True

    def test_falling(self):
        assert _growth_rising(s(101.0, 100.5, 100.0, 99.5)) is False

    def test_flat(self):
        assert _growth_rising(s(100.0, 100.0, 100.0, 100.0)) is False

    def test_too_short(self):
        assert _growth_rising(s(100.0, 100.5, 101.0)) is False


# ── 인플레이션축 ───────────────────────────────────────────────

class TestInflationRising:
    def test_rising(self):
        assert _inflation_rising(s(1.5, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8)) is True

    def test_falling(self):
        assert _inflation_rising(s(2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.5)) is False

    def test_too_short(self):
        assert _inflation_rising(s(2.0, 2.1, 2.2, 2.3, 2.4, 2.5)) is False  # 6개 = 부족


# ── 4분면 분류 ─────────────────────────────────────────────────

class TestClassifyRegime:
    def _cli_up(self):
        return s(99.0, 99.5, 100.0, 100.5, 101.0, 101.5)

    def _cli_down(self):
        return s(102.0, 101.5, 101.0, 100.5, 100.0, 99.5)

    def _bei_up(self):
        return s(1.5, 1.8, 2.0, 2.2, 2.5, 2.7, 3.0)

    def _bei_down(self):
        return s(3.0, 2.8, 2.6, 2.4, 2.2, 2.0, 1.9)

    def test_goldilocks(self):
        assert classify_regime(self._cli_up(), self._bei_down()) == "골디락스"

    def test_reflation(self):
        assert classify_regime(self._cli_up(), self._bei_up()) == "리플레이션"

    def test_stagflation(self):
        assert classify_regime(self._cli_down(), self._bei_up()) == "스태그플레이션"

    def test_recession(self):
        assert classify_regime(self._cli_down(), self._bei_down()) == "침체"


# ── 역사적 시점 통합 테스트 (실 FRED 데이터) ──────────────────────

@pytest.mark.skipif(not FRED_KEY, reason="FRED_API_KEY 미설정")
class TestHistoricalRegime:
    """4개 핵심 시점 체제 분류 검증."""

    def _fetch(self, end_date: str) -> tuple:
        from main import fetch_regime_data
        result = fetch_regime_data(FRED_KEY, end_date=end_date)
        assert result is not None
        return result

    def test_2017_06_goldilocks(self):
        assert classify_regime(*self._fetch("2017-06-30")) == "골디락스"

    def test_2022_01_stagflation(self):
        assert classify_regime(*self._fetch("2022-01-31")) == "스태그플레이션"

    def test_2008_10_recession(self):
        assert classify_regime(*self._fetch("2008-10-31")) == "침체"

    def test_2009_08_reflation(self):
        assert classify_regime(*self._fetch("2009-08-31")) == "리플레이션"
