"""Phase 3: 성장/인플레이션 4분면 체제 분류."""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

REGIME_EMOJI = {"골디락스": "🟢", "리플레이션": "🟡", "침체": "🟠", "스태그플레이션": "🔴"}

REGIME_POSITION = {
    "골디락스":    "레버리지 ETF 풀 비중",
    "리플레이션":  "레버리지 ETF 중립 (원자재 우위)",
    "침체":        "레버리지 ETF 축소",
    "스태그플레이션": "레버리지 ETF 청산 검토",
}


def _growth_rising(cli: pd.Series) -> bool:
    """CLI 3개월 모멘텀 양수."""
    if len(cli) < 4:
        return False
    return bool(cli.iloc[-1] > cli.iloc[-4])


def _inflation_rising(bei: pd.Series) -> bool:
    """BEI 5y 6개월 모멘텀 양수 (단기 잡음 제거)."""
    if len(bei) < 7:
        return False
    return bool(bei.iloc[-1] > bei.iloc[-7])


def classify_regime(cli: pd.Series, bei: pd.Series) -> str:
    """4분면 체제 분류: 골디락스/리플레이션/침체/스태그플레이션."""
    growth_up = _growth_rising(cli)
    inflation_up = _inflation_rising(bei)
    logger.debug(f"체제 — 성장↑:{growth_up} 인플↑:{inflation_up}")
    if growth_up and not inflation_up:
        return "골디락스"
    if growth_up and inflation_up:
        return "리플레이션"
    if not growth_up and inflation_up:
        return "스태그플레이션"
    return "침체"


def get_position_guide(regime: str) -> str:
    """체제별 레버리지 ETF 포지션 가이드."""
    return REGIME_POSITION.get(regime, "판단 불가")
