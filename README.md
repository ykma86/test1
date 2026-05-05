# 매크로 투자 통합 대시보드

레버리지 ETF 투자자를 위한 **거시경제 기반 투자 의사결정 보조 시스템**

## 주요 기능
- 매크로 시장 단계 판정 (골디락스, 회피 등)
- 거시 체제 4사분면 분석
- 모멘텀 기반 종목 추천
- Telegram 실시간 알림
- Streamlit 대시보드
- 백테스트 엔진

## 기술 스택
- Python 3.10+
- Streamlit + Plotly
- yfinance, fredapi
- Telegram Bot
- GitHub Actions

## 주의사항
**본 시스템은 투자 참고용 정보 제공 도구일 뿐입니다.**  
모든 투자 결정은 사용자 본인 판단으로 진행하시기 바랍니다.  
레버리지 ETF는 높은 위험을 수반합니다.

## 개발 단계
- Phase 0 (MVP): VIX 기반 최소 알림 시스템
- Phase 1~10: 단계적 확장 예정

## 프로젝트 구조
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
