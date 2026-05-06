"""Phase 0 MVP: VIX 임계치 감지 → Telegram 알림."""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

from classifier import classify_phase
from fetchers import fetch_series, fetch_move_series
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
        return {"threshold_level": 0, "phase": "불명확", "regime": "불명확", "last_vix": None, "last_updated": None}
    state = json.loads(STATE_FILE.read_text())
    state.setdefault("phase", "불명확")
    state.setdefault("regime", "불명확")
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


PHASE_EMOJI = {"회피": "🔴", "1단계": "🟡", "2단계": "🟢", "3단계": "🟠", "불명확": "⚪"}


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
    bei_raw = fetch_series("T5YIE",             api_key, n_periods=200, end_date=end_date)  # 일별 ~10개월
    if cli is None or bei_raw is None:
        logger.warning("체제 분류 데이터 부족 — 체제 판정 스킵")
        return None
    bei = bei_raw.resample("ME").last().iloc[-8:]  # 월별로 축소 후 8개 (6개월 비교용)
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


def build_phase_message(new_phase: str, prev_phase: str) -> str:
    """단계 전환 알림 메시지 생성."""
    e_new  = PHASE_EMOJI.get(new_phase, "⚪")
    e_prev = PHASE_EMOJI.get(prev_phase, "⚪")
    return (
        f"📍 매크로 단계 전환\n"
        f"{e_prev} {prev_phase} → {e_new} {new_phase}\n"
        f"{DISCLAIMER}"
    )


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
) -> None:
    """메인: VIX 임계치 + 매크로 단계 판정 → 알림."""
    logger.info(f"알림 실행 (dry_run={dry_run})")

    try:
        vix = fetch_vix()
    except Exception as e:
        logger.error(f"VIX fetch 실패: {e}")
        sys.exit(1)

    logger.info(f"VIX: {vix:.2f}")
    state = load_state()
    prev_level = state["threshold_level"]
    prev_phase = state.get("phase", "불명확")
    prev_regime = state.get("regime", "불명확")
    new_level = get_threshold_level(vix)

    # 단계 + 체제 분류 (FRED key 있을 때만)
    new_phase = prev_phase
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

    level_changed = new_level != prev_level
    phase_changed = new_phase != prev_phase and new_phase != "불명확"
    regime_changed = new_regime != prev_regime

    if not level_changed and not phase_changed and not regime_changed:
        logger.info(f"변화 없음 (level={new_level}, phase={new_phase}, regime={new_regime}), 알림 스킵")
        return

    alerts = []
    if level_changed:
        alerts.append(build_message(vix, new_level, prev_level))
        logger.info(f"임계치 변경: {prev_level} → {new_level}")
    if phase_changed:
        alerts.append(build_phase_message(new_phase, prev_phase))
    if regime_changed:
        alerts.append(build_regime_message(new_regime, prev_regime, new_phase))

    if dry_run:
        for msg in alerts:
            logger.info(f"[DRY-RUN] 발송 예정:\n{msg}")
        return

    for msg in alerts:
        send_telegram(msg, token, chat_id)
    save_state({
        "threshold_level": new_level,
        "phase": new_phase,
        "regime": new_regime,
        "last_vix": vix,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIX 임계치 알림 (Phase 0 MVP)")
    parser.add_argument("--dry-run", action="store_true", help="알림/저장 없이 테스트 실행")
    args = parser.parse_args()

    _token    = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "")
    _chat_id  = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")
    _fred_key = os.environ.get("FRED_API_KEY", "")

    if not args.dry_run and (not _token or not _chat_id):
        logger.error("환경변수 필요: TELEGRAM_TEST_BOT_TOKEN, TELEGRAM_TEST_CHAT_ID")
        sys.exit(1)

    main(dry_run=args.dry_run, token=_token, chat_id=_chat_id, fred_api_key=_fred_key)
