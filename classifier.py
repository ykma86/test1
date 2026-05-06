"""Phase 2: 매크로 단계 분류 (1~4단계 + 회피)."""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ── 회피 조건 (3개 중 2개 이상 → 회피) ───────────────────────────

def _cli_declining(cli: pd.Series) -> bool:
    """CLI 고점 통과 후 3개월 전 대비 하락."""
    if len(cli) < 4:
        return False
    return bool(cli.iloc[-1] < cli.iloc[-4])


def _anfci_turning_positive(anfci: pd.Series) -> bool:
    """ANFCI 음수→양수 전환 또는 빠르게 상승."""
    if len(anfci) < 5:
        return False
    was_low = anfci.iloc[-5] < 0.3
    rising_fast = anfci.iloc[-1] > anfci.iloc[-5] + 0.2
    turned_positive = anfci.iloc[-1] >= 0 and anfci.iloc[-5] < 0
    return bool(was_low and (rising_fast or turned_positive))


def _vix_trending_up_or_30plus(vix: pd.Series) -> bool:
    """VIX 30 돌파 또는 10일 전 대비 15% 이상 상승."""
    if vix.iloc[-1] > 30:
        return True
    if len(vix) < 11:
        return False
    return bool(vix.iloc[-1] > vix.iloc[-11] * 1.15)


# ── 1단계 조건 (4개 중 3개 이상 → 1단계) ─────────────────────────

def _cli_rebounding(cli: pd.Series) -> bool:
    """CLI < 100, 3개월 전 대비 반등."""
    if len(cli) < 4:
        return False
    return bool(cli.iloc[-1] < 100 and cli.iloc[-1] > cli.iloc[-4])


def _anfci_peak_declining(anfci: pd.Series) -> bool:
    """ANFCI 로컬 고점 통과 후 하락 (2022형 소폭 고점 포함)."""
    if len(anfci) < 5:
        return False
    peak = anfci.iloc[-5:].max()
    return bool(peak > -0.1 and anfci.iloc[-1] < peak - 0.05)


def _vix_cooling_from_high(vix: pd.Series) -> bool:
    """VIX 30 초과 고점 대비 -20% 이상 진정 (30일 윈도우)."""
    n = min(31, len(vix))
    if n < 11:
        return False
    high = vix.iloc[-n:-1].max()
    return bool(high > 30 and vix.iloc[-1] < high * 0.8)


def _move_peak_declining(move: pd.Series) -> bool:
    """MOVE 최근 고점 이후 5% 이상 하락."""
    if len(move) < 11:
        return False
    recent = move.iloc[-11:]
    return bool(recent.iloc[-1] < recent.max() * 0.95)


# ── 2단계 조건 (4개 중 3개 이상 → 2단계) ─────────────────────────

def _cli_above_100_rising(cli: pd.Series) -> bool:
    """CLI > 100, 3개월 모멘텀 양수."""
    if len(cli) < 4:
        return False
    return bool(cli.iloc[-1] > 100 and cli.iloc[-1] > cli.iloc[-4])


def _anfci_negative(anfci: pd.Series) -> bool:
    """ANFCI 음수 (금융 여건 완화)."""
    return bool(anfci.iloc[-1] < 0)


def _vix_below_20(vix: pd.Series) -> bool:
    """VIX 20 미만 안정 구간 (골디락스 극도 안정 포함)."""
    return bool(vix.iloc[-1] < 20)


def _move_below_avg(move: pd.Series) -> bool:
    """MOVE 가용 기간 평균 이하."""
    if len(move) < 20:
        return False
    return bool(move.iloc[-1] < move.mean())


# ── 3단계 조건 (4개 중 3개 이상 → 3단계) ─────────────────────────

def _cli_expanding(cli: pd.Series) -> bool:
    """CLI 전월 대비 양수 (확장 추세 유지)."""
    if len(cli) < 2:
        return False
    return bool(cli.iloc[-1] >= cli.iloc[-2])


def _anfci_stable_or_rising(anfci: pd.Series) -> bool:
    """ANFCI 안정 또는 소폭 상승 (5주 변화 -0.3 ~ +0.8)."""
    if len(anfci) < 5:
        return False
    delta = float(anfci.iloc[-1] - anfci.iloc[-5])
    return bool(-0.3 <= delta <= 0.8)


def _vix_temp_spike_25_30(vix: pd.Series) -> bool:
    """VIX 일시적 25~30 스파이크."""
    return bool(25 <= vix.iloc[-1] <= 30)


def _move_short_term_rising(move: pd.Series) -> bool:
    """MOVE 5일 전 대비 상승."""
    if len(move) < 6:
        return False
    return bool(move.iloc[-1] > move.iloc[-6])


# ── 메인 분류 함수 ─────────────────────────────────────────────────

def classify_phase(
    cli: pd.Series,
    anfci: pd.Series,
    vix: pd.Series,
    move: pd.Series,
) -> str:
    """4단계 + 회피 분류. 우선순위: 회피 → 1단계 → 3단계 → 2단계."""
    avoidance = sum([
        _cli_declining(cli),
        _anfci_turning_positive(anfci),
        _vix_trending_up_or_30plus(vix),
    ])
    phase1 = sum([
        _cli_rebounding(cli),
        _anfci_peak_declining(anfci),
        _vix_cooling_from_high(vix),
        _move_peak_declining(move),
    ])
    phase3 = sum([
        _cli_expanding(cli),
        _anfci_stable_or_rising(anfci),
        _vix_temp_spike_25_30(vix),
        _move_short_term_rising(move),
    ])
    phase2 = sum([
        _cli_above_100_rising(cli),
        _anfci_negative(anfci),
        _vix_below_20(vix),
        _move_below_avg(move),
    ])

    logger.debug(f"단계 점수 — 회피:{avoidance} 1단계:{phase1} 3단계:{phase3} 2단계:{phase2}")

    if avoidance >= 2:
        return "회피"
    if phase1 >= 3:
        return "1단계"
    if _vix_temp_spike_25_30(vix) and phase3 >= 3:  # VIX 스파이크 필수
        return "3단계"
    if phase2 >= 3:
        return "2단계"
    return "불명확"