"""Phase 0 MVP: VIX 임계치 감지 → Telegram 알림."""
import argparse
import json
import logging
import os
import sys
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

from classifier import classify_phase
from falling_knife import (
    evaluate as fk_evaluate,
    fetch_data as fk_fetch,
    build_alert_message as fk_alert,
    build_clear_message as fk_clear,
)
from fetchers import fetch_series, fetch_move_series, fetch_fred
from momentum import scan_all
from regime import classify_regime, get_position_guide, REGIME_EMOJI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STATE_FILE = Path("state/previous_state.json")
DISCLAIMER = "\n⚠️ 본 시스템은 정보 제공 도구이며 투자 자문이 아닙니다."

THRESHOLD_MESSAGES = {
    30: "🔴 VIX 30 돌파 — 전량 청산 검토",
    25: "🟠 VIX 25 돌파 — 비중 50% 축소 검토",
    20: "🟡 VIX 20 돌파 — 비중 30% 축소 검토",
    0:  "🟢 VIX 20 하향 — 안정 구간 회복",
}

PHASE_EMOJI = {"회피": "🔴", "1단계": "🟡", "2단계": "🟢", "3단계": "🟠", "불명확": "⚪"}


def fetch_vix() -> float:
    """Yahoo Finance에서 VIX 현재값 조회."""
    data = yf.Ticker("^VIX").history(period="1d")
    if data.empty:
        raise ValueError("VIX 데이터 조회 실패")
    return float(data["Close"].iloc[-1])


def get_threshold_level(vix: float) -> int:
    """VIX값으로 현재 임계치 레벨 반환 (0, 20, 25, 30)."""
    if vix >= 30:
        return 30
    if vix >= 25:
        return 25
    if vix >= 20:
        return 20
    return 0


def load_state() -> dict:
    """이전 상태 로드. 파일 없으면 기본값 반환."""
    if not STATE_FILE.exists():
        return {
            "threshold_level": 0,
            "phase": "불명확",
            "regime": "불명확",
            "last_vix": None,
            "last_updated": None,
            "fx_level": "normal",
        }
    state = json.loads(STATE_FILE.read_text())
    state.setdefault("phase", "불명확")
    state.setdefault("regime", "불명확")
    state.setdefault("momentum_top3", [])
    state.setdefault("momentum_scores", {})
    state.setdefault("falling_knife_active", False)
    state.setdefault("fx_level", "normal")
    return state


