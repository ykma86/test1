"""Phase 10 단위 테스트: Shadow 모드 + 라이브 전환 체크리스트."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from live_checklist import (
    check_alert_ratio,
    check_error_ratio,
    check_run_count,
    check_run_period,
    check_unclear_phase_ratio,
    load_shadow_log,
    run_checklist,
)
from main import append_shadow_log, main

_BASE_STATE = {
    "threshold_level": 0,
    "phase": "불명확",
    "regime": "불명확",
    "momentum_top3": [],
    "momentum_scores": {},
    "falling_knife_active": False,
    "fx_level": "normal",
}


def _make_entries(
    n: int,
    days_span: int = 20,
    alert_ratio: float = 0.2,
    error_ratio: float = 0.0,
    unclear_ratio: float = 0.1,
) -> list[dict]:
    """테스트용 shadow log 항목 생성."""
    base = datetime(2026, 4, 1, 10, 0, tzinfo=timezone(timedelta(hours=9)))
    entries = []
    for i in range(n):
        offset_days = i * days_span / max(n - 1, 1)
        ts = base + timedelta(days=offset_days)
        entries.append({
            "ts":          ts.isoformat(),
            "vix":         18.5,
            "phase":       "불명확" if i < int(n * unclear_ratio) else "2단계",
            "regime":      "골디락스",
            "alert_count": 1 if i < int(n * alert_ratio) else 0,
            "error":       "oops" if i < int(n * error_ratio) else None,
        })
    return entries


# ── load_shadow_log ───────────────────────────────────────────────

class TestLoadShadowLog:
    def test_returns_empty_when_no_file(self, tmp_path):
        with patch("live_checklist.SHADOW_LOG", tmp_path / "nonexistent.jsonl"):
            assert load_shadow_log() == []

    def test_loads_valid_entries(self, tmp_path):
        log_file = tmp_path / "shadow_log.jsonl"
        log_file.write_text(
            '{"ts": "2026-04-01T10:00:00+09:00", "vix": 18.0, "phase": "2단계", "regime": "골디락스", "alert_count": 0, "error": null}\n'
            '{"ts": "2026-04-02T10:00:00+09:00", "vix": 19.0, "phase": "1단계", "regime": "침체", "alert_count": 1, "error": null}\n',
            encoding="utf-8",
        )
        with patch("live_checklist.SHADOW_LOG", log_file):
            entries = load_shadow_log()
        assert len(entries) == 2
        assert entries[0]["phase"] == "2단계"

    def test_skips_invalid_json_lines(self, tmp_path):
        log_file = tmp_path / "shadow_log.jsonl"
        log_file.write_text(
            '{"ts": "2026-04-01T10:00:00+09:00", "alert_count": 0, "error": null}\n'
            'invalid json line\n'
            '{"ts": "2026-04-02T10:00:00+09:00", "alert_count": 1, "error": null}\n',
            encoding="utf-8",
        )
        with patch("live_checklist.SHADOW_LOG", log_file):
            entries = load_shadow_log()
        assert len(entries) == 2


# ── 체크 함수들 ───────────────────────────────────────────────────

class TestCheckRunCount:
    def test_pass_when_enough(self):
        ok, _ = check_run_count(_make_entries(20))
        assert ok is True

    def test_fail_when_too_few(self):
        ok, _ = check_run_count(_make_entries(10))
        assert ok is False

    def test_boundary_14(self):
        ok, _ = check_run_count(_make_entries(14))
        assert ok is True


class TestCheckRunPeriod:
    def test_pass_when_long_enough(self):
        ok, _ = check_run_period(_make_entries(20, days_span=20))
        assert ok is True

    def test_fail_when_too_short(self):
        ok, _ = check_run_period(_make_entries(20, days_span=5))
        assert ok is False

    def test_fail_with_single_entry(self):
        ok, _ = check_run_period(_make_entries(1))
        assert ok is False


class TestCheckAlertRatio:
    def test_pass_when_low(self):
        ok, _ = check_alert_ratio(_make_entries(20, alert_ratio=0.3))
        assert ok is True

    def test_fail_when_high(self):
        ok, _ = check_alert_ratio(_make_entries(20, alert_ratio=0.8))
        assert ok is False

    def test_fail_empty(self):
        ok, _ = check_alert_ratio([])
        assert ok is False


class TestCheckErrorRatio:
    def test_pass_when_no_errors(self):
        ok, _ = check_error_ratio(_make_entries(20, error_ratio=0.0))
        assert ok is True

    def test_fail_when_too_many_errors(self):
        ok, _ = check_error_ratio(_make_entries(20, error_ratio=0.5))
        assert ok is False

    def test_boundary_just_under_10pct(self):
        entries = _make_entries(20, error_ratio=0.0)
        entries[0]["error"] = "err"   # 1/20 = 5%
        ok, _ = check_error_ratio(entries)
        assert ok is True


class TestCheckUnclearPhaseRatio:
    def test_pass_when_low(self):
        ok, _ = check_unclear_phase_ratio(_make_entries(20, unclear_ratio=0.1))
        assert ok is True

    def test_fail_when_high(self):
        ok, _ = check_unclear_phase_ratio(_make_entries(20, unclear_ratio=0.5))
        assert ok is False


# ── run_checklist ─────────────────────────────────────────────────

class TestRunChecklist:
    def test_no_go_when_no_log(self, capsys):
        with patch("live_checklist.load_shadow_log", return_value=[]):
            result = run_checklist()
        assert result is False
        assert "shadow_log" in capsys.readouterr().out

    def test_go_when_all_pass(self, capsys):
        good_entries = _make_entries(20, days_span=20, alert_ratio=0.2,
                                     error_ratio=0.0, unclear_ratio=0.1)
        with patch("live_checklist.load_shadow_log", return_value=good_entries), \
             patch("live_checklist.check_tests", return_value=(True, "단위 테스트: 156 passed")):
            result = run_checklist()
        assert result is True
        assert "GO" in capsys.readouterr().out

    def test_no_go_when_one_fails(self, capsys):
        bad_entries = _make_entries(5)  # run_count < 14
        with patch("live_checklist.load_shadow_log", return_value=bad_entries), \
             patch("live_checklist.check_tests", return_value=(True, "156 passed")):
            result = run_checklist()
        assert result is False
        assert "NO-GO" in capsys.readouterr().out


# ── append_shadow_log + shadow mode in main() ────────────────────

class TestAppendShadowLog:
    def test_creates_file_and_appends(self, tmp_path):
        log_file = tmp_path / "state" / "shadow_log.jsonl"
        with patch("main.SHADOW_LOG", log_file):
            append_shadow_log({"ts": "2026-01-01", "vix": 18.0, "alert_count": 0, "error": None})
            append_shadow_log({"ts": "2026-01-02", "vix": 19.0, "alert_count": 1, "error": None})
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_entry_is_valid_json(self, tmp_path):
        log_file = tmp_path / "state" / "shadow_log.jsonl"
        with patch("main.SHADOW_LOG", log_file):
            append_shadow_log({"ts": "2026-01-01", "phase": "2단계", "error": None})
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["phase"] == "2단계"


class TestMainShadowMode:
    def test_shadow_logs_and_saves_state(self, tmp_path):
        log_file = tmp_path / "state" / "shadow_log.jsonl"
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram") as mock_send, \
             patch("main.save_state") as mock_save, \
             patch("main._is_quiet_hours", return_value=False), \
             patch("main.SHADOW_LOG", log_file):
            main(shadow=True, token="t", chat_id="c", fred_api_key="")
        mock_send.assert_not_called()
        mock_save.assert_called_once()

    def test_shadow_runs_even_with_no_change(self, tmp_path):
        log_file = tmp_path / "state" / "shadow_log.jsonl"
        with patch("main.fetch_vix", return_value=18.0), \
             patch("main.load_state", return_value=dict(_BASE_STATE)), \
             patch("main.scan_all", return_value=[]), \
             patch("main.fk_fetch", return_value=None), \
             patch("main.send_telegram"), \
             patch("main.save_state"), \
             patch("main._is_quiet_hours", return_value=False), \
             patch("main.SHADOW_LOG", log_file):
            main(shadow=True, token="t", chat_id="c", fred_api_key="")
        assert log_file.exists()
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert "ts" in entry
        assert "vix" in entry
