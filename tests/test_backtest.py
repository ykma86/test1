"""Phase 7 단위 테스트: 백테스트 엔진."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest import run_scenario, run_backtest, print_report, SCENARIOS


def _phase_inputs_2단계() -> tuple:
    """classify_phase → '2단계' 를 반환하는 픽스처."""
    cli   = pd.Series([99.0, 100.0, 101.0, 102.0, 103.0, 104.0])   # >100, rising
    anfci = pd.Series([-0.5] * 8)                                    # negative
    vix   = pd.Series([15.0] * 40)                                   # <20
    move  = pd.Series([90.0] * 20)                                   # stable
    return cli, anfci, vix, move


def _phase_inputs_회피() -> tuple:
    """classify_phase → '회피' 를 반환하는 픽스처."""
    cli   = pd.Series([104.0, 103.0, 102.0, 101.0, 100.0, 99.0])    # declining
    anfci = pd.Series([-0.5, -0.4, -0.2, 0.0, 0.3, 0.5, 0.5, 0.5]) # 음→양 전환
    vix   = pd.Series([35.0] * 40)                                   # >30
    move  = pd.Series([120.0] * 20)
    return cli, anfci, vix, move


def _regime_inputs_골디락스() -> tuple:
    """classify_regime → '골디락스' 를 반환하는 픽스처."""
    cli = pd.Series([99.0, 100.0, 101.0, 102.0, 103.0, 104.0])  # rising
    bei = pd.Series([3.0, 2.8, 2.6, 2.4, 2.3, 2.2, 2.1])        # 6개월 하락 → inflation_up=False
    return cli, bei


def _regime_inputs_스태그() -> tuple:
    """classify_regime → '스태그플레이션' 을 반환하는 픽스처."""
    cli = pd.Series([104.0, 103.0, 102.0, 101.0, 100.0, 99.0])   # declining
    bei = pd.Series([2.0, 2.1, 2.3, 2.5, 2.7, 2.9, 3.1])        # 6개월 상승 → inflation_up=True
    return cli, bei


# ── run_scenario ──────────────────────────────────────────────────────

class TestRunScenario:
    def test_returns_required_keys(self):
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_2단계()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            r = run_scenario(SCENARIOS[0], "fake_key")
        for key in ("date", "event", "expected_phase", "expected_regime",
                    "actual_phase", "actual_regime", "phase_ok", "regime_ok"):
            assert key in r

    def test_phase_ok_true_when_match(self):
        # SCENARIOS[0]: expected phase="회피"
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_회피()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            r = run_scenario(SCENARIOS[0], "fake_key")
        assert r["phase_ok"] is True
        assert r["actual_phase"] == "회피"

    def test_regime_ok_true_when_match(self):
        # SCENARIOS[4]: expected regime="스태그플레이션"
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_회피()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_스태그()):
            r = run_scenario(SCENARIOS[4], "fake_key")
        assert r["regime_ok"] is True
        assert r["actual_regime"] == "스태그플레이션"

    def test_phase_ok_false_when_mismatch(self):
        # SCENARIOS[0]: expected phase="회피", actual="2단계"
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_2단계()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            r = run_scenario(SCENARIOS[0], "fake_key")
        assert r["phase_ok"] is False

    def test_fetch_failure_gives_unclear(self):
        with patch("backtest._fetch_phase_inputs", return_value=None), \
             patch("backtest._fetch_regime_inputs", return_value=None):
            r = run_scenario(SCENARIOS[0], "fake_key")
        assert r["actual_phase"]  == "불명확"
        assert r["actual_regime"] == "불명확"
        assert r["phase_ok"]  is False
        assert r["regime_ok"] is False

    def test_partial_failure_phase_only(self):
        with patch("backtest._fetch_phase_inputs", return_value=None), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            r = run_scenario(SCENARIOS[5], "fake_key")   # expected regime="골디락스"
        assert r["actual_phase"]  == "불명확"
        assert r["regime_ok"] is True


# ── run_backtest ──────────────────────────────────────────────────────

class TestRunBacktest:
    def test_returns_six_results(self):
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_2단계()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            results = run_backtest("fake_key")
        assert len(results) == 6

    def test_all_results_have_bool_flags(self):
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_2단계()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            results = run_backtest("fake_key")
        for r in results:
            assert isinstance(r["phase_ok"],  bool)
            assert isinstance(r["regime_ok"], bool)

    def test_scenario_dates_preserved(self):
        with patch("backtest._fetch_phase_inputs", return_value=_phase_inputs_2단계()), \
             patch("backtest._fetch_regime_inputs", return_value=_regime_inputs_골디락스()):
            results = run_backtest("fake_key")
        dates = [r["date"] for r in results]
        assert "2022-09-30" in dates
        assert "2020-04-30" in dates


# ── print_report ──────────────────────────────────────────────────────

class TestPrintReport:
    def _make_results(self, phase_ok: bool, regime_ok: bool, n: int = 6) -> list[dict]:
        return [
            {
                "date":            "2022-09-30",
                "event":           "테스트",
                "expected_phase":  "회피",
                "actual_phase":    "회피" if phase_ok else "2단계",
                "expected_regime": "스태그플레이션",
                "actual_regime":   "스태그플레이션" if regime_ok else "침체",
                "phase_ok":        phase_ok,
                "regime_ok":       regime_ok,
            }
            for _ in range(n)
        ]

    def test_pass_when_all_correct(self, capsys):
        print_report(self._make_results(True, True))
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_fail_when_below_threshold(self, capsys):
        print_report(self._make_results(False, False))
        out = capsys.readouterr().out
        assert "FAIL" in out

    def test_output_contains_header(self, capsys):
        print_report(self._make_results(True, True))
        out = capsys.readouterr().out
        assert "백테스트 결과" in out
        assert "Phase" in out
        assert "Regime" in out
