"""Phase 1: 12개 거시경제 지표 fetch."""
import logging
from typing import Optional

import yfinance as yf
import pandas as pd
from fredapi import Fred

logger = logging.getLogger(__name__)

FRED_SERIES: dict[str, str] = {
    "cli":       "OECDLOLITOAASTSAM",
    "anfci":     "ANFCI",
    "nfci":      "NFCI",
    "vix_fred":  "VIXCLS",
    "hy_spread": "BAMLH0A0HYM2",
    "t10y2y":    "T10Y2Y",
    "t10y3m":    "T10Y3M",
    "dxy":       "DTWEXBGS",
    "usdkrw":    "DEXKOUS",
    "bei_5y":    "T5YIE",
}


def fetch_fred(series_id: str, api_key: str) -> Optional[float]:
    """FRED 시리즈 최신값 조회. 실패 시 None 반환."""
    try:
        data = Fred(api_key=api_key).get_series(series_id).dropna()
        if data.empty:
            logger.warning(f"FRED {series_id}: 빈 데이터")
            return None
        return float(data.iloc[-1])
    except Exception as e:
        logger.warning(f"FRED {series_id} fetch 실패: {e}")
        return None


def fetch_cpi_yoy(api_key: str) -> Optional[float]:
    """CPI YoY % (CPIAUCSL 12개월 변화율)."""
    try:
        data = Fred(api_key=api_key).get_series("CPIAUCSL").dropna()
        if len(data) < 13:
            logger.warning("CPI 데이터 부족 (13개월 미만)")
            return None
        return round(float(data.iloc[-1] / data.iloc[-13] - 1) * 100, 2)
    except Exception as e:
        logger.warning(f"CPI YoY fetch 실패: {e}")
        return None


def fetch_move() -> Optional[float]:
    """Yahoo Finance에서 MOVE 지수 조회."""
    try:
        data = yf.Ticker("^MOVE").history(period="5d")
        if data.empty:
            logger.warning("MOVE: 빈 데이터")
            return None
        return float(data["Close"].dropna().iloc[-1])
    except Exception as e:
        logger.warning(f"MOVE fetch 실패: {e}")
        return None


def fetch_all(api_key: str) -> dict[str, Optional[float]]:
    """12개 지표 전체 fetch. 실패 지표는 None."""
    results: dict[str, Optional[float]] = {}

    for name, series_id in FRED_SERIES.items():
        results[name] = fetch_fred(series_id, api_key)

    results["cpi_yoy"] = fetch_cpi_yoy(api_key)
    results["move"] = fetch_move()

    failed = [k for k, v in results.items() if v is None]
    if failed:
        logger.warning(f"fetch 실패 지표: {failed}")
    else:
        logger.info("12개 지표 전체 fetch 완료")

    return results