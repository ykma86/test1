"""Phase 0 MVP: VIX 임계치 감지 → Telegram 알림."""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yfinance as yf

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
        return {"threshold_level": 0, "last_vix": None, "last_updated": None}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    """상태 파일 저장."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def build_message(vix: float, new_level: int, prev_level: int) -> str:
    """알림 메시지 생성."""
    direction = "↑" if new_level > prev_level else "↓"
    body = THRESHOLD_MESSAGES.get(new_level, "")
    return f"📊 VIX 임계치 알림 {direction}\n현재 VIX: {vix:.2f}\n{body}{DISCLAIMER}"


def send_telegram(message: str, token: str, chat_id: str) -> None:
    """Telegram 봇으로 메시지 발송."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    resp.raise_for_status()
    logger.info("텔레그램 발송 완료")


def main(dry_run: bool = False, token: str = "", chat_id: str = "") -> None:
    """메인: VIX fetch → 임계치 판정 → 알림."""
    logger.info(f"VIX 알림 실행 (dry_run={dry_run})")

    try:
        vix = fetch_vix()
    except Exception as e:
        logger.error(f"VIX fetch 실패: {e}")
        sys.exit(1)

    logger.info(f"VIX: {vix:.2f}")
    state = load_state()
    prev_level = state["threshold_level"]
    new_level = get_threshold_level(vix)

    if new_level == prev_level:
        logger.info(f"임계치 변화 없음 (level={new_level}), 알림 스킵")
        return

    message = build_message(vix, new_level, prev_level)
    logger.info(f"임계치 변경: {prev_level} → {new_level}")

    if dry_run:
        logger.info(f"[DRY-RUN] 발송 예정 메시지:\n{message}")
        return

    send_telegram(message, token, chat_id)
    save_state({
        "threshold_level": new_level,
        "last_vix": vix,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIX 임계치 알림 (Phase 0 MVP)")
    parser.add_argument("--dry-run", action="store_true", help="알림/저장 없이 테스트 실행")
    args = parser.parse_args()

    _token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "")
    _chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")

    if not args.dry_run and (not _token or not _chat_id):
        logger.error("환경변수 필요: TELEGRAM_TEST_BOT_TOKEN, TELEGRAM_TEST_CHAT_ID")
        sys.exit(1)

    main(dry_run=args.dry_run, token=_token, chat_id=_chat_id)
