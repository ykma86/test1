"""Phase 6: Streamlit 매크로 투자 대시보드."""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from classifier import classify_phase
from falling_knife import evaluate as fk_evaluate
from fetchers import fetch_all, fetch_series, fetch_move_series
from momentum import scan_all
from regime import REGIME_EMOJI, classify_regime, get_position_guide

try:
    FRED_KEY = st.secrets.get("FRED_API_KEY", "")
except Exception:
    FRED_KEY = ""
FRED_KEY = FRED_KEY or os.environ.get("FRED_API_KEY", "")
STATE_FILE = Path("state/previous_state.json")

PHASE_EMOJI = {"회피": "🔴", "1단계": "🟡", "2단계": "🟢", "3단계": "🟠", "불명확": "⚪"}
DISCLAIMER = "⚠️ 본 시스템은 정보 제공 도구이며 투자 자문이 아닙니다."

st.set_page_config(page_title="매크로 대시보드", layout="wide", page_icon="📊")
st.title("📊 매크로 투자 대시보드")
st.caption(DISCLAIMER)

# ── 데이터 fetch (1시간 캐시) ──────────────────────────────────

@st.cache_data(ttl=3600)
def load_indicators() -> dict:
    return fetch_all(FRED_KEY) if FRED_KEY else {}


@st.cache_data(ttl=3600)
def load_phase() -> str:
    if not FRED_KEY:
        return "불명확"
    cli   = fetch_series("OECDLOLITOAASTSAM", FRED_KEY, n_periods=6)
    anfci = fetch_series("ANFCI",             FRED_KEY, n_periods=8)
    vix_s = fetch_series("VIXCLS",            FRED_KEY, n_periods=40)
    move  = fetch_move_series(n_periods=400)
    if cli is None or anfci is None or vix_s is None:
        return "불명확"
    return classify_phase(cli, anfci, vix_s, move if move is not None else pd.Series(dtype=float))


@st.cache_data(ttl=3600)
def load_regime() -> str:
    if not FRED_KEY:
        return "불명확"
    cli     = fetch_series("OECDLOLITOAASTSAM", FRED_KEY, n_periods=6)
    bei_raw = fetch_series("T5YIE",             FRED_KEY, n_periods=200)
    if cli is None or bei_raw is None:
        return "불명확"
    bei = bei_raw.resample("ME").last().iloc[-8:]
    if len(bei) < 7:
        return "불명확"
    return classify_regime(cli, bei)


@st.cache_data(ttl=3600)
def load_momentum() -> list:
    return scan_all()


@st.cache_data(ttl=3600)
def load_vix_history() -> pd.Series:
    data = yf.Ticker("^VIX").history(period="1y")
    return data["Close"].dropna()


@st.cache_data(ttl=3600)
def load_spy_vix_for_fk() -> tuple:
    spy = yf.Ticker("SPY").history(period="10d")["Close"].dropna()
    vix = yf.Ticker("^VIX").history(period="10d")["Close"].dropna()
    return spy, vix


# ── 1. 신호등 ─────────────────────────────────────────────────

with st.spinner("데이터 로드 중..."):
    phase  = load_phase()
    regime = load_regime()

col1, col2, col3, col4 = st.columns(4)
col1.metric("매크로 단계", f"{PHASE_EMOJI.get(phase,'⚪')} {phase}")
col2.metric("거시 체제", f"{REGIME_EMOJI.get(regime,'⚪')} {regime}")
col3.metric("포지션 가이드", get_position_guide(regime))

# 떨어지는 칼날 상태
try:
    spy_s, vix_s = load_spy_vix_for_fk()
    hy_s = fetch_series("BAMLH0A0HYM2", FRED_KEY, n_periods=10) if FRED_KEY else None
    fk = fk_evaluate(spy_s, vix_s, hy_s if hy_s is not None else pd.Series(dtype=float))
    fk_status = "🔪 활성" if fk["active"] else "✅ 비활성"
except Exception:
    fk_status = "⚪ 확인불가"
col4.metric("떨어지는 칼날", fk_status)

st.divider()

# ── 2. 핵심 지표 12개 ─────────────────────────────────────────

st.subheader("핵심 지표")
indicators = load_indicators()

INDICATOR_LABELS = {
    "cli": "OECD CLI", "anfci": "ANFCI", "nfci": "NFCI", "vix_fred": "VIX (FRED)",
    "hy_spread": "HY 스프레드", "t10y2y": "10Y-2Y", "t10y3m": "10Y-3M", "dxy": "DXY",
    "usdkrw": "USD/KRW", "bei_5y": "BEI 5Y", "cpi_yoy": "CPI YoY", "move": "MOVE",
}
cols = st.columns(6)
for i, (key, label) in enumerate(INDICATOR_LABELS.items()):
    val = indicators.get(key)
    display = f"{val:.2f}" if val is not None else "N/A"
    cols[i % 6].metric(label, display)

st.subheader("확장 지표")
EXTENDED_DISPLAY: dict[str, tuple[str, object]] = {
    "ism_pmi": ("ISM PMI",      lambda v: f"{v:.1f}"),
    "nfp_chg": ("NFP 변화(K)",  lambda v: f"{v:+,.0f}K"),
    "fed_bs":  ("Fed BS(조$)",  lambda v: f"${v:.1f}T"),
    "m2_yoy":  ("M2 YoY",       lambda v: f"{v:+.1f}%"),
    "wti":     ("WTI($)",        lambda v: f"${v:.0f}"),
    "copper":  ("구리($/lb)",    lambda v: f"${v:.2f}"),
}
ext_cols = st.columns(6)
for i, (key, (label, fmt)) in enumerate(EXTENDED_DISPLAY.items()):
    val = indicators.get(key)
    display = fmt(val) if val is not None else "N/A"
    ext_cols[i].metric(label, display)

