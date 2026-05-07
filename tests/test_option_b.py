"""Option B 단위 테스트: ISM PMI 50선 + Fed BS 방향 전환 알림."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import (
    _build_fed_bs_message,
    _build_ism_message,
    check_fed_bs_trend,
    check_ism_threshold,
    get_fed_bs_trend,
    get_ism_level,
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
}


# ── get_ism_level ─────────────────────────────────────────────────

class TestGetIsmLevel:
    def test_above_50(self):
        assert get_ism_level(52.3) == "above"

    def test_below_50(self):
        assert get_ism_level(48.7) == "below"

    def test_exactly_50_is_below(self):
        assert get_ism_level(50.0) == "below"

    def test_none_returns_unknown(self):
        assert get_ism_level(None) == "unknown"


# ── check_ism_threshold ───────────────────────────────────────────

class TestCheckIsmThreshold:
    def test_no_change_same_level(self):
        msg, level = check_ism_threshold(52.0, "above")
        assert msg is None
        assert level == "above"

    def test_above_to_below_triggers(self):
        msg, level = check_ism_threshold(48.5, "above")
        assert msg is not None
        assert level == "below"
        assert "수축" in msg

    def test_below_to_above_triggers(self):
        msg, level = check_ism_threshold(51.2, "below")
        assert msg is not None
        assert level == "above"
        assert "확장" in msg

    def test_unknown_prev_no_trigger(self):
        msg, level = check_ism_threshold(52.0, "unknown")
        assert msg is not None   # unknown → above 는 알림 발생
        assert level == "above"

    def test_none_value_no_trigger(self):
        msg, level = check_ism_threshold(None, "above")
        assert msg is None
        assert level == "above"


# ── _build_ism_message ────────────────────────────────────────────

class TestBuildIsmMessage:
    def test_above_contains_expansion(self):
        msg = _build_ism_message(51.2, "above")
        assert "확장" in msg
        assert "51.2" in msg
        assert "투자 자문" in msg

    def test_below_contains_contraction(self):
        msg = _build_ism_message(48.5, "below")
        assert "수축" in msg
        assert "48.5" in msg


# ── get_fed_bs_trend ──────────────────────────────────────────────

class TestGetFedBsTrend:
    def test_expanding_when_second_half_higher(self):
        # 전반 4주 평균 < 후반 4주 평균
        s = pd.Series([7_000_000.0] * 4 + [7_200_000.0] * 4)
        assert get_fed_bs_trend(s) == "expanding"

    def test_contracting_when_second_half_lower(self):
        s = pd.Series([7_200_000.0] * 4 + [7_000_000.0] * 4)
        assert get_fed_bs_trend(s) == "contracting"

    def test_unknown_when_none(self):
        assert get_fed_bs_trend(None) == "unknown"

    def test_unknown_when_too_short(self):
        assert get_fed_bs_trend(pd.Series([7_000_000.0] * 5)) == "unknown"


# ── check_fed_bs_trend ────────────────────────────────────────────

class TestCheckFedBsTrend:
    def _expanding_series(self):
        return pd.Series([7_000_000.0] * 4 + [7_200_000.0] * 4)

    def _contracting_series(self):
        return pd.Series([7_200_000.0] * 4 + [7_000_000.0] * 4)

    def test_no_change_same_trend(self):
        msg, trend = check_fed_bs_trend(self._expanding_series(), "expanding")
        assert msg is None
        assert trend == "expanding"

    def test_contracting_to_expanding_triggers(self):
        msg, trend = check_fed_bs_trend(self._expanding_series(), "contracting")
        assert msg is not None
        assert trend == "expanding"
        assert "QT→QE" in msg

    def test_expanding_to_contracting_triggers(self):
        msg, trend = check_fed_bs_trend(self._contracting_series(), "expanding")
        assert msg is not None
        assert trend == "contracting"
        assert "QE→QT" in msg

    def test_none_series_no_trigger(self):
        msg, trend = check_fed_bs_trend(None, "expanding")
        assert msg is None
        assert trend == "expanding"


# ── _build_fed_bs_message ─────────────────────────────────────────

class TestBuildFedBsMessage:
    def test_expanding_contains_qt_to_qe(self):
        msg = _build_fed_bs_message(7.2, "expanding")
        assert "QT→QE" in msg
        assert "7.2" in msg
        assert "투자 자문" in msg

    def test_contracting_contains_qe_to_qt(self):
        msg = _build_fed_bs_message(7.0, "contracting")
        assert "QE→QT" in msg


# ── main() 통합: ISM + Fed BS 알림 발송 ──────────────────────────

class TestMainOptionB:
    def test_ism_alert_fires_on_cross(self):
        state = {**_BASE_STATE, "ism_level": "above"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=48.5), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_called_once()
        assert "수축" in mock_send.call_args[0][0]

    def test_fed_bs_alert_fires_on_trend_change(self):
        state = {**_BASE_STATE, "fed_bs_trend": "contracting"}
        expanding = pd.Series([7_000_000.0] * 4 + [7_200_000.0] * 4)
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=None), \
             patch("main.fetch_series", return_value=expanding), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_called_once()
        assert "QT→QE" in mock_send.call_args[0][0]

    def test_no_alert_when_no_change(self):
        state = {**_BASE_STATE, "ism_level": "above", "fed_bs_trend": "contracting"}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.fetch_phase_data", return_value=None), \
             patch("main.fetch_regime_data", return_value=None), \
             patch("main.fetch_ism_pmi", return_value=52.0), \
             patch("main.fetch_series", return_value=None), \
             patch("main.fetch_fred", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="key")
        mock_send.assert_not_called()
