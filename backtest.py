"""Phase 7: 과거 시나리오 백테스트 — Phase/Regime 분류기 검증."""
import argparse
import logging
import os
import sys

import pandas as pd

from classifier import classify_phase
from fetchers import fetch_series, fetch_move_series
from regime import classify_regime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCENARIOS = [
    {"date": "2009-03-31", "event": "GFC 바닥",       "phase": "회피",  "regime": "침체"},
    {"date": "2020-04-30", "event": "COVID 충격",      "phase": "회피",  "regime": "침체"},
    {"date": "2020-12-31", "event": "COVID 회복",      "phase": "2단계", "regime": "리플레이션"},
    {"date": "2021-09-30", "event": "강세장 후반",     "phase": "2단계", "regime": "리플레이션"},
    {"date": "2022-09-30", "event": "금리인상 충격",   "phase": "회피",  "regime": "스태그플레이션"},
    {"date": "2023-06-30", "event": "연착륙 기대",     "phase": "1단계", "regime": "골디락스"},
]


def _fetch_phase_inputs(
    date: str, api_key: str
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series] | None:
    """단계 분류 입력 데이터 fetch (end_date 기준)."""
    cli   = fetch_series("OECDLOLITOAASTSAM", api_key, n_periods=6,  end_date=date)
    anfci = fetch_series("ANFCI",             api_key, n_periods=8,  end_date=date)
    vix_s = fetch_series("VIXCLS",            api_key, n_periods=40, end_date=date)
    move  = fetch_move_series(n_periods=400, end_date=date)
    if cli is None or anfci is None or vix_s is None:
        return None
    return cli, anfci, vix_s, move if move is not None else pd.Series(dtype=float)


def _fetch_regime_inputs(
    date: str, api_key: str
) -> tuple[pd.Series, pd.Series] | None:
    """체제 분류 입력 데이터 fetch (end_date 기준)."""
    cli     = fetch_series("OECDLOLITOAASTSAM", api_key, n_periods=6,   end_date=date)
    bei_raw = fetch_series("T5YIE",             api_key, n_periods=200, end_date=date)
    if cli is None or bei_raw is None:
        return None
    bei = bei_raw.resample("ME").last().iloc[-8:]
    if len(bei) < 7:
        logger.warning(f"BEI 월별 데이터 부족 ({date})")
        return None
    return cli, bei


def run_scenario(s: dict, api_key: str) -> dict:
    """단일 시나리오 실행 → 결과 dict."""
    date = s["date"]
    result: dict = {
        "date":            date,
        "event":           s["event"],
        "expected_phase":  s["phase"],
        "expected_regime": s["regime"],
        "actual_phase":    "불명확",
        "actual_regime":   "불명확",
    }

    phase_inputs = _fetch_phase_inputs(date, api_key)
    if phase_inputs:
        result["actual_phase"] = classify_phase(*phase_inputs)
    else:
        logger.warning(f"[{date}] Phase 입력 데이터 부족")

    regime_inputs = _fetch_regime_inputs(date, api_key)
    if regime_inputs:
        result["actual_regime"] = classify_regime(*regime_inputs)
    else:
        logger.warning(f"[{date}] Regime 입력 데이터 부족")

    result["phase_ok"]  = result["actual_phase"]  == result["expected_phase"]
    result["regime_ok"] = result["actual_regime"] == result["expected_regime"]
    return result


def run_backtest(api_key: str) -> list[dict]:
    """6개 시나리오 전체 실행."""
    results = []
    for s in SCENARIOS:
        logger.info(f"시나리오: {s['date']} {s['event']}")
        results.append(run_scenario(s, api_key))
    return results


def print_report(results: list[dict]) -> None:
    """결과 테이블 출력."""
    print("\n" + "=" * 84)
    print("백테스트 결과")
    print("=" * 84)
    print(f"{'날짜':<12} {'이벤트':<12} {'기대Phase':<10} {'실제Phase':<10} {'P':<3} "
          f"{'기대Regime':<14} {'실제Regime':<14} {'R'}")
    print("-" * 84)
    for r in results:
        p = "✓" if r["phase_ok"] else "✗"
        reg = "✓" if r["regime_ok"] else "✗"
        print(
            f"{r['date']:<12} {r['event']:<12} "
            f"{r['expected_phase']:<10} {r['actual_phase']:<10} {p:<3} "
            f"{r['expected_regime']:<14} {r['actual_regime']:<14} {reg}"
        )
    print("-" * 84)
    phase_pass  = sum(r["phase_ok"]  for r in results)
    regime_pass = sum(r["regime_ok"] for r in results)
    total = len(results)
    overall = "PASS ✓" if phase_pass >= 5 and regime_pass >= 5 else "FAIL ✗"
    print(f"Phase: {phase_pass}/{total}  Regime: {regime_pass}/{total}  →  {overall} (기준: 각 5/6)")
    print("=" * 84 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 7: 백테스트 엔진")
    parser.add_argument("--fred-key", default=os.environ.get("FRED_API_KEY", ""))
    args = parser.parse_args()

    if not args.fred_key:
        print("오류: FRED API 키 필요 (--fred-key 또는 FRED_API_KEY 환경변수)")
        sys.exit(1)

    results = run_backtest(args.fred_key)
    print_report(results)