st.divider()

# ── 3. VIX 추세 차트 + 4사분면 ────────────────────────────────

col_chart, col_quad = st.columns([2, 1])

with col_chart:
    st.subheader("VIX 1년 추세")
    vix_hist = load_vix_history()
    fig_vix = go.Figure()
    fig_vix.add_trace(go.Scatter(x=vix_hist.index, y=vix_hist.values, mode="lines",
                                  line=dict(color="#ef5350"), name="VIX"))
    for level, color, label in [(20, "orange", "VIX 20"), (25, "red", "VIX 25"), (30, "darkred", "VIX 30")]:
        fig_vix.add_hline(y=level, line_dash="dash", line_color=color,
                          annotation_text=label, annotation_position="right")
    fig_vix.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis_title=None, yaxis_title="VIX")
    st.plotly_chart(fig_vix, use_container_width=True)

with col_quad:
    st.subheader("거시 체제 4사분면")
    QUAD_POS = {
        "골디락스":    (1, 1),
        "리플레이션":  (-1, 1),
        "침체":        (1, -1),
        "스태그플레이션": (-1, -1),
    }
    fig_q = go.Figure()
    colors = {"골디락스": "#4caf50", "리플레이션": "#ff9800", "침체": "#2196f3", "스태그플레이션": "#f44336"}
    for name, (x, y) in QUAD_POS.items():
        is_current = (name == regime)
        fig_q.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=60 if is_current else 40, color=colors[name],
                        opacity=1.0 if is_current else 0.3,
                        line=dict(width=3 if is_current else 0, color="white")),
            text=[name], textposition="middle center",
            textfont=dict(size=10, color="white"),
            showlegend=False,
        ))
    fig_q.add_hline(y=0, line_color="gray", line_width=1)
    fig_q.add_vline(x=0, line_color="gray", line_width=1)
    fig_q.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(range=[-2, 2], showticklabels=False, title="성장"),
        yaxis=dict(range=[-2, 2], showticklabels=False, title="인플레"),
    )
    fig_q.add_annotation(x=1.5, y=-1.8, text="성장↑", showarrow=False, font=dict(size=10))
    fig_q.add_annotation(x=-1.5, y=-1.8, text="성장↓", showarrow=False, font=dict(size=10))
    fig_q.add_annotation(x=-1.8, y=1.5, text="인플↑", showarrow=False, font=dict(size=10), textangle=-90)
    fig_q.add_annotation(x=-1.8, y=-1.5, text="인플↓", showarrow=False, font=dict(size=10), textangle=-90)
    st.plotly_chart(fig_q, use_container_width=True)

st.divider()

# ── 4. 모멘텀 랭킹 + 환율 모니터 ──────────────────────────────

col_mom, col_fx = st.columns([3, 1])

with col_mom:
    st.subheader("모멘텀 랭킹")
    with st.spinner("종목 스캔 중..."):
        mom_results = load_momentum()
    if mom_results:
        df = pd.DataFrame([{"종목": r["ticker"], "점수": f"{r['score']}/7",
                             "판정": "🟢 매수" if r["score"] >= 5 else ("🟡 중립" if r["score"] >= 3 else "🔴 회피")}
                           for r in mom_results])
        st.dataframe(df, use_container_width=True, hide_index=True, height=280)
    else:
        st.info("모멘텀 데이터 없음")

with col_fx:
    st.subheader("환율 모니터")
    usdkrw = indicators.get("usdkrw")
    dxy    = indicators.get("dxy")
    if usdkrw:
        color = "inverse" if usdkrw >= 1450 else "normal"
        st.metric("USD/KRW", f"{usdkrw:,.0f}원",
                  delta="⚠️ 미국 진입 부담" if usdkrw >= 1450 else
                        ("✅ 환노출 OK" if usdkrw <= 1300 else "🔄 환헤지 검토"))
    if dxy:
        st.metric("DXY", f"{dxy:.1f}")
    st.caption("1,450↑ 미국 비중 축소\n1,300↓ 환노출 ETF 유리")

st.divider()

# ── 5. 포지션 계산기 + 데이터 신선도 ──────────────────────────

col_pos, col_fresh = st.columns([2, 1])

with col_pos:
    st.subheader("포지션 계산기 (레버리지)")
    entry = st.number_input("진입 가격", min_value=0.1, value=100.0, step=0.5)
    size  = st.number_input("투자 금액 (만원)", min_value=10, value=1000, step=100)
    if entry > 0:
        col_a, col_b = st.columns(2)
        col_a.metric("손절 (-10%)",  f"{entry * 0.90:,.2f}")
        col_a.metric("트레일링 (-7%)", f"{entry * 0.93:,.2f}")
        col_b.metric("익절 1차 (+30%)", f"{entry * 1.30:,.2f}")
        col_b.metric("익절 2차 (+60%)", f"{entry * 1.60:,.2f}")
        st.caption(f"비중 20% 기준 투입: {size * 0.2:,.0f}만원")

with col_fresh:
    st.subheader("데이터 신선도")
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        last_updated = state.get("last_updated", "알 수 없음")
        st.metric("마지막 알림 실행", last_updated[:16] if last_updated else "없음")
        st.metric("저장된 단계", state.get("phase", "불명확"))
        st.metric("저장된 체제", state.get("regime", "불명확"))
    else:
        st.info("state 파일 없음")
    if not FRED_KEY:
        st.warning("FRED_API_KEY 미설정 — 일부 데이터 표시 불가")
