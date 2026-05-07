"""Phase 1 단위 테스트: 12개 지표 fetch + thresholds.yaml."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from fetchers import fetch_all, fetch_cpi_yoy, fetch_fred, fetch_move


class TestFetchFred:
    def test_returns_latest_float(self):
        mock_fred = MagicMock()
        mock_fred.get_series.return_value = pd.Series([1.0, 2.0, 3.0])
        with patch("fetchers.Fred", return_value=mock_fred):
            assert fetch_fred("T10Y2Y", "key") == 3.0

    def test_returns_none_on_empty(self):
        mock_fred = MagicMock()
        mock_fred.get_series.return_value = pd.Series([], dtype=float)
        with patch("fetchers.Fred", return_value=mock_fred):
            assert fetch_fred("T10Y2Y", "key") is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("network error")):
            assert fetch_fred("T10Y2Y", "key") is None


class TestFetchCpiYoy:
    def test_calculates_yoy_correctly(self):
        mock_fred = MagicMock()
        mock_fred.get_series.return_value = pd.Series([100.0] * 12 + [103.0])
        with patch("fetchers.Fred", return_value=mock_fred):
            result = fetch_cpi_yoy("key")
        assert result == pytest.approx(3.0, abs=0.01)

    def test_returns_none_on_insufficient_data(self):
        mock_fred = MagicMock()
        mock_fred.get_series.return_value = pd.Series([1.0] * 5)
        with patch("fetchers.Fred", return_value=mock_fred):
            assert fetch_cpi_yoy("key") is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.Fred", side_effect=Exception("fail")):
            assert fetch_cpi_yoy("key") is None


class TestFetchMove:
    def test_returns_float(self):
        df = pd.DataFrame({"Close": [120.5]})
        with patch("fetchers.yf.Ticker") as mock:
            mock.return_value.history.return_value = df
            assert fetch_move() == 120.5

    def test_returns_none_on_empty(self):
        with patch("fetchers.yf.Ticker") as mock:
            mock.return_value.history.return_value = pd.DataFrame()
            assert fetch_move() is None

    def test_returns_none_on_exception(self):
        with patch("fetchers.yf.Ticker", side_effect=Exception("fail")):
            assert fetch_move() is None


class TestFetchAll:
    _ext_patches = dict(
        fetch_ism_pmi=52.0, fetch_nfp_change=250.0, fetch_fed_balance=7.2,
        fetch_m2_yoy=3.1,   fetch_wti=78.5,         fetch_copper=4.2,
    )

    def test_returns_18_indicators(self):
        with patch("fetchers.fetch_fred", return_value=1.0), \
             patch("fetchers.fetch_cpi_yoy", return_value=3.0), \
             patch("fetchers.fetch_move", return_value=120.0), \
             patch("fetchers.fetch_ism_pmi", return_value=52.0), \
             patch("fetchers.fetch_nfp_change", return_value=250.0), \
             patch("fetchers.fetch_fed_balance", return_value=7.2), \
             patch("fetchers.fetch_m2_yoy", return_value=3.1), \
             patch("fetchers.fetch_wti", return_value=78.5), \
             patch("fetchers.fetch_copper", return_value=4.2):
            result = fetch_all("key")
        assert len(result) == 18

    def test_all_none_on_full_failure(self):
        with patch("fetchers.fetch_fred", return_value=None), \
             patch("fetchers.fetch_cpi_yoy", return_value=None), \
             patch("fetchers.fetch_move", return_value=None), \
             patch("fetchers.fetch_ism_pmi", return_value=None), \
             patch("fetchers.fetch_nfp_change", return_value=None), \
             patch("fetchers.fetch_fed_balance", return_value=None), \
             patch("fetchers.fetch_m2_yoy", return_value=None), \
             patch("fetchers.fetch_wti", return_value=None), \
             patch("fetchers.fetch_copper", return_value=None):
            result = fetch_all("key")
        assert all(v is None for v in result.values())

    def test_expected_keys_present(self):
        with patch("fetchers.fetch_fred", return_value=1.0), \
             patch("fetchers.fetch_cpi_yoy", return_value=3.0), \
             patch("fetchers.fetch_move", return_value=120.0):
            result = fetch_all("key")
        for key in ["cli", "anfci", "nfci", "vix_fred", "hy_spread",
                    "t10y2y", "t10y3m", "dxy", "usdkrw", "bei_5y",
                    "cpi_yoy", "move"]:
            assert key in result


class TestThresholdsYaml:
    def test_vix_thresholds(self):
        config = yaml.safe_load(Path("config/thresholds.yaml").read_text())
        assert config["vix"]["warn"] == 20
        assert config["vix"]["reduce"] == 25
        assert config["vix"]["exit"] == 30

    def test_usdkrw_thresholds(self):
        config = yaml.safe_load(Path("config/thresholds.yaml").read_text())
        assert config["usdkrw"]["high"] == 1450
        assert config["usdkrw"]["low"] == 1250

    def test_falling_knife_mode_enabled(self):
        config = yaml.safe_load(Path("config/thresholds.yaml").read_text())
        assert config["falling_knife_mode"] is True
