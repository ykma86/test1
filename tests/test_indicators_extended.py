"""확장 지표 fetch 함수 단위 테스트."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from fetchers import (
    fetch_copper,
    fetch_fed_balance,
    fetch_ism_pmi,
    fetch_m2_yoy,
    fetch_nfp_change,
    fetch_wti,
)


def _mock_fred(values: list[float]):
    """fredapi.Fred mock 헬퍼."""
    m = MagicMock()
    m.return_value.get_series.return_value = pd.Series(values, dtype=float)
    return m


def _mock_ticker(closes: list[float]):
    """yfinance.Ticker mock 헬퍼."""
    m = MagicMock()
    m.return_value.history.return_value = pd.DataFrame({"Close": closes})
    return m


# ── fetch_ism_pmi ─────────────────────────────────────────────────

class TestFetchIsmPmi:
    @patch("fetchers.Fred", new_callable=lambda: lambda: _mock_fred([50.5, 52.3, 53.1]))
    def test_returns_latest_value(self, mock_fred):
        with patch("fetchers.Fred", _mock_fred([50.5, 52.3, 53.1])):
            result = fetch_ism_pmi("key")
        assert result == pytest.approx(53.1, abs=0.1)

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("network error")):
            result = fetch_ism_pmi("key")
        assert result is None


# ── fetch_nfp_change ──────────────────────────────────────────────

class TestFetchNfpChange:
    def test_returns_mom_change(self):
        with patch("fetchers.Fred", _mock_fred([155000.0, 155250.0])):
            result = fetch_nfp_change("key")
        assert result == pytest.approx(250.0)

    def test_negative_change(self):
        with patch("fetchers.Fred", _mock_fred([155000.0, 154800.0])):
            result = fetch_nfp_change("key")
        assert result == pytest.approx(-200.0)

    def test_returns_none_when_single_entry(self):
        with patch("fetchers.Fred", _mock_fred([155000.0])):
            result = fetch_nfp_change("key")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("error")):
            result = fetch_nfp_change("key")
        assert result is None


# ── fetch_fed_balance ─────────────────────────────────────────────

class TestFetchFedBalance:
    def test_converts_millions_to_trillions(self):
        with patch("fetchers.Fred", _mock_fred([7_200_000.0])):
            result = fetch_fed_balance("key")
        assert result == pytest.approx(7.2, abs=0.01)

    def test_returns_none_on_empty(self):
        with patch("fetchers.Fred", _mock_fred([])):
            result = fetch_fed_balance("key")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("error")):
            result = fetch_fed_balance("key")
        assert result is None


# ── fetch_m2_yoy ──────────────────────────────────────────────────

class TestFetchM2Yoy:
    def test_returns_yoy_pct(self):
        data = [100.0] * 12 + [103.0]  # +3% YoY
        with patch("fetchers.Fred", _mock_fred(data)):
            result = fetch_m2_yoy("key")
        assert result == pytest.approx(3.0, abs=0.1)

    def test_negative_yoy(self):
        data = [100.0] * 12 + [97.0]  # -3% YoY
        with patch("fetchers.Fred", _mock_fred(data)):
            result = fetch_m2_yoy("key")
        assert result == pytest.approx(-3.0, abs=0.1)

    def test_returns_none_when_insufficient(self):
        with patch("fetchers.Fred", _mock_fred([100.0] * 5)):
            result = fetch_m2_yoy("key")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("error")):
            result = fetch_m2_yoy("key")
        assert result is None


# ── fetch_wti ─────────────────────────────────────────────────────

class TestFetchWti:
    def test_returns_price(self):
        with patch("fetchers.yf.Ticker", _mock_ticker([78.5, 79.2, 78.9])):
            result = fetch_wti()
        assert result == pytest.approx(78.9, abs=0.1)

    def test_returns_none_on_empty(self):
        with patch("fetchers.yf.Ticker") as mock_t:
            mock_t.return_value.history.return_value = pd.DataFrame()
            result = fetch_wti()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.yf.Ticker", side_effect=Exception("error")):
            result = fetch_wti()
        assert result is None


# ── fetch_copper ──────────────────────────────────────────────────

class TestFetchCopper:
    def test_returns_price(self):
        with patch("fetchers.yf.Ticker", _mock_ticker([4.20, 4.25, 4.23])):
            result = fetch_copper()
        assert result == pytest.approx(4.23, abs=0.01)

    def test_returns_none_on_empty(self):
        with patch("fetchers.yf.Ticker") as mock_t:
            mock_t.return_value.history.return_value = pd.DataFrame()
            result = fetch_copper()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.yf.Ticker", side_effect=Exception("error")):
            result = fetch_copper()
        assert result is None
