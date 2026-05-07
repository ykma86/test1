"""Option D 단위 테스트: CNN Fear & Greed Index 알림."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import (
    _build_fg_message,
    check_fg_threshold,
    get_fg_zone,
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


# ── get_fg_zone ───────────────────────────────────────────────────

class TestGetFgZone:
    def test_extreme_fear_at_25(self):
        assert get_fg_zone(25) == "extreme_fear"

    def test_fear_range(self):
        assert get_fg_zone(35) == "fear"

    def test_neutral_range(self):
        assert get_fg_zone(50) == "neutral"

    def test_greed_range(self):
        assert get_fg_zone(60) == "greed"

    def test_extreme_greed_above_75(self):
        assert get_fg_zone(80) == "extreme_greed"

    def test_exactly_75_is_greed(self):
        assert get_fg_zone(75) == "greed"

    def test_none_returns_unknown(self):
        assert get_fg_zone(None) == "unknown"


# ── check_fg_threshold ────────────────────────────────────────────

class TestCheckFgThreshold:
    def test_no_change_same_zone(self):
        msg, zone = check_fg_threshold(20.0, "extreme_fear")
        assert msg is None
        assert zone == "extreme_fear"

    def test_fear_to_extreme_fear_triggers(self):
        msg, zone = check_fg_threshold(20.0, "fear")
        assert msg is not None
        assert zone == "extreme_fear"
        assert "극단적 공포" in msg

    def test_neutral_to_greed_triggers(self):
        msg, zone = check_fg_threshold(60.0, "neutral")
        assert msg is not None
        assert zone == "greed"
        assert "탐욕" in msg

    def test_greed_to_extreme_greed_triggers(self):
        msg, zone = check_fg_threshold(80.0, "greed")
        assert msg is not None
        assert zone == "extreme_greed"
        assert "극단적 탐욕" in msg

    def test_unknown_prev_triggers(self):
        msg, zone = check_fg_threshold(20.0, "unknown")
        assert msg is not None
        assert zone == "extreme_fear"

    def test_none_value_no_trigger(self):
        msg, zone = check_fg_threshold(None, "neutral")
        assert msg is None
        assert zone == "neutral"


# ── _build_fg_message ─────────────────────────────────────────────

class TestBuildFgMessage:
    def test_extreme_fear_message(self):
        msg = _build_fg_message(20.0, "extreme_fear")
        assert "극단적 공포" in msg
        assert "20" in msg
        assert "투자 자문" in msg

    def test_extreme_greed_message(self):
        msg = _build_fg_message(80.0, "extreme_greed")
        assert "극단적 탐욕" in msg
        assert "80" in msg

    def test_neutral_message(self):
        msg = _build_fg_message(50.0, "neutral")
        assert "중립" in msg


# ── fetch_fear_greed ──────────────────────────────────────────────

class TestFetchFearGreed:
    def test_returns_score(self):
        from fetchers import fetch_fear_greed
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"fear_and_greed": {"score": 35.7, "rating": "Fear"}}
        mock_resp.raise_for_status = MagicMock()
        with patch("fetchers.requests.get", return_value=mock_resp):
            result = fetch_fear_greed()
        assert result == pytest.approx(35.7, abs=0.1)

    def test_returns_none_on_missing_key(self):
        from fetchers import fetch_fear_greed
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        with patch("fetchers.requests.get", return_value=mock_resp):
            result = fetch_fear_greed()
        assert result is None

    def test_returns_none_on_exception(self):
        from fetchers import fetch_fear_greed
        with patch("fetchers.requests.get", side_effect=Exception("network error")):
            result = fetch_fear_greed()
        assert result is None


# ── main() 통합: Fear & Greed 알림 발송 ──────────────────────────

class TestMainOptionD:
    def test_fg_alert_fires_on_zone_change(self):
        state = {**_BASE_STATE, "fg_zone": "neutral"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=None), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.fetch_put_call_ratio", return_value=None), \
             patch("main.fetch_fear_greed", return_value=20.0), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_called_once()
        assert "극단적 공포" in mock_send.call_args[0][0]

    def test_no_alert_when_same_zone(self):
        state = {**_BASE_STATE, "fg_zone": "extreme_fear"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=None), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.fetch_put_call_ratio", return_value=None), \
             patch("main.fetch_fear_greed", return_value=20.0), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_not_called()
