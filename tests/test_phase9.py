"""Phase 9 단위 테스트: 스마트 데일리."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import (
    _build_fx_message,
    _is_quiet_hours,
    build_bundle_message,
    build_daily_summary,
    check_fx_threshold,
    get_fx_level,
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
}


# ── get_fx_level ──────────────────────────────────────────────────

class TestGetFxLevel:
    def test_high(self):
        assert get_fx_level(1460) == "high"

    def test_low(self):
        assert get_fx_level(1240) == "low"

    def test_normal(self):
        assert get_fx_level(1380) == "normal"

    def test_none_returns_unknown(self):
        assert get_fx_level(None) == "unknown"

    def test_boundary_high(self):
        assert get_fx_level(1450) == "high"

    def test_boundary_low(self):
        assert get_fx_level(1250) == "low"


# ── check_fx_threshold ────────────────────────────────────────────

class TestCheckFxThreshold:
    def test_no_change_same_level(self):
        msg, level = check_fx_threshold(1460, "high")
        assert msg is None
        assert level == "high"

    def test_normal_to_high(self):
        msg, level = check_fx_threshold(1460, "normal")
        assert msg is not None
        assert level == "high"
        assert "1,450" in msg

    def test_normal_to_low(self):
        msg, level = check_fx_threshold(1240, "normal")
        assert msg is not None
        assert level == "low"
        assert "1,250" in msg

    def test_high_to_normal_recovery(self):
        msg, level = check_fx_threshold(1380, "high")
        assert msg is not None
        assert level == "normal"

    def test_unknown_no_change(self):
        msg, level = check_fx_threshold(None, "normal")
        assert msg is None
        assert level == "normal"


# ── _build_fx_message ─────────────────────────────────────────────

class TestBuildFxMessage:
    def test_high_contains_warning(self):
        msg = _build_fx_message(1460, "high")
        assert "1,450 돌파" in msg
        assert "축소" in msg
        assert "투자 자문" in msg

    def test_low_contains_opportunity(self):
        msg = _build_fx_message(1240, "low")
        assert "1,250 하향" in msg
        assert "유리" in msg

    def test_normal_recovery(self):
        msg = _build_fx_message(1380, "normal")
        assert "복귀" in msg


# ── build_daily_summary ───────────────────────────────────────────

class TestBuildDailySummary:
    def test_contains_required_fields(self):
        results = [{"ticker": "TQQQ", "score": 6}]
        msg = build_daily_summary(18.5, "2단계", "골디락스", 1380.0, results)
        assert "2단계" in msg
        assert "골디락스" in msg
        assert "18.5" in msg
        assert "1,380" in msg
        assert "TQQQ" in msg

    def test_no_fx_shows_na(self):
        msg = build_daily_summary(20.0, "1단계", "침체", None, [])
        assert "N/A" in msg

    def test_no_momentum_shows_empty(self):
        msg = build_daily_summary(20.0, "1단계", "침체", None, [])
        assert "없음" in msg

    def test_contains_disclaimer(self):
        msg = build_daily_summary(18.5, "2단계", "골디락스", 1380.0, [])
        assert "투자 자문" in msg


# ── build_bundle_message ──────────────────────────────────────────

class TestBuildBundleMessage:
    def test_shows_count(self):
        msg = build_bundle_message(["알림1", "알림2", "알림3"])
        assert "3개" in msg

    def test_contains_all_alerts(self):
        msg = build_bundle_message(["알림A", "알림B"])
        assert "알림A" in msg
        assert "알림B" in msg


# ── _is_quiet_hours ───────────────────────────────────────────────

class TestIsQuietHours:
    def test_inside_quiet(self):
        dt = datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(0, 7, _now=dt) is True

    def test_outside_quiet(self):
        dt = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(0, 7, _now=dt) is False

    def test_boundary_start_included(self):
        dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(0, 7, _now=dt) is True

    def test_boundary_end_excluded(self):
        dt = datetime(2024, 1, 1, 7, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(0, 7, _now=dt) is False


# ── main() 통합: quiet hours + 번들링 + daily ────────────────────

class TestMainQuietHours:
    def test_non_urgent_not_sent_during_quiet(self):
        with patch("main.fetch_vix", return_value=22.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=True):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="")
        mock_send.assert_not_called()

    def test_non_urgent_state_saved_during_quiet(self):
        with patch("main.fetch_vix", return_value=22.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram"), \
             patch("main.save_state") as mock_save, \
             patch("main._is_quiet_hours", return_value=True):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="")
        mock_save.assert_called_once()

    def test_urgent_sends_even_in_quiet_hours(self):
        with patch("main.fetch_vix", return_value=31.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=True):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="")
        mock_send.assert_called_once()


class TestMainBundling:
    def test_multiple_alerts_bundled_into_one_call(self):
        state = {**_BASE_STATE, "threshold_level": 20, "momentum_top3": ["X", "Y", "Z"]}
        results = [{"ticker": "A", "score": 6}, {"ticker": "B", "score": 5}, {"ticker": "C", "score": 4}]
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=results), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="")
        mock_send.assert_called_once()
        assert "매크로 알림" in mock_send.call_args[0][0]

    def test_single_alert_not_wrapped_in_bundle(self):
        state = {**_BASE_STATE, "threshold_level": 20}
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=state), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="")
        mock_send.assert_called_once()
        assert "매크로 알림" not in mock_send.call_args[0][0]


class TestMainDaily:
    def test_daily_sends_even_with_no_change(self):
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[{"ticker": "TQQQ", "score": 6}]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="", daily=True)
        mock_send.assert_called_once()
        assert "일일 요약" in mock_send.call_args[0][0]

    def test_daily_suppressed_during_quiet_hours(self):
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=True):
            main(dry_run=False, token="t", chat_id="c", fred_api_key="", daily=True)
        mock_send.assert_not_called()
