"""Phase 1: 12개 거시경제 지표 fetch."""
import logging
import time
from typing import Optional

import requests
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


def fetch_series(
    series_id: str,
    api_key: str,
    end_date: Optional[str] = None,
    n_periods: int = 20,
) -> Optional[pd.Series]:
    """FRED 시리즈 최근 n_periods개 반환. end_date 지정 시 해당 날짜 기준. 500 오류 시 1회 재시도."""
    kwargs: dict = {}
    if end_date:
        kwargs["observation_end"] = end_date
    for attempt in range(2):
        try:
            data = Fred(api_key=api_key).get_series(series_id, **kwargs).dropna()
            if data.empty:
                logger.warning(f"FRED {series_id}: 빈 데이터")
                return None
            return data.iloc[-n_periods:]
        except Exception as e:
            if "Internal Server Error" in str(e) and attempt == 0:
                time.sleep(2)
                continue
            logger.warning(f"FRED {series_id} series fetch 실패: {e}")
            return None
    return None


def fetch_move_series(
    n_periods: int = 20,
    end_date: Optional[str] = None,
) -> Optional[pd.Series]:
    """Yahoo Finance ^MOVE 시리즈. end_date 지정 시 해당 날짜 기준."""
    try:
        if end_date:
            end_dt = pd.Timestamp(end_date)
            start_dt = end_dt - pd.Timedelta(days=n_periods * 2 + 60)
            data = yf.Ticker("^MOVE").history(
                start=start_dt.strftime("%Y-%m-%d"),
                end=(end_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            )
        else:
            data = yf.Ticker("^MOVE").history(period=f"{min(n_periods * 2 + 60, 3650)}d")
        if data.empty:
            logger.warning("MOVE series: 빈 데이터")
            return None
        series = data["Close"].dropna()
        return series.iloc[-n_periods:]
    except Exception as e:
        logger.warning(f"MOVE series fetch 실패: {e}")
        return None


def fetch_ism_pmi(api_key: str) -> Optional[float]:
    """ISM 제조업 PMI (NAPM). 50 기준 확장/수축."""
    return fetch_fred("NAPM", api_key)


def fetch_nfp_change(api_key: str) -> Optional[float]:
    """비농업 고용 전월비 변화 (단위: 천명)."""
    try:
        data = Fred(api_key=api_key).get_series("PAYEMS").dropna()
        if len(data) < 2:
            return None
        return round(float(data.iloc[-1] - data.iloc[-2]), 0)
    except Exception as e:
        logger.warning(f"NFP fetch 실패: {e}")
        return None


def fetch_fed_balance(api_key: str) -> Optional[float]:
    """Fed 대차대조표 규모 (단위: 조 달러)."""
    try:
        data = Fred(api_key=api_key).get_series("WALCL").dropna()
        if data.empty:
            return None
        return round(float(data.iloc[-1]) / 1_000_000, 2)  # millions → trillions
    except Exception as e:
        logger.warning(f"Fed 대차대조표 fetch 실패: {e}")
        return None


def fetch_m2_yoy(api_key: str) -> Optional[float]:
    """M2 통화량 전년비 증가율 (%)."""
    try:
        data = Fred(api_key=api_key).get_series("M2SL").dropna()
        if len(data) < 13:
            return None
        return round(float(data.iloc[-1] / data.iloc[-13] - 1) * 100, 2)
    except Exception as e:
        logger.warning(f"M2 YoY fetch 실패: {e}")
        return None


def fetch_wti() -> Optional[float]:
    """WTI 원유 선물 현재가 (USD/배럴)."""
    try:
        data = yf.Ticker("CL=F").history(period="5d")
        if data.empty:
            return None
        return float(data["Close"].dropna().iloc[-1])
    except Exception as e:
        logger.warning(f"WTI fetch 실패: {e}")
        return None


def fetch_copper() -> Optional[float]:
    """구리 선물 현재가 (USD/파운드)."""
    try:
        data = yf.Ticker("HG=F").history(period="5d")
        if data.empty:
            return None
        return float(data["Close"].dropna().iloc[-1])
    except Exception as e:
        logger.warning(f"구리 fetch 실패: {e}")
        return None


def fetch_put_call_ratio() -> Optional[float]:
    """CBOE 주식 Put/Call Ratio 일별 최신값. 실패 시 None."""
    try:
        url = "https://www.cboe.com/publish/scheduledtask/mktdata/datahouse/equitypc.csv"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().splitlines():
            line = line.strip()
            if not line or line.upper().startswith('"DATE') or line.upper().startswith('DATE'):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                rows.append(parts)
        if not rows:
            return None
        return round(float(rows[-1][1].strip().strip('"')), 2)
    except Exception as e:
        logger.warning(f"Put/Call Ratio fetch 실패: {e}")
        return None


def fetch_fear_greed() -> Optional[float]:
    """CNN Fear & Greed Index (0~100). 비공식 API — 실패 시 None."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return round(float(resp.json()["fear_and_greed"]["score"]), 1)
    except Exception as e:
        logger.warning(f"Fear & Greed fetch 실패: {e}")
        return None


def fetch_all(api_key: str) -> dict[str, Optional[float]]:
    """12개 핵심 + 8개 확장 지표 fetch. 실패 지표는 None."""
    results: dict[str, Optional[float]] = {}

    for name, series_id in FRED_SERIES.items():
        results[name] = fetch_fred(series_id, api_key)

    results["cpi_yoy"] = fetch_cpi_yoy(api_key)
    results["move"]    = fetch_move()

    # 확장 지표
    results["ism_pmi"]   = fetch_ism_pmi(api_key)
    results["nfp_chg"]   = fetch_nfp_change(api_key)
    results["fed_bs"]    = fetch_fed_balance(api_key)
    results["m2_yoy"]    = fetch_m2_yoy(api_key)
    results["wti"]       = fetch_wti()
    results["copper"]    = fetch_copper()
    results["pc_ratio"]  = fetch_put_call_ratio()
    results["fear_greed"] = fetch_fear_greed()

    failed = [k for k, v in results.items() if v is None]
    if failed:
        logger.warning(f"fetch 실패 지표: {failed}")
    else:
        logger.info("20개 지표 전체 fetch 완료")

    return results