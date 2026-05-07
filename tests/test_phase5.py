"""Phase 5 단위 테스트: 떨어지는 칼날 모드 트리거."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from falling_knife import (
    check_spx_drop, check_vix_spike, check_hy_spread_rise,
    evaluate, build_alert_message, build_clear_message,
)


def s(*values) -> pd.Series:
    return pd.Series(list(values), dtype=float)


# ── S&P500 하락 트리거 ─────────────────────────────────────────

class TestSpxDrop:
    def test_triggered(self):
        # 100 → 92 = -8%
        spy = s(100, 99, 98, 97, 96, 92)
        assert check_spx_drop(spy) is True

    def test_not_triggered(self):
        # 100 → 95 = -5% (임계치 미달)
        spy = s(100, 99, 98, 97, 96, 95)
        assert check_spx_drop(spy) is False

    def test_too_short(self):
        assert check_spx_drop(s(100, 90)) is False


# ── VIX 급등 트리거 ───────────────────────────────────────────

class TestVixSpike:
    def test_triggered(self):
        # 15 → 28 = +87%
        vix = s(15, 16, 18, 21, 25, 28)
        assert check_vix_spike(vix) is True

    def test_not_triggered(self):
        # 15 → 22 = +47% (임계치 미달)
        vix = s(15, 16, 17, 18, 20, 22)
        assert check_vix_spike(vix) is False

    def test_too_short(self):
        assert check_vix_spike(s(10, 20)) is False


# ── HY 스프레드 상승 트리거 ────────────────────────────────────

class TestHySpreadRise:
    def test_triggered(self):
        # 3.0 → 4.2 = +120bp
        hy = s(3.0, 3.2, 3.5, 3.8, 4.0, 4.2)
        assert check_hy_spread_rise(hy) is True

    def test_not_triggered(self):
        # 3.0 → 3.8 = +80bp (임계치 미달)
        hy = s(3.0, 3.2, 3.4, 3.5, 3.7, 3.8)
        assert check_hy_spread_rise(hy) is False

    def test_too_short(self):
        assert check_hy_spread_rise(s(3.0, 5.0)) is False


# ── evaluate (2개 이상 충족) ──────────────────────────────────

class TestEvaluate:
    def _spy_ok(self):
        return s(100, 99, 98, 97, 96, 92)   # -8% ✓

    def _vix_ok(self):
        return s(15, 16, 18, 21, 25, 28)    # +87% ✓

    def _hy_ok(self):
        return s(3.0, 3.2, 3.5, 3.8, 4.0, 4.2)  # +120bp ✓

    def _spy_no(self):
        return s(100, 100, 100, 100, 100, 97)   # -3%

    def _vix_no(self):
        return s(15, 15, 16, 16, 16, 17)   # +13%

    def _hy_no(self):
        return s(3.0, 3.0, 3.0, 3.1, 3.1, 3.2)  # +20bp

    def test_all_three_triggered(self):
        r = evaluate(self._spy_ok(), self._vix_ok(), self._hy_ok())
        assert r["active"] is True
        assert r["spx_drop"] is True
        assert r["vix_spike"] is True
        assert r["hy_spread"] is True

    def test_two_triggered(self):
        r = evaluate(self._spy_ok(), self._vix_ok(), self._hy_no())
        assert r["active"] is True

    def test_one_triggered_not_active(self):
        r = evaluate(self._spy_ok(), self._vix_no(), self._hy_no())
        assert r["active"] is False

    def test_none_triggered(self):
        r = evaluate(self._spy_no(), self._vix_no(), self._hy_no())
        assert r["active"] is False
        assert r["spx_drop"] is False


# ── 메시지 빌더 ───────────────────────────────────────────────

class TestMessages:
    def test_alert_contains_disclaimer(self):
        triggers = {"spx_drop": True, "vix_spike": True, "hy_spread": False, "active": True}
        msg = build_alert_message(triggers, sqqq_score=6)
        assert "고급자용" in msg
        assert "SQQQ" in msg
        assert "6/7" in msg

    def test_clear_contains_disclaimer(self):
        msg = build_clear_message()
        assert "해제" in msg
        assert "고급자용" in msg
