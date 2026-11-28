"""여러 화면에서 같이 쓰는 Streamlit 요소와 디자인 토큰.

디자인 기준: DESIGN.md (토큰 값을 바꾸면 DESIGN.md 3장도 함께 고칠 것)
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

# ---------------------------------------------------------------- 디자인 토큰 (DESIGN.md 3장)
FONT = "Paperlogy, sans-serif"
OLIVE = "#747F00"        # 7호선 올리브: 토글·라디오 등 글자가 아닌 UI
OLIVE_TEXT = "#5C6500"   # 올리브를 글자로 쓸 때 (카드 위 6.33:1)
BAND = "#667000"         # 역명판 노선 띠 (흰 글자 5.41:1)
NAVY = "#1F2A44"         # 본문
SECONDARY = "#4A5468"    # 보조 글
MUTED = "#5B6577"        # 흐린 글 (출처·주의)
PLATFORM = "#ECEEEA"     # 페이지 배경
CARD = "#FFFFFF"
HAIRLINE = "rgba(31,42,68,.08)"
GREY_SERIES = "#858C99"  # 그래프의 비교 계열 (흰 바탕 3.38:1)
# 혼잡 단계 (흰 카드 위 3:1 이상)
EASY = "#849349"         # 여유
MID = "#9C8F12"          # 보통
BUSY = "#B97F00"         # 붐빔
PACKED = "#B8322A"       # 매우 붐빔
LED = "#F2A900"          # 막차 전광판 글자 전용
LINE_COLORS = {"1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE",
               "5호선": "#996CAC", "6호선": "#CD7C2F", "7호선": BAND, "8호선": "#E6186C"}
CONGESTION_SCALE = [[0, "#F4F5F1"], [0.4, EASY], [0.75, BUSY], [1, PACKED]]
EASE = "cubic-bezier(0.22, 1, 0.36, 1)"
KST = ZoneInfo("Asia/Seoul")

pio.templates["metro"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=NAVY, size=13),
    colorway=[OLIVE, GREY_SERIES, NAVY, PACKED],
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=CARD,
    xaxis=dict(gridcolor="#E4E7E1", linecolor="#C9CEC4", zeroline=False, tickfont=dict(size=12, color=SECONDARY)),
    yaxis=dict(gridcolor="#E4E7E1", linecolor="#C9CEC4", zeroline=False, tickfont=dict(size=12, color=SECONDARY)),
    hoverlabel=dict(font_family=FONT),
    legend=dict(orientation="h", y=-0.25, x=0, font=dict(size=12, color=SECONDARY)),
    margin=dict(l=8, r=8, t=16, b=8),
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
        return "보통이에요", MID
    return "여유 있어요", EASY


LEVEL_SHORT = {"여유 있어요": "여유", "보통이에요": "보통", "붐벼요": "붐빔", "매우 붐벼요": "매우 붐빔"}


# ---------------------------------------------------------------- CSS (간격은 4px 단위)
_BASE_CSS = f"""
<style>
html, body, [data-testid="stApp"] {{ font-variant-numeric: tabular-nums; touch-action: manipulation; }}
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {{ text-wrap: balance; }}
.sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
           clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
/* 휴대폰: 본문 16px, 누르는 곳 44px 이상 (web-design-reviewer 점검 결과) */
@media (max-width: 640px) {{
  [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ font-size: 16px; }}
}}
@media (pointer: coarse) {{
  [data-testid="stButtonGroup"] button {{ min-height: 44px; }}
  [data-testid="stExpander"] summary {{ min-height: 44px; }}
  [data-baseweb="select"] > div, [data-testid="stNumberInput"] input,
  [data-testid="stTimeInput"] input {{ min-height: 44px; }}
  [data-testid="stNumberInput"] button {{ min-width: 44px; min-height: 44px; }}
  [data-testid="stCheckbox"] label {{ min-height: 44px; align-items: center; }}
  .modebar-container {{ display: none !important; }}  /* 그래프 도구막대는 휴대폰에서 숨김 */
}}
.block-container {{ padding-top: 72px; padding-bottom: 64px; max-width: 860px; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 16px; padding-right: 16px; padding-top: 64px; }}
}}
[data-testid="stMain"] h1 {{ font-size: clamp(28px, 6.5vw, 36px); line-height: 1.2; font-weight: 600; }}
:focus-visible {{ outline: 3px solid {OLIVE} !important; outline-offset: 2px; }}

/* 역명판 (시그니처: 노선 띠) */
.sign {{ background: {CARD}; border: 1px solid {HAIRLINE}; border-radius: 12px; overflow: hidden;
        margin: 0 0 24px 0; }}
.sign-main {{ display: flex; align-items: center; gap: 16px; padding: 20px 20px 16px; }}
.sign-line {{ flex: none; width: 44px; height: 44px; border-radius: 50%; color: #fff;
             display: grid; place-items: center; font: 600 20px {FONT}; }}
[data-testid="stMarkdownContainer"] h1.sign-name {{ font-family: {FONT}; font-weight: 600; color: {NAVY};
             font-size: clamp(36px, 10vw, 48px); line-height: 1.05; letter-spacing: -0.02em;
             margin: 0; padding: 0; }}
.sign-name a {{ display: none; }}  /* Streamlit 제목 앵커 숨김 */
.sign-band {{ display: flex; justify-content: space-between; color: #fff; font-size: 15px; font-weight: 500;
             padding: 8px 20px; }}
.sign-band span:empty::before {{ content: "\\00a0"; }}

