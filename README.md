# 매크로 투자 통합 대시보드 (Macro Dashboard)

레버리지 ETF 투자자를 위한 거시경제 기반 투자 의사결정 보조 시스템

## 주요 기능
- 매크로 단계 판정 (바닥 잡기 → 골디락스 → 눌림목 → 회피)
- 거시 체제 4사분면 분석 (골디락스, 리플레이션, 스태그플레이션, 디플레 침체)
- 모멘텀 기반 종목 추천 (TQQQ, SOXL, KODEX 레버리지 등)
- 실시간 알림 (Telegram)
- Streamlit 대시보드
- 백테스트 엔진

## 기술 스택
- Python 3.10+
- Streamlit + Plotly
- yfinance, fredapi
- GitHub Actions (스케줄러)
- Telegram Bot

## 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/ykma86/test1.git
cd test1

# 2. 가상환경 생성
python -m venv venv
venv\Scripts\activate     # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. Streamlit 대시보드 실행
streamlit run main.py

##프로젝트 구조
macro-dashboard/
├── CLAUDE.md
├── README.md
├── main.py
├── requirements.txt
├── config/
├── state/
├── alerts/
├── tests/
└── backtest/

##중요 주의사항

본 시스템은 투자 참고용 정보 제공 도구이며, 투자 권유나 자문이 아닙니다.
모든 매매 결정은 사용자 본인 판단으로 진행해주세요.
레버리지 ETF는 높은 변동성을 가지고 있으니 위험 관리를 철저히 하세요.

##개발 단계

Phase 0 (MVP): VIX 기반 최소 알림 시스템
Phase 1~10: 점진적 확장 예정