def save_state(state: dict) -> None:
    """상태 파일 저장."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def build_message(vix: float, new_level: int, prev_level: int) -> str:
    """알림 메시지 생성."""
    direction = "↑" if new_level > prev_level else "↓"
    body = THRESHOLD_MESSAGES.get(new_level, "")
    return f"📊 VIX 임계치 알림 {direction}\n현재 VIX: {vix:.2f}\n{body}{DISCLAIMER}"


def fetch_phase_data(api_key: str) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series] | None:
    """단계 분류용 시리즈 fetch. 실패 시 None."""
    cli   = fetch_series("OECDLOLITOAASTSAM", api_key, n_periods=6)
    anfci = fetch_series("ANFCI",             api_key, n_periods=8)
    vix_s = fetch_series("VIXCLS",            api_key, n_periods=40)
    move  = fetch_move_series(n_periods=400)
    if cli is None or anfci is None or vix_s is None:
        logger.warning("단계 분류 데이터 부족 — 단계 판정 스킵")
        return None
    return cli, anfci, vix_s, move if move is not None else pd.Series(dtype=float)


def fetch_regime_data(api_key: str, end_date: str | None = None) -> tuple[pd.Series, pd.Series] | None:
    """체제 분류용 시리즈 fetch. 실패 시 None."""
    cli     = fetch_series("OECDLOLITOAASTSAM", api_key, n_periods=6, end_date=end_date)
    bei_raw = fetch_series("T5YIE",             api_key, n_periods=200, end_date=end_date)
    if cli is None or bei_raw is None:
        logger.warning("체제 분류 데이터 부족 — 체제 판정 스킵")
        return None
    bei = bei_raw.resample("ME").last().iloc[-8:]
    if len(bei) < 7:
        logger.warning("BEI 월별 데이터 부족")
        return None
    return cli, bei


def build_regime_message(new_regime: str, prev_regime: str, phase: str) -> str:
    """체제 전환 알림 메시지 생성."""
    e_new  = REGIME_EMOJI.get(new_regime, "⚪")
    e_prev = REGIME_EMOJI.get(prev_regime, "⚪")
    guide  = get_position_guide(new_regime)
    return (
        f"🌐 거시 체제 전환\n"
        f"{e_prev} {prev_regime} → {e_new} {new_regime}\n"
        f"현재 단계: {PHASE_EMOJI.get(phase, '⚪')} {phase}\n"
        f"포지션: {guide}"
        f"{DISCLAIMER}"
    )


def build_momentum_top3_message(results: list[dict]) -> str:
    """모멘텀 TOP 3 변경 알림 메시지."""
    lines = ["🚀 모멘텀 TOP 3 변경"]
    for i, r in enumerate(results[:3], 1):
        lines.append(f"{i}. {r['ticker']}: {r['score']}/7점")
    return "\n".join(lines) + DISCLAIMER


def build_degradation_message(degraded: list[tuple[str, int, int]]) -> str:
    """모멘텀 약화 알림 메시지 (5점 이상 → 3점 이하)."""
    lines = ["⚠️ 모멘텀 약화 경고"]
    for ticker, prev, curr in degraded:
        lines.append(f"• {ticker}: {prev}점 → {curr}점")
    return "\n".join(lines) + DISCLAIMER


def build_phase_message(new_phase: str, prev_phase: str) -> str:
    """단계 전환 알림 메시지 생성."""
    e_new  = PHASE_EMOJI.get(new_phase, "⚪")
    e_prev = PHASE_EMOJI.get(prev_phase, "⚪")
    return (
        f"📍 매크로 단계 전환\n"
        f"{e_prev} {prev_phase} → {e_new} {new_phase}\n"
        f"{DISCLAIMER}"
    )


# ── Phase 9: 스마트 데일리 ────────────────────────────────────────

def get_fx_level(usdkrw: float | None) -> str:
    """USD/KRW 값으로 레벨 반환 (high/low/normal/unknown)."""
    if usdkrw is None:
        return "unknown"
    if usdkrw >= 1450:
        return "high"
    if usdkrw <= 1250:
        return "low"
    return "normal"


def check_fx_threshold(usdkrw: float | None, prev_level: str) -> tuple[str | None, str]:
    """환율 임계치 체크. (알림메시지|None, 새레벨) 반환."""
    new_level = get_fx_level(usdkrw)
    if new_level == "unknown" or new_level == prev_level:
        return None, prev_level
    return _build_fx_message(usdkrw, new_level), new_level  # type: ignore[arg-type]


def _build_fx_message(usdkrw: float, new_level: str) -> str:
    """환율 알림 메시지 생성."""
    if new_level == "high":
        body = f"USD/KRW {usdkrw:,.0f}원 (1,450 돌파)\n⚠️ 미국 ETF 진입 비용 증가 — 비중 축소 검토"
    elif new_level == "low":
        body = f"USD/KRW {usdkrw:,.0f}원 (1,250 하향)\n✅ 환노출 ETF 유리 구간"
    else:
        body = f"USD/KRW {usdkrw:,.0f}원 — 정상 구간 복귀 (1,250~1,450)"
    return f"💱 환율 알림\n{body}{DISCLAIMER}"


def build_daily_summary(
    vix: float,
    phase: str,
    regime: str,
    usdkrw: float | None,
    momentum_results: list[dict],
) -> str:
    """일일 현황 요약 메시지."""
    fx_str  = f"{usdkrw:,.0f}원" if usdkrw else "N/A"
    top1    = momentum_results[0] if momentum_results else None
    top1_str = f"{top1['ticker']} ({top1['score']}/7)" if top1 else "없음"
    guide   = get_position_guide(regime)
    return (
        f"📊 일일 요약\n"
        f"단계: {PHASE_EMOJI.get(phase,'⚪')} {phase} | 체제: {REGIME_EMOJI.get(regime,'⚪')} {regime}\n"
        f"VIX: {vix:.1f} | USD/KRW: {fx_str}\n"
        f"모멘텀 TOP1: {top1_str}\n"
        f"포지션: {guide}"
        f"{DISCLAIMER}"
    )


def build_bundle_message(alerts: list[str]) -> str:
    """여러 알림을 하나의 메시지로 묶기."""
    body = "\n━━━━━━━━━━\n".join(alerts)
    return f"📋 매크로 알림 ({len(alerts)}개)\n━━━━━━━━━━\n{body}"


def _is_quiet_hours(
    quiet_start: int, quiet_end: int, _now: datetime | None = None
) -> bool:
    """현재 KST 시각이 quiet 구간인지 확인. _now는 테스트용 주입."""
    if _now is None:
        _now = datetime.now(timezone(timedelta(hours=9)))
    return quiet_start <= _now.hour < quiet_end


# ─────────────────────────────────────────────────────────────────

def send_telegram(message: str, token: str, chat_id: str) -> None:
    """Telegram 봇으로 메시지 발송."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    resp.raise_for_status()
    logger.info("텔레그램 발송 완료")