/* 판정 문장 */
[data-testid="stMarkdownContainer"] p.verdict {{ font-family: {FONT}; font-weight: 600;
           font-size: clamp(28px, 7.2vw, 36px); line-height: 1.25; letter-spacing: -0.02em;
           margin: 0 0 8px 0; color: {NAVY}; text-wrap: balance; }}
[data-testid="stMarkdownContainer"] p.advice {{ font-size: 17px; line-height: 1.6; margin: 0 0 24px 0;
           max-width: 34em; color: {NAVY}; }}
[data-testid="stMarkdownContainer"] p.advice b {{ font-weight: 600; }}

/* 시간대 혼잡 막대 (빛나는 순간 1) */
.strip-card {{ background: {CARD}; border: 1px solid {HAIRLINE}; border-radius: 12px;
              padding: 28px 16px 16px; margin: 0 0 16px 0; }}
.strip {{ display: grid; grid-template-columns: repeat(20, 1fr); gap: 4px; align-items: end; height: 96px; }}
.strip div {{ border-radius: 4px 4px 0 0; position: relative; min-height: 4px; }}
.strip .target {{ box-shadow: inset 0 -3px 0 {NAVY}; }}  /* 바깥 외곽선은 옆 막대의 "추천" 글자와 겹쳐서 안쪽 밑줄로 */
.strip .best::after {{ content: "추천"; position: absolute; top: -20px; left: 50%;
                       transform: translateX(-50%); font-size: 12px; color: {NAVY}; white-space: nowrap;
                       font-weight: 600; background: {CARD}; padding: 0 4px; border-radius: 4px; }}
.strip-axis {{ display: grid; grid-template-columns: repeat(20, 1fr); font-size: 12px; color: {SECONDARY};
              margin-top: 4px; }}
.strip-mark {{ display: grid; grid-template-columns: repeat(20, 1fr); font-size: 12px;
               color: {NAVY}; font-weight: 600; margin-top: 4px; min-height: 16px; }}
.strip-mark span {{ text-align: center; white-space: nowrap; overflow: visible; }}
.strip-legend {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: {SECONDARY};
                margin: 12px 0 0; }}
.strip-legend i {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px;
                   vertical-align: -1px; margin-right: 4px; }}
[data-testid="stMarkdownContainer"] p.note {{ font-size: 13px; color: {MUTED}; margin-top: 24px; }}
@media (prefers-reduced-motion: no-preference) {{
  [data-testid="stExpander"] summary {{ transition: background-color 160ms {EASE}; }}
}}
</style>
"""


def base_css():
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- 데이터
@st.cache_data(show_spinner="데이터 불러오는 중…")
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
<div class="sign" aria-label="{html.escape(line)} {html.escape(name)}역">
  <div class="sign-main">
    <div class="sign-line" style="background:{color}">{num}</div>
    <h1 class="sign-name">{html.escape(name)}</h1>
  </div>
  <div class="sign-band" style="background:{color}"><span>{prev_s}</span><span>{next_s}</span></div>
</div>""", unsafe_allow_html=True)


def congestion_strip(profile, target_hour: int | None = None, best_hour: int | None = None):
    """05~24시 혼잡 막대. profile: hour, mean 컬럼."""
    peak = max(profile["mean"].max(), 1)
    bars, items = [], []
    for h, m in zip(profile["hour"], profile["mean"]):
        r = m / peak
        _, color = level_of(r)
        cls = " ".join(c for c, on in (("target", h == target_hour), ("best", h == best_hour)) if on)
        word, _ = level_of(r)  # noqa: F841 (아래 숨김 목록에서 씀)
        bars.append(f'<div class="{cls}" style="height:{max(r, .04) * 100:.0f}%;background:{color}" '
                    f'title="{hour_label(h)} 평균 {m:,.0f}명"></div>')
        extra = " (고른 시간)" if h == target_hour else ""
        extra += " (추천)" if h == best_hour else ""
        items.append(f"<li>{hour_label(h)}: {LEVEL_SHORT[word]}, 평균 {m:,.0f}명{extra}</li>")
    axis = "".join(f"<span>{h:02d}</span>" if h in (5, 9, 12, 15, 18, 21, 24) else "<span></span>"
                   for h in profile["hour"])
    mark = "".join("<span>▲ 고른 시간</span>" if h == target_hour and h != best_hour else "<span></span>"
                   for h in profile["hour"])
    st.markdown(f"""
<div class="strip-card">
<div class="strip" aria-hidden="true">{''.join(bars)}</div>
<ul class="sr-only" aria-label="05시부터 24시까지 시간대별 혼잡도">{''.join(items)}</ul>
<div class="strip-axis" aria-hidden="true">{axis}</div>
<div class="strip-mark" aria-hidden="true">{mark}</div>
<div class="strip-legend"><span><i style="background:{EASY}"></i>여유</span><span><i style="background:{MID}"></i>보통</span>
<span><i style="background:{BUSY}"></i>붐빔</span><span><i style="background:{PACKED}"></i>매우 붐빔</span></div>
</div>
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


def choice(label: str, options: list, default=None, format_func=None, container=st, key=None):
    """한 개만 고르는 선택지. 라디오 대신 segmented_control (DESIGN.md 4장).

    다시 눌러 선택을 풀면 None이 되므로 기본값으로 돌려준다.
    """
    default = options[0] if default is None else default
    kwargs = {"format_func": format_func} if format_func else {}
    value = container.segmented_control(label, options, default=default, selection_mode="single",
                                        key=key, **kwargs)
    return default if value is None else value
