"""여러 화면에서 같이 쓰는 Streamlit 요소와 디자인 토큰.

디자인 기준: docs/superpowers/specs/2026-11-26-ui-redesign-design.md
"""
from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from src.config import TARGET_STATION, hour_label
from src.data_loader import load_data

# ---------------------------------------------------------------- 디자인 토큰
OLIVE = "#747F00"      # 7호선
NAVY = "#1F2A44"       # 안내판 글자
PLATFORM = "#ECEEEA"   # 승강장 회색
EASY = "#C9D38A"       # 여유
BUSY = "#E8B931"       # 혼잡
PACKED = "#B8322A"     # 매우 혼잡
LED = "#F2A900"        # 막차 전광판
LINE_COLORS = {"1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE",
               "5호선": "#996CAC", "6호선": "#CD7C2F", "7호선": OLIVE, "8호선": "#E6186C"}
CONGESTION_SCALE = [[0, "#F4F5F1"], [0.35, EASY], [0.7, BUSY], [1, PACKED]]
KST = ZoneInfo("Asia/Seoul")

pio.templates["metro"] = go.layout.Template(layout=dict(
    font=dict(family="Pretendard, sans-serif", color=NAVY, size=13),
    colorway=[OLIVE, NAVY, BUSY, PACKED, "#6B7A8F", EASY],
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
    xaxis=dict(gridcolor="#E4E7E1", linecolor="#C9CEC4", zeroline=False),
    yaxis=dict(gridcolor="#E4E7E1", linecolor="#C9CEC4", zeroline=False),
    hoverlabel=dict(font_family="Pretendard, sans-serif"),
    legend=dict(orientation="h", y=-0.25, x=0),
    margin=dict(l=8, r=8, t=36, b=8),
))
pio.templates.default = "plotly_white+metro"


def now_kst() -> datetime:
    return datetime.now(KST)


def level_of(ratio: float) -> tuple[str, str]:
    """상대 혼잡도(0~1) -> (문구, 색)"""
    if ratio >= 0.8:
        return "매우 붐벼요", PACKED
    if ratio >= 0.55:
        return "붐벼요", BUSY
    if ratio >= 0.3:
        return "보통이에요", EASY
    return "여유 있어요", "#DDE3C2"


# ---------------------------------------------------------------- CSS
_BASE_CSS = f"""
<style>
.block-container {{ padding-top: 4.5rem; padding-bottom: 4rem; max-width: 860px; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 4rem; }}
}}
[data-testid="stMain"] h1 {{ font-size: clamp(1.7rem, 6.5vw, 2.4rem); line-height: 1.2; }}
:focus-visible {{ outline: 3px solid {OLIVE} !important; outline-offset: 2px; }}

/* 역명판 */
.sign {{ background: #FFFFFF; border: 1px solid #C9CEC4; border-radius: 10px; overflow: hidden;
        margin: 0 0 1.4rem 0; }}
.sign-main {{ display: flex; align-items: center; gap: .9rem; padding: 1.1rem 1.2rem .9rem; }}
.sign-line {{ flex: none; width: 2.6rem; height: 2.6rem; border-radius: 50%; color: #fff;
             display: grid; place-items: center; font: 700 1.25rem Pretendard, sans-serif; }}
.sign-name {{ font-family: SeoulNamsan, Pretendard, sans-serif; color: {NAVY};
             font-size: clamp(2rem, 9vw, 3.1rem); line-height: 1.05; letter-spacing: -0.01em; }}
.sign-band {{ display: flex; justify-content: space-between; color: #fff; font-size: .95rem;
             padding: .45rem 1.2rem; }}
.sign-band span:empty::before {{ content: "\\00a0"; }}

/* 판정 문장 */
[data-testid="stMarkdownContainer"] p.verdict {{ font-family: SeoulNamsan, Pretendard, sans-serif; font-size: clamp(1.7rem, 7.2vw, 2.2rem);
           line-height: 1.25; margin: 0 0 .5rem 0; color: {NAVY}; }}
[data-testid="stMarkdownContainer"] p.advice {{ font-size: 1.05rem; line-height: 1.6; margin: 0 0 1.6rem 0; max-width: 34em; }}
[data-testid="stMarkdownContainer"] p.advice b {{ font-weight: 700; }}

/* 시간대 혼잡 막대 */
.strip {{ display: grid; grid-template-columns: repeat(20, 1fr); gap: 3px; align-items: end;
         height: 92px; margin-top: .4rem; }}
.strip div {{ border-radius: 3px 3px 0 0; position: relative; min-height: 4px; }}
.strip .target {{ outline: 2px solid {NAVY}; outline-offset: 1px; }}
.strip .best::after {{ content: "추천"; position: absolute; top: -1.35rem; left: 50%;
                       transform: translateX(-50%); font-size: .72rem; color: {NAVY}; white-space: nowrap;
                       font-weight: 700; }}
.strip-axis {{ display: grid; grid-template-columns: repeat(20, 1fr); font-size: .72rem; color: #5B6577;
              margin-top: .25rem; }}
.strip-mark {{ display: grid; grid-template-columns: repeat(20, 1fr); font-size: .72rem;
               color: {NAVY}; font-weight: 700; margin-top: .1rem; }}
.strip-mark span {{ text-align: center; white-space: nowrap; overflow: visible; }}
[data-testid="stMarkdownContainer"] p.strip-legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: .8rem; color: #4A5468; margin: .6rem 0 0; }}
.strip-legend i {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 2px;
                   vertical-align: -1px; margin-right: .3rem; }}
[data-testid="stMarkdownContainer"] p.note {{ font-size: .82rem; color: #5B6577; margin-top: 1.4rem; }}
</style>
"""


