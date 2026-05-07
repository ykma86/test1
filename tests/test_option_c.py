"""Option C 단위 테스트: Put/Call Ratio 알림."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import (
    _build_pc_message,
    check_pc_threshold,
    get_pc_level,
    main,
)

_BASE_STATE = {
    "threshold_level": 0,
    "phase": "불명확",
    "regime": "불명확",
    "momentum_top3": [],
    "momentum_scores": {},
    "falling_knife_active": False,
    "fx_level": "normal",
    "ism_level": "unknown",
    "fed_bs_trend": "unknown",
    "pc_level": "unknown",
    "fg_zone": "unknown",
}


# ── get_pc_level ──────────────────────────────────────────────────

class TestGetPcLevel:
    def test_above_1_is_put_dominant(self):
        assert get_pc_level(1.1) == "put_dominant"

    def test_exactly_1_is_neutral(self):
        assert get_pc_level(1.0) == "neutral"

    def test_below_07_is_call_dominant(self):
        assert get_pc_level(0.65) == "call_dominant"

    def test_exactly_07_is_neutral(self):
        assert get_pc_level(0.7) == "neutral"

    def test_in_range_is_neutral(self):
        assert get_pc_level(0.85) == "neutral"

    def test_none_returns_unknown(self):
        assert get_pc_level(None) == "unknown"


# ── check_pc_threshold ────────────────────────────────────────────

class TestCheckPcThreshold:
    def test_no_change_same_level(self):
        msg, level = check_pc_threshold(1.2, "put_dominant")
        assert msg is None
        assert level == "put_dominant"

    def test_neutral_to_put_dominant_triggers(self):
        msg, level = check_pc_threshold(1.1, "neutral")
        assert msg is not None
        assert level == "put_dominant"
        assert "풋" in msg

    def test_neutral_to_call_dominant_triggers(self):
        msg, level = check_pc_threshold(0.65, "neutral")
        assert msg is not None
        assert level == "call_dominant"
        assert "콜" in msg

    def test_put_dominant_to_neutral_triggers(self):
        msg, level = check_pc_threshold(0.85, "put_dominant")
        assert msg is not None
        assert level == "neutral"
        assert "중립" in msg or "복귀" in msg

    def test_unknown_prev_triggers(self):
        msg, level = check_pc_threshold(1.2, "unknown")
        assert msg is not None
        assert level == "put_dominant"

    def test_none_value_no_trigger(self):
        msg, level = check_pc_threshold(None, "neutral")
        assert msg is None
        assert level == "neutral"


# ── _build_pc_message ─────────────────────────────────────────────

class TestBuildPcMessage:
    def test_put_dominant_contains_put(self):
        msg = _build_pc_message(1.15, "put_dominant")
        assert "풋" in msg
        assert "1.15" in msg
        assert "투자 자문" in msg

    def test_call_dominant_contains_call(self):
        msg = _build_pc_message(0.65, "call_dominant")
        assert "콜" in msg
        assert "0.65" in msg

    def test_neutral_message(self):
        msg = _build_pc_message(0.85, "neutral")
        assert "중립" in msg or "복귀" in msg


# ── fetch_put_call_ratio ──────────────────────────────────────────

class TestFetchPutCallRatio:
    def test_returns_latest_value(self):
        from fetchers import fetch_put_call_ratio
        csv_text = '"DATE","PC RATIO"\n01/01/2024,0.75\n01/02/2024,1.15\n'
        mock_resp = MagicMock()
        mock_resp.text = csv_text
        mock_resp.raise_for_status = MagicMock()
        with patch("fetchers.requests.get", return_value=mock_resp):
            result = fetch_put_call_ratio()
        assert result == pytest.approx(1.15, abs=0.01)

    def test_returns_none_on_empty_csv(self):
        from fetchers import fetch_put_call_ratio
        mock_resp = MagicMock()
        mock_resp.text = '"DATE","PC RATIO"\n'
        mock_resp.raise_for_status = MagicMock()
        with patch("fetchers.requests.get", return_value=mock_resp):
            result = fetch_put_call_ratio()
        assert result is None

    def test_returns_none_on_exception(self):
        from fetchers import fetch_put_call_ratio
        with patch("fetchers.requests.get", side_effect=Exception("network error")):
            result = fetch_put_call_ratio()
        assert result is None


# ── main() 통합: P/C Ratio 알림 발송 ─────────────────────────────

class TestMainOptionC:
    def test_pc_alert_fires_on_cross(self):
        state = {**_BASE_STATE, "pc_level": "neutral"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=None), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.fetch_put_call_ratio", return_value=1.15), \
             patch("main.fetch_fear_greed", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_called_once()
        assert "풋" in mock_send.call_args[0][0]

    def test_no_alert_when_same_level(self):
        state = {**_BASE_STATE, "pc_level": "put_dominant"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=None), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.fetch_put_call_ratio", return_value=1.05), \
             patch("main.fetch_fear_greed", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_not_called()
