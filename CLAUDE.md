# 매크로 투자 통합 시스템 (Macro Dashboard)

## 프로젝트 기본 정보
- 목적: 거시경제 지표 기반 레버리지 ETF 투자 의사결정 보조 시스템
- 사용자: 한국 거주 레버리지 ETF 트레이더 (TQQQ, UPRO, KODEX 200 2x 등)
- 핵심: 매크로 단계 + 거시 체제 + 모멘텀 + 환율 종합 분석
- 중요 규칙: **매매 자동 실행 절대 금지** (의사결정 보조 도구)

## 엄격 준수 원칙 (Karpathy 4원칙)
1. Think Before Coding — 코드 작성 전 설계 먼저 제시, 사용자 확인 필수
2. Simplicity First — 최소한의 코드로 해결, 오버엔지니어링 금지
3. Surgical Changes — 필요한 부분만 수정
4. Goal-Driven Execution — 성공 기준 정의 후 테스트 통과해야 진행

## MVP 우선 전략
- Phase 0 완료 및 검증 전에는 Phase 1 이상 절대 진행 금지
- 각 Phase 종료 시 단위 테스트 + 사용자 승인 필수

## 기술 스택
- Python 3.10+
- Streamlit + Plotly
- yfinance, fredapi, pandas
- Telegram Bot + GitHub Actions
- pytest

## 코딩 규칙
- Type hints 필수
- 함수에 docstring 작성
- logging 적절히 사용
- `--dry-run` 옵션 지원
- 모든 알림에 "투자 자문 아님" 면책 문구 포함
- 불필요한 추상화, 미래 확장 기능 금지

## Claude에게 요청하는 사항
- 코드 작성 전 항상 설계안 먼저 제시
- 더 단순한 방법이 있으면 적극 제안
- 모호한 부분은 질문
- Phase 0 검증 전 다른 기능 미리 만들지 않기
