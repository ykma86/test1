"""Phase 4 단위 테스트: 모멘텀 7개 지표 점수화."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from momentum import (
    _check_rs_rising, _check_ma_aligned, _check_rsi_above50,
    _check_macd_bullish, _check_near_high, _check_volume_rising,
    _check_sharpe_positive, score_ticker, scan_all,
)


# ── 헬퍼 ─────────────────────────────────────────────────────

def rising_series(n: int, start: float = 100.0, step: float = 0.5) -> pd.Series:
    return pd.Series([start + i * step for i in range(n)], dtype=float)


def falling_series(n: int, start: float = 120.0, step: float = 0.5) -> pd.Series:
    return pd.Series([start - i * step for i in range(n)], dtype=float)


def flat_series(n: int, val: float = 100.0) -> pd.Series:
    return pd.Series([val] * n, dtype=float)


# ── RS 우상향 ─────────────────────────────────────────────────

class TestCheckRsRising:
    def test_rising(self):
        close = rising_series(60, 100, 0.5)
        spy = flat_series(60, 100.0)
        assert _check_rs_rising(close, spy) is True

    def test_falling(self):
        close = falling_series(60, 120, 0.5)
        spy = flat_series(60, 100.0)
        assert _check_rs_rising(close, spy) is False

    def test_too_short(self):
        assert _check_rs_rising(flat_series(30), flat_series(30)) is False


# ── MA 정렬 ──────────────────────────────────────────────────

class TestCheckMaAligned:
    def test_aligned(self):
        # 우상향 200일 → price > 50MA > 200MA
        close = rising_series(210, 50, 0.5)
        assert _check_ma_aligned(close) is True

    def test_not_aligned(self):
        close = falling_series(210, 200, 0.5)
        assert _check_ma_aligned(close) is False

    def test_too_short(self):
        assert _check_ma_aligned(rising_series(100)) is False


# ── RSI ──────────────────────────────────────────────────────

class TestCheckRsiAbove50:
    def test_above_50(self):
        # 꾸준히 상승 → RSI 높음
        close = rising_series(30, 100, 1.0)
        assert _check_rsi_above50(close) is True

    def test_below_50(self):
        # 꾸준히 하락 → RSI 낮음
        close = falling_series(30, 130, 1.0)
        assert _check_rsi_above50(close) is False

    def test_too_short(self):
        assert _check_rsi_above50(flat_series(10)) is False


# ── MACD ─────────────────────────────────────────────────────

class TestCheckMacdBullish:
    def test_bullish(self):
        # 가속 상승(2차 함수) → MACD 0선 위, 히스토그램 확대
        close = pd.Series([100 + i ** 2 * 0.1 for i in range(60)], dtype=float)
        assert _check_macd_bullish(close) is True

    def test_too_short(self):
        assert _check_macd_bullish(flat_series(20)) is False


# ── 신고가 ────────────────────────────────────────────────────

class TestCheckNearHigh:
    def test_at_high(self):
        # 마지막 값이 최고가
        close = rising_series(25, 100, 1.0)
        assert _check_near_high(close) is True

    def test_not_at_high(self):
        # 최근 5일이 이전 고점보다 낮음
        close = pd.Series([100] * 15 + [120] + [90] * 5, dtype=float)
        assert _check_near_high(close) is False

    def test_too_short(self):
        assert _check_near_high(flat_series(10)) is False


# ── 거래량 ────────────────────────────────────────────────────

class TestCheckVolumeRising:
    def test_rising(self):
        volume = pd.Series([100] * 15 + [200] * 5, dtype=float)
        assert _check_volume_rising(volume) is True

    def test_falling(self):
        volume = pd.Series([200] * 15 + [50] * 5, dtype=float)
        assert _check_volume_rising(volume) is False

    def test_zero_volume(self):
        assert _check_volume_rising(flat_series(20, 0.0)) is False


# ── Sharpe ───────────────────────────────────────────────────

class TestCheckSharpePositive:
    def test_positive(self):
        close = rising_series(70, 100, 1.0)
        assert _check_sharpe_positive(close) is True

    def test_negative(self):
        close = falling_series(70, 170, 1.0)
        assert _check_sharpe_positive(close) is False

    def test_too_short(self):
        assert _check_sharpe_positive(flat_series(30)) is False


# ── score_ticker ─────────────────────────────────────────────

class TestScoreTicker:
    def _make_mock_data(self, close_vals, volume_vals=None):
        if volume_vals is None:
            volume_vals = [1_000_000] * len(close_vals)
        df = pd.DataFrame({
            "Close": close_vals,
            "Volume": volume_vals,
            "High": close_vals,
            "Low": close_vals,
            "Open": close_vals,
        })
        return df

    @patch("momentum._fetch_ohlcv")
    def test_returns_dict_with_score(self, mock_fetch):
        close = list(rising_series(250, 50, 0.5))
        mock_fetch.return_value = self._make_mock_data(close)
        result = score_ticker("TQQQ")
        assert result is not None
        assert "ticker" in result
        assert "score" in result
        assert 0 <= result["score"] <= 7

    @patch("momentum._fetch_ohlcv")
    def test_returns_none_on_fetch_failure(self, mock_fetch):
        mock_fetch.return_value = None
        assert score_ticker("TQQQ") is None


# ── scan_all ─────────────────────────────────────────────────

class TestScanAll:
    @patch("momentum.score_ticker")
    @patch("momentum._fetch_ohlcv")
    def test_sorted_descending(self, mock_fetch, mock_score):
        mock_fetch.return_value = None  # SPY fetch
        mock_score.side_effect = lambda ticker, spy_close=None: (
            {"ticker": ticker, "score": len(ticker), "details": {}}
        )
        results = scan_all()
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @patch("momentum.score_ticker")
    @patch("momentum._fetch_ohlcv")
    def test_skips_none_results(self, mock_fetch, mock_score):
        mock_fetch.return_value = None
        mock_score.return_value = None
        results = scan_all()
        assert results == []
