"""Phase 0 MVP 단위 테스트."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import build_message, fetch_vix, get_threshold_level, load_state, main, save_state


class TestGetThresholdLevel:
    def test_below_20(self):
        assert get_threshold_level(15.0) == 0

    def test_at_20(self):
        assert get_threshold_level(20.0) == 20

    def test_between_20_and_25(self):
        assert get_threshold_level(22.5) == 20

    def test_at_25(self):
        assert get_threshold_level(25.0) == 25

    def test_between_25_and_30(self):
        assert get_threshold_level(27.0) == 25

    def test_at_30(self):
        assert get_threshold_level(30.0) == 30

    def test_above_30(self):
        assert get_threshold_level(45.0) == 30


class TestFetchVix:
    @patch("main.yf.Ticker")
    def test_fetch_returns_float(self, mock_ticker):
        df = pd.DataFrame({"Close": [18.5]})
        mock_ticker.return_value.history.return_value = df
        assert fetch_vix() == 18.5

    @patch("main.yf.Ticker")
    def test_fetch_raises_on_empty_data(self, mock_ticker):
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        with pytest.raises(ValueError):
            fetch_vix()


class TestStateManagement:
    def test_load_state_returns_default_when_no_file(self, tmp_path):
        with patch("main.STATE_FILE", tmp_path / "nonexistent.json"):
            state = load_state()
        assert state["threshold_level"] == 0
        assert state["last_vix"] is None

    def test_save_and_load_roundtrip(self, tmp_path):
        state_file = tmp_path / "state" / "previous_state.json"
        with patch("main.STATE_FILE", state_file):
            save_state({"threshold_level": 20, "last_vix": 22.5, "last_updated": "2026-01-01"})
            loaded = load_state()
        assert loaded["threshold_level"] == 20
        assert loaded["last_vix"] == 22.5


class TestDuplicateAlertPrevention:
    _base_state = {"threshold_level": 20, "last_vix": 21.0, "last_updated": None,
                   "phase": "불명확", "regime": "불명확", "momentum_top3": [], "momentum_scores": {}}

    @patch("main.scan_all", return_value=[])
    @patch("main.fetch_vix", return_value=22.0)
    @patch("main.load_state", return_value=_base_state)
    @patch("main.send_telegram")
    @patch("main.save_state")
    def test_no_alert_when_level_unchanged(self, mock_save, mock_send, mock_load, mock_fetch, mock_scan):
        main(token="tok", chat_id="123")
        mock_send.assert_not_called()
        mock_save.assert_not_called()

    @patch("main.scan_all", return_value=[])
    @patch("main.fetch_vix", return_value=26.0)
    @patch("main.load_state", return_value=_base_state)
    @patch("main.send_telegram")
    @patch("main.save_state")
    @patch("main._is_quiet_hours", return_value=False)
    def test_alert_fires_on_level_change(self, mock_quiet, mock_save, mock_send, mock_load, mock_fetch, mock_scan):
        main(token="tok", chat_id="123")
        mock_send.assert_called_once()
        mock_save.assert_called_once()


class TestDryRun:
    @patch("main.scan_all", return_value=[])
    @patch("main.fetch_vix", return_value=26.0)
    @patch("main.load_state", return_value={"threshold_level": 0, "last_vix": None, "last_updated": None,
                                             "phase": "불명확", "regime": "불명확",
                                             "momentum_top3": [], "momentum_scores": {}})
    @patch("main.send_telegram")
    @patch("main.save_state")
    def test_dry_run_skips_send_and_save(self, mock_save, mock_send, mock_load, mock_fetch, mock_scan):
        main(dry_run=True)
        mock_send.assert_not_called()
        mock_save.assert_not_called()


class TestBuildMessage:
    def test_upward_cross_contains_direction(self):
        msg = build_message(26.0, 25, 20)
        assert "↑" in msg
        assert "VIX 25" in msg

    def test_downward_cross_contains_direction(self):
        msg = build_message(18.0, 0, 20)
        assert "↓" in msg

    def test_disclaimer_always_included(self):
        msg = build_message(22.0, 20, 0)
        assert "투자 자문이 아닙니다" in msg