def base_css():
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- 데이터
@st.cache_data(show_spinner="데이터 불러오는 중...")
def get_data():
    return load_data()


@st.cache_data
def line_neighbors() -> dict:
    """역명 -> (호선, 이전역, 다음역). 노선 순서 데이터(막차 기능용)를 재사용한다."""
    from src.transit import load_transit

    stations, _, _ = load_transit(include_bus=False)
    out = {}
    for line, g in stations.sort_values("seq").groupby("line"):
        names = list(g["name"] if "name" in g else g["station"])
        for i, n in enumerate(names):
            out.setdefault(n, (line, names[i - 1] if i > 0 else "", names[i + 1] if i + 1 < len(names) else ""))
    return out


# ---------------------------------------------------------------- 조각
def station_sign(name: str, line: str | None = None):
    """서울 지하철 역명판. ◀ 이전역 / 다음역 ▶ 은 노선 데이터가 있을 때만."""
    nb = line_neighbors().get(name)
    line = line or (nb[0] if nb else "")
    color = LINE_COLORS.get(line, NAVY)
    num = "".join(ch for ch in line if ch.isdigit()) or "·"
    prev_s = f"◀ {html.escape(nb[1])}" if nb and nb[1] else ""
    next_s = f"{html.escape(nb[2])} ▶" if nb and nb[2] else ""
    st.markdown(f"""
<div class="sign" role="img" aria-label="{html.escape(line)} {html.escape(name)}역">
  <div class="sign-main">
    <div class="sign-line" style="background:{color}">{num}</div>
    <div class="sign-name">{html.escape(name)}</div>
  </div>
  <div class="sign-band" style="background:{color}"><span>{prev_s}</span><span>{next_s}</span></div>
</div>""", unsafe_allow_html=True)


def congestion_strip(profile, target_hour: int | None = None, best_hour: int | None = None):
    """05~24시 혼잡 막대. profile: hour, mean 컬럼."""
    peak = max(profile["mean"].max(), 1)
    bars = []
    for h, m in zip(profile["hour"], profile["mean"]):
        r = m / peak
        _, color = level_of(r)
        cls = " ".join(c for c, on in (("target", h == target_hour), ("best", h == best_hour)) if on)
        bars.append(f'<div class="{cls}" style="height:{max(r, .04) * 100:.0f}%;background:{color}" '
                    f'title="{hour_label(h)} 평균 {m:,.0f}명"></div>')
    axis = "".join(f"<span>{h:02d}</span>" if h in (5, 9, 12, 15, 18, 21, 24) else "<span></span>"
                   for h in profile["hour"])
    mark = "".join("<span>▲ 고른 시간</span>" if h == target_hour and h != best_hour else "<span></span>"
                   for h in profile["hour"])
    st.markdown(f"""
<div class="strip" role="img" aria-label="시간대별 혼잡도 막대">{''.join(bars)}</div>
<div class="strip-axis" aria-hidden="true">{axis}</div>
<div class="strip-mark" aria-hidden="true">{mark}</div>
<p class="strip-legend"><span><i style="background:#DDE3C2"></i>여유</span><span><i style="background:{EASY}"></i>보통</span>
<span><i style="background:{BUSY}"></i>붐빔</span><span><i style="background:{PACKED}"></i>매우 붐빔</span></p>
""", unsafe_allow_html=True)


def sample_note(is_sample: bool):
    if is_sample:
        st.markdown('<p class="note">지금은 앱 시험용 가짜 데이터예요. 실제 승하차 CSV를 넣으면 실제 분석으로 바뀝니다.</p>',
                    unsafe_allow_html=True)


def sidebar(show_year=True):
    """분석 화면용 사이드바: 역/연도 선택. (df, station, year) 반환"""
    base_css()
    df, is_sample = get_data()
    with st.sidebar:
        if is_sample:
            st.warning("시험용 가짜 데이터로 보는 중이에요. `data/processed/subway_clean.csv`를 만들면 실제 데이터로 바뀝니다.")
        stations = sorted(df["station"].unique())
        if "station" not in st.session_state:
            st.session_state["station"] = TARGET_STATION if TARGET_STATION in stations else stations[0]
        station = st.selectbox("역", stations, key="station")
        year = None
        if show_year:
            years = sorted(df["year"].unique())
            year = st.selectbox("연도", ["전체"] + years, index=len(years), key="year")
            year = None if year == "전체" else year
        st.caption(f"데이터 기간 {df['date'].min():%Y.%m.%d} ~ {df['date'].max():%Y.%m.%d}")
    if year is not None:
        df = df[df["year"] == year]
    return df, station, year
