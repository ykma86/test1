"""Phase 5: 떨어지는 칼날 모드 — SQQQ 단기 추천."""
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

KNIFE_DISCLAIMER = "\n⚠️ 떨어지는 칼날 트레이딩은 고급자용. 룰 엄수 필수, 시드 일부로만."
SAFETY_RULES = "비중 최대 20% / 손절 -10% / 익절 +20% 절반·+30% 전량 / 보유 최대 2주"


def check_spx_drop(spy: pd.Series) -> bool:
    """S&P500 5일 수익률 -7% 이하."""
    if len(spy) < 6:
        return False
    return bool(spy.iloc[-1] / spy.iloc[-6] - 1 <= -0.07)


def check_vix_spike(vix: pd.Series) -> bool:
    """VIX 5일 변화율 +80% 이상."""
    if len(vix) < 6 or vix.iloc[-6] == 0:
        return False
    return bool(vix.iloc[-1] / vix.iloc[-6] - 1 >= 0.80)


def check_hy_spread_rise(hy: pd.Series) -> bool:
    """HY 스프레드 5일(1주) +100bp(+1.0%p) 이상 상승."""
    if len(hy) < 6:
        return False
    return bool(hy.iloc[-1] - hy.iloc[-6] >= 1.0)


def evaluate(spy: pd.Series, vix: pd.Series, hy: pd.Series) -> dict:
    """트리거 3개 평가. 2개 이상 충족 시 active=True."""
    t = {
        "spx_drop":  check_spx_drop(spy),
        "vix_spike": check_vix_spike(vix),
        "hy_spread": check_hy_spread_rise(hy),
    }
    t["active"] = sum(v for k, v in t.items() if k != "active") >= 2
    return t


def fetch_data() -> Optional[tuple[pd.Series, pd.Series]]:
    """SPY, VIX 10일 시계열 fetch. 실패 시 None."""
    try:
        spy = yf.Ticker("SPY").history(period="10d")["Close"].dropna()
        vix = yf.Ticker("^VIX").history(period="10d")["Close"].dropna()
        if len(spy) < 6 or len(vix) < 6:
            logger.warning("떨어지는 칼날 데이터 부족")
            return None
        return spy, vix
    except Exception as e:
        logger.warning(f"떨어지는 칼날 fetch 실패: {e}")
        return None


def build_alert_message(triggers: dict, sqqq_score: int) -> str:
    """SQQQ 단기 진입 알림 메시지."""
    fired = [k for k, v in triggers.items() if k != "active" and v]
    trigger_str = " / ".join({
        "spx_drop":  "S&P500 -7%↓",
        "vix_spike": "VIX +80%↑",
        "hy_spread": "HY +100bp↑",
    }.get(k, k) for k in fired)
    return (
        f"🔪 떨어지는 칼날 모드 진입\n"
        f"트리거: {trigger_str}\n"
        f"SQQQ 모멘텀: {sqqq_score}/7점\n"
        f"━━━━━━━━━━━━\n"
        f"{SAFETY_RULES}"
        f"{KNIFE_DISCLAIMER}"
    )


def build_clear_message() -> str:
    """트리거 해제 알림 메시지."""
    return f"✅ 떨어지는 칼날 모드 해제 — 트리거 조건 소멸{KNIFE_DISCLAIMER}"
