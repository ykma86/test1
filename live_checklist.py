"""Phase 10: 라이브 전환 체크리스트."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SHADOW_LOG = Path("state/shadow_log.jsonl")


def load_shadow_log() -> list[dict]:
    """shadow_log.jsonl 로드. 파일 없으면 빈 리스트."""
    if not SHADOW_LOG.exists():
        return []
    entries = []
    for line in SHADOW_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def check_run_count(entries: list[dict]) -> tuple[bool, str]:
    """총 실행 횟수 14회 이상."""
    n = len(entries)
    return n >= 14, f"총 실행 횟수: {n}회 (기준: 14+)"


def check_run_period(entries: list[dict]) -> tuple[bool, str]:
    """운영 기간 14일 이상."""
    if len(entries) < 2:
        return False, "운영 기간: 데이터 부족 (최소 2개 항목 필요)"
    first = datetime.fromisoformat(entries[0]["ts"])
    last  = datetime.fromisoformat(entries[-1]["ts"])
    days  = (last - first).days
    return days >= 14, f"운영 기간: {days}일 (기준: 14+)"


def check_alert_ratio(entries: list[dict]) -> tuple[bool, str]:
    """알림 발생 비율 50% 이하 (노이즈 방지)."""
    if not entries:
        return False, "알림 비율: 데이터 없음"
    fired = sum(1 for e in entries if e.get("alert_count", 0) > 0)
    ratio = fired / len(entries) * 100
    return ratio <= 50, f"알림 발생 비율: {ratio:.0f}% (기준: ≤50%)"


def check_error_ratio(entries: list[dict]) -> tuple[bool, str]:
    """오류 비율 10% 미만."""
    if not entries:
        return False, "오류 비율: 데이터 없음"
    errors = sum(1 for e in entries if e.get("error"))
    ratio = errors / len(entries) * 100
    return ratio < 10, f"오류 비율: {ratio:.0f}% (기준: <10%)"


def check_unclear_phase_ratio(entries: list[dict]) -> tuple[bool, str]:
    """불명확 Phase 비율 30% 미만."""
    if not entries:
        return False, "불명확 Phase 비율: 데이터 없음"
    unclear = sum(1 for e in entries if e.get("phase") == "불명확")
    ratio = unclear / len(entries) * 100
    return ratio < 30, f"불명확 Phase 비율: {ratio:.0f}% (기준: <30%)"


def check_tests() -> tuple[bool, str]:
    """단위 테스트 전체 통과."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
    )
    ok = result.returncode == 0
    lines = result.stdout.strip().splitlines()
    summary = lines[-1] if lines else "결과 없음"
    return ok, f"단위 테스트: {summary}"


CHECKS = [
    check_run_count,
    check_run_period,
    check_alert_ratio,
    check_error_ratio,
    check_unclear_phase_ratio,
]


def run_checklist() -> bool:
    """체크리스트 실행. True=GO, False=NO-GO."""
    print("\n" + "=" * 52)
    print("라이브 전환 체크리스트")
    print("=" * 52)

    entries = load_shadow_log()
    if not entries:
        print("⚠️  shadow_log.jsonl 없음")
        print("   Shadow 모드 14일 운영 후 다시 실행하세요.")
        print("   실행: python main.py --shadow")
        print("=" * 52 + "\n")
        return False

    results = []
    for check_fn in CHECKS:
        ok, msg = check_fn(entries)
        results.append(ok)
        print(f"{'[✓]' if ok else '[✗]'} {msg}")

    ok, msg = check_tests()
    results.append(ok)
    print(f"{'[✓]' if ok else '[✗]'} {msg}")

    print("-" * 52)
    failed = results.count(False)
    go = failed == 0
    verdict = "🟢 GO: 라이브 전환 가능" if go else f"🔴 NO-GO: {failed}개 항목 미충족"
    print(f"→ {verdict}")
    print("=" * 52 + "\n")
    return go


if __name__ == "__main__":
    sys.exit(0 if run_checklist() else 1)