def main(
    dry_run: bool = False,
    token: str = "",
    chat_id: str = "",
    fred_api_key: str = "",
    daily: bool = False,
) -> None:
    """메인: VIX 임계치 + 매크로 단계 판정 → 알림."""
    logger.info(f"알림 실행 (dry_run={dry_run}, daily={daily})")

    try:
        vix = fetch_vix()
    except Exception as e:
        logger.error(f"VIX fetch 실패: {e}")
        sys.exit(1)

    logger.info(f"VIX: {vix:.2f}")
    state = load_state()
    prev_level    = state["threshold_level"]
    prev_phase    = state.get("phase", "불명확")
    prev_regime   = state.get("regime", "불명확")
    prev_fx_level = state.get("fx_level", "normal")
    new_level = get_threshold_level(vix)

    cfg = yaml.safe_load(Path("config/thresholds.yaml").read_text(encoding="utf-8"))
    quiet_start, quiet_end = cfg.get("quiet_hours", [0, 7])
    fk_enabled = cfg.get("falling_knife_mode", True)

    # 단계 + 체제 분류 (FRED key 있을 때만)
    new_phase  = prev_phase
    new_regime = prev_regime
    if fred_api_key:
        data = fetch_phase_data(fred_api_key)
        if data:
            classified = classify_phase(*data)
            if classified != "불명확":
                new_phase = classified
                logger.info(f"단계: {prev_phase} → {new_phase}")
        regime_data = fetch_regime_data(fred_api_key)
        if regime_data:
            new_regime = classify_regime(*regime_data)
            logger.info(f"체제: {prev_regime} → {new_regime}")

    # 모멘텀 스캔
    prev_top3   = state.get("momentum_top3", [])
    prev_scores = state.get("momentum_scores", {})
    momentum_results = scan_all()
    new_scores = {r["ticker"]: r["score"] for r in momentum_results}
    new_top3   = [r["ticker"] for r in momentum_results[:3]]

    top3_changed = new_top3 != prev_top3
    degraded = [
        (t, prev_scores[t], new_scores[t])
        for t in new_scores
        if prev_scores.get(t, 0) >= 5 and new_scores[t] <= 3
    ]

    # 떨어지는 칼날 체크
    prev_fk_active = state.get("falling_knife_active", False)
    new_fk_active  = False
    fk_triggers    = {}
    if fk_enabled:
        fk_data = fk_fetch()
        if fk_data:
            spy_s, vix_s = fk_data
            hy_s = fetch_series("BAMLH0A0HYM2", fred_api_key, n_periods=10) if fred_api_key else None
            fk_triggers   = fk_evaluate(spy_s, vix_s, hy_s if hy_s is not None else pd.Series(dtype=float))
            new_fk_active = bool(fk_triggers.get("active", False))
    fk_activated = new_fk_active and not prev_fk_active
    fk_cleared   = not new_fk_active and prev_fk_active

    # 환율 임계치 체크
    usdkrw = fetch_fred("DEXKOUS", fred_api_key) if fred_api_key else None
    fx_msg, new_fx_level = check_fx_threshold(usdkrw, prev_fx_level)
    fx_changed = fx_msg is not None

    level_changed  = new_level  != prev_level
    phase_changed  = new_phase  != prev_phase  and new_phase  != "불명확"
    regime_changed = new_regime != prev_regime

    has_change = any([
        level_changed, phase_changed, regime_changed,
        top3_changed, degraded, fk_activated, fk_cleared, fx_changed,
    ])

    if not has_change and not daily:
        logger.info(f"변화 없음 (level={new_level}, phase={new_phase}, regime={new_regime}), 알림 스킵")
        return

    # 알림 목록 구성
    alerts: list[str] = []
    if fx_changed and fx_msg:
        alerts.append(fx_msg)
        logger.info(f"환율 레벨 변경: {prev_fx_level} → {new_fx_level}")
    if level_changed:
        alerts.append(build_message(vix, new_level, prev_level))
        logger.info(f"임계치 변경: {prev_level} → {new_level}")
    if phase_changed:
        alerts.append(build_phase_message(new_phase, prev_phase))
    if regime_changed:
        alerts.append(build_regime_message(new_regime, prev_regime, new_phase))
    if top3_changed and new_top3:
        alerts.append(build_momentum_top3_message(momentum_results))
        logger.info(f"TOP 3 변경: {prev_top3} → {new_top3}")
    for d in degraded:
        alerts.append(build_degradation_message([d]))
        logger.info(f"모멘텀 약화: {d[0]} {d[1]}→{d[2]}")
    if fk_activated:
        sqqq_score = new_scores.get("SQQQ", 0)
        if sqqq_score >= 5:
            alerts.append(fk_alert(fk_triggers, sqqq_score))
            logger.info(f"떨어지는 칼날 진입 (SQQQ {sqqq_score}/7)")
        else:
            logger.info(f"떨어지는 칼날 트리거됐으나 SQQQ 점수 부족 ({sqqq_score}/7 < 5)")
    if fk_cleared:
        alerts.append(fk_clear())
        logger.info("떨어지는 칼날 해제")
    if daily:
        alerts.append(build_daily_summary(vix, new_phase, new_regime, usdkrw, momentum_results))

    # Quiet hours: 긴급 아닌 알림 억제 (KST quiet_start~quiet_end)
    urgent = new_level >= 30 or fk_activated
    if _is_quiet_hours(quiet_start, quiet_end) and not urgent:
        logger.info(f"Quiet hours ({quiet_start}~{quiet_end}시 KST) — non-urgent 알림 억제, 상태만 저장")
        if not dry_run:
            save_state({
                "threshold_level": new_level,
                "phase": new_phase,
                "regime": new_regime,
                "momentum_top3": new_top3,
                "momentum_scores": new_scores,
                "falling_knife_active": new_fk_active,
                "fx_level": new_fx_level,
                "last_vix": vix,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })
        return

    if dry_run:
        for msg in alerts:
            logger.info(f"[DRY-RUN] 발송 예정:\n{msg}")
        return

    # 번들링 발송: 1개면 그대로, 2개 이상이면 하나로 묶기
    if len(alerts) == 1:
        send_telegram(alerts[0], token, chat_id)
    elif len(alerts) > 1:
        send_telegram(build_bundle_message(alerts), token, chat_id)

    save_state({
        "threshold_level": new_level,
        "phase": new_phase,
        "regime": new_regime,
        "momentum_top3": new_top3,
        "momentum_scores": new_scores,
        "falling_knife_active": new_fk_active,
        "fx_level": new_fx_level,
        "last_vix": vix,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIX 임계치 알림 (Phase 0 MVP)")
    parser.add_argument("--dry-run", action="store_true", help="알림/저장 없이 테스트 실행")
    parser.add_argument("--daily",   action="store_true", help="일일 요약 발송 (변화 없어도)")
    args = parser.parse_args()

    _token    = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "")
    _chat_id  = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")
    _fred_key = os.environ.get("FRED_API_KEY", "")

    if not args.dry_run and (not _token or not _chat_id):
        logger.error("환경변수 필요: TELEGRAM_TEST_BOT_TOKEN, TELEGRAM_TEST_CHAT_ID")
        sys.exit(1)

    main(dry_run=args.dry_run, token=_token, chat_id=_chat_id, fred_api_key=_fred_key, daily=args.daily)
