"""Phase 4: 모멘텀 7개 지표 점수화 + 종목 스캔."""
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

TICKERS = [
    "TQQQ", "UPRO", "SPXL", "SOXL", "LABU", "FAS", "FNGU",  # US 레버리지
    "SQQQ", "SPXU", "SOXS",                                   # US 인버스
    "GLD", "TLT", "BIL", "XLE", "XLP", "XLV", "SCHP",        # US 자산
    "122630.KS", "233740.KS",                                  # 한국 (실패 시 skip)
]


def _fetch_ohlcv(ticker: str) -> Optional[pd.DataFrame]:
    """yfinance OHLCV 250일 fetch. 데이터 부족/실패 시 None."""
    try:
        data = yf.Ticker(ticker).history(period="250d")
        if data.empty or len(data) < 50:
            logger.warning(f"{ticker}: 데이터 부족 ({len(data)}일)")
            return None
        return data
    except Exception as e:
        logger.warning(f"{ticker} fetch 실패: {e}")
        return None


def _rsi(close: pd.Series, period: int = 14) -> float:
    """RSI(14) 계산."""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else float("inf")
    return float(100 - 100 / (1 + rs))


def _macd_above_zero_expanding(close: pd.Series) -> bool:
    """MACD 0선 위 + 히스토그램 확대."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return bool(macd.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2])


def _check_rs_rising(close: pd.Series, spy_close: pd.Series) -> bool:
    """RS 50일 MA 우상향 (vs SPY)."""
    common = close.index.intersection(spy_close.index)
    if len(common) < 55:
        return False
    rs = close.reindex(common) / spy_close.reindex(common)
    ma = rs.rolling(50).mean().dropna()
    return bool(len(ma) >= 6 and ma.iloc[-1] > ma.iloc[-6])


def _check_ma_aligned(close: pd.Series) -> bool:
    """가격 > 50DMA > 200DMA."""
    if len(close) < 200:
        return False
    return bool(close.iloc[-1] > close.rolling(50).mean().iloc[-1] > close.rolling(200).mean().iloc[-1])


def _check_rsi_above50(close: pd.Series) -> bool:
    """RSI(14) ≥ 50."""
    return bool(len(close) >= 15 and _rsi(close) >= 50)


def _check_macd_bullish(close: pd.Series) -> bool:
    """MACD 0선 위 + 히스토그램 확대."""
    return bool(len(close) >= 35 and _macd_above_zero_expanding(close))


def _check_near_high(close: pd.Series) -> bool:
    """최근 5일 내 20일 신고가 달성."""
    if len(close) < 20:
        return False
    return bool(close.iloc[-5:].max() >= close.iloc[-20:].max())


def _check_volume_rising(volume: pd.Series) -> bool:
    """5일 평균 거래량 > 20일 평균."""
    if len(volume) < 20 or volume.sum() == 0:
        return False
    return bool(volume.iloc[-5:].mean() > volume.iloc[-20:].mean())


def _check_sharpe_positive(close: pd.Series) -> bool:
    """3개월(63일) 수익률 양수."""
    return bool(len(close) >= 63 and close.iloc[-1] > close.iloc[-63])


def score_ticker(ticker: str, spy_close: Optional[pd.Series] = None) -> Optional[dict]:
    """종목 모멘텀 7개 지표 점수 계산. 실패 시 None."""
    data = _fetch_ohlcv(ticker)
    if data is None:
        return None
    close = data["Close"]
    volume = data["Volume"]

    conditions = {
        "rs_rising":      _check_rs_rising(close, spy_close) if spy_close is not None else False,
        "ma_aligned":     _check_ma_aligned(close),
        "rsi_above50":    _check_rsi_above50(close),
        "macd_bullish":   _check_macd_bullish(close),
        "near_high":      _check_near_high(close),
        "volume_rising":  _check_volume_rising(volume),
        "sharpe_positive": _check_sharpe_positive(close),
    }
    score = sum(conditions.values())
    logger.debug(f"{ticker}: {score}/7 {conditions}")
    return {"ticker": ticker, "score": score, "details": conditions}


def scan_all() -> list[dict]:
    """전체 종목 모멘텀 스캔. 점수 내림차순 반환."""
    spy_data = _fetch_ohlcv("SPY")
    spy_close = spy_data["Close"] if spy_data is not None else None

    results = []
    for ticker in TICKERS:
        result = score_ticker(ticker, spy_close)
        if result is not None:
            results.append(result)

    return sorted(results, key=lambda x: x["score"], reverse=True)
