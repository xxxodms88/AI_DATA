"""막차 놓쳤을 때: 지하철·심야버스로 최대한 가까이 간 뒤 남은 거리만 택시"""
import html
from datetime import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import TARGET_STATION
from src.night_route import plan, summary
from src.transit import Network, load_transit, parse_time
from src.ui import LED, NAVY, base_css, now_kst

MODE_COLOR = {"지하철": "#A3AE2A", "심야버스": "#5B8FD9", "택시": LED, "도보": "#B8C0CC"}
NIGHT_BG = "#16213A"

NIGHT_CSS = f"""
<style>
[data-testid="stApp"], [data-testid="stHeader"] {{ background: {NIGHT_BG}; }}
[data-testid="stMain"] p, [data-testid="stMain"] label, [data-testid="stMain"] h1,
[data-testid="stMain"] h2, [data-testid="stMain"] h3, [data-testid="stMain"] li,
[data-testid="stMain"] [data-testid="stWidgetLabel"] p, [data-testid="stMain"] summary span,
[data-testid="stMain"] [data-testid="stCaptionContainer"] {{ color: #E4E8F0; }}
[data-testid="stMain"] [data-testid="stExpander"] details {{ border-color: #33405E; }}
[data-testid="stMain"] [data-testid="stAlert"] p {{ color: {NAVY}; }}
[data-testid="stTopNav"] a, [data-testid="stTopNav"] p, [data-testid="stTopNav"] span,
[data-testid="stTopNavSection"] {{ color: #DCE2EC !important; }}
[data-testid="stMarkdownContainer"] p.night-title {{ font-family: SeoulNamsan, Pretendard, sans-serif; font-size: clamp(1.7rem, 7vw, 2.3rem);
               color: #FFFFFF; margin: 0 0 .3rem; }}
[data-testid="stMarkdownContainer"] p.night-sub {{ color: #AEB8CB !important; margin: 0 0 1.2rem; max-width: 34em; }}

/* 막차 안내 전광판 */
.board {{ background: #000; border-radius: 8px; padding: 1rem 1.1rem 1.1rem; margin: 1.2rem 0 .9rem;
         border: 2px solid #2C2C2C;
         background-image: radial-gradient(rgba(255,255,255,.05) 1px, transparent 1.2px);
         background-size: 4px 4px; }}
.board-head {{ color: {LED}; opacity: .75; font-size: .85rem; margin-bottom: .6rem; }}
.board-row {{ display: grid; grid-template-columns: 4.2rem 1fr; gap: .6rem; color: {LED};
             font-weight: 600; font-size: 1.08rem; line-height: 1.45; padding: .2rem 0;
             font-variant-numeric: tabular-nums; text-shadow: 0 0 6px rgba(242,169,0,.45); }}
.board-row .what small {{ display: block; font-weight: 400; opacity: .8; font-size: .85rem; }}
[data-testid="stMarkdownContainer"] p.fare {{ font-family: SeoulNamsan, Pretendard, sans-serif; color: #fff; font-size: clamp(1.6rem, 7vw, 2.2rem);
        margin: .2rem 0 .1rem; }}
[data-testid="stMarkdownContainer"] p.fare-sub {{ color: #C9D1DF !important; margin: 0 0 1rem; }}
[data-testid="stMarkdownContainer"] p.fare-sub b {{ color: {LED}; }}
@media (prefers-reduced-motion: no-preference) {{
  .board {{ animation: boardOn .5s ease-out; }}
  @keyframes boardOn {{ from {{ opacity: .2; }} to {{ opacity: 1; }} }}
}}
</style>
"""


@st.cache_resource(show_spinner="노선·시간표 불러오는 중...")
def get_network(include_bus: bool):
    stations, timetable, state = load_transit(include_bus=include_bus)
    return Network(stations, timetable), state


base_css()
st.markdown(NIGHT_CSS, unsafe_allow_html=True)
st.markdown('<p class="night-title">막차 놓쳤을 때</p>'
            '<p class="night-sub">지하철과 심야버스로 갈 수 있는 데까지 간 다음, 남은 거리만 택시를 타는 가장 싼 방법을 찾아요.</p>',
            unsafe_allow_html=True)

answer = st.container()  # 답을 위에 보여주고, 입력은 그 아래에 둔다
st.markdown('<p class="night-sub" style="margin-top:1rem">출발·도착 바꾸기</p>', unsafe_allow_html=True)
use_bus = st.toggle("심야버스도 탈게요", value=True)
net, state = get_network(use_bus)

subway_names = sorted({net.names[n] for n in net.coords if net.modes[n] == "지하철"})
now = now_kst()
late = now.hour >= 22 or now.hour < 4
default_t = time(now.hour, now.minute - now.minute % 5) if late else time(0, 30)

c1, c2 = st.columns(2)
origin = c1.selectbox("지금 있는 역", subway_names,
                      index=subway_names.index(TARGET_STATION) if TARGET_STATION in subway_names else 0)
dep_time = c2.time_input("출발 시각", value=default_t, step=300)
c3, c4 = st.columns([3, 2])
dest_station = c3.selectbox("집에서 가까운 역", subway_names,
                            index=subway_names.index("노원") if "노원" in subway_names else 0)
off = c4.number_input("역에서 집까지(km)", 0.0, 10.0, 1.5, 0.5)
lat0, lon0 = net.coords[net.nodes_of(dest_station)[0]]
dest = (lat0 + off / 111.0, lon0)  # 역에서 북쪽으로 off km 떨어진 지점으로 근사

with st.expander("더 정확하게"):
    if st.checkbox("집 좌표 직접 넣기"):
        d1, d2 = st.columns(2)
        dest = (d1.number_input("위도", value=dest[0], format="%.4f"),
                d2.number_input("경도", value=dest[1], format="%.4f"))
    outside = st.checkbox("집이 서울 밖이에요 (시계외 할증 20%)")
    time_value = st.select_slider("빨리 가는 것도 중요해요 (1분을 몇 원으로 칠지)",
                                  options=[0, 50, 100, 200, 300, 500], value=0,
                                  help="0이면 무조건 가장 싼 방법. 올릴수록 조금 비싸도 빨리 도착하는 방법을 골라요.")


depart = parse_time(dep_time.strftime("%H:%M"))
df = plan(net, origin, dest, depart, outside, time_value)
if df.empty:
    st.error("출발역에서 갈 수 있는 경로가 없어요. 출발역이나 시각을 바꿔 보세요.")
    st.stop()

with answer:
    if not late:
        st.caption(f"지금은 심야가 아니라서 {default_t:%H:%M} 출발 기준으로 보여줘요. 아래에서 출발 시각을 바꿀 수 있어요.")
    s = summary(df)
    best = s["best"]
    rows = []
    for leg in best["_legs"]:
        rows.append((leg["board"], f'{html.escape(leg["from"])} → {html.escape(leg["to"])}',
                     f'{html.escape(leg["line"])} 탑승, {leg["alight"]} 하차'))
    last = "걸어서" if best["마지막 이동"] == "도보" else f"택시 {best['택시 거리(km)']}km"
    where = best["하차 위치"].replace(" (바로 택시)", "")
    rows.append((best["하차 시각"] if best["_legs"] else dep_time.strftime("%H:%M"),
                 f"{html.escape(where)}에서 {last}",
                 f"{best['할증']} 할증" if best["마지막 이동"] == "택시" and best["할증"] != "일반" else ""))
    rows.append((best["도착 예상"], "집 도착", f"약 {best['소요(분)']}분"))
    board_rows = "".join(
        f'<div class="board-row"><span>{t}</span><span class="what">{w}<small>{sm}</small></span></div>'
        for t, w, sm in rows)
    st.markdown(f'<div class="board" role="region" aria-label="추천 경로"><div class="board-head">'
                f'{html.escape(origin)}에서 {html.escape(dest_station)} 근처 집까지</div>'
                f'{board_rows}</div>', unsafe_allow_html=True)

    fare_sub = (f"바로 택시를 타면 {s['direct_fare']:,}원이에요. <b>{s['saving']:,}원</b> 아낄 수 있어요."
                if s["direct_fare"] and s["saving"] > 0 else
                "지금은 대중교통을 타도 아낄 수 없어서 바로 택시가 가장 나아요.")
    st.markdown(f'<p class="fare">{best["총 요금"]:,}원</p><p class="fare-sub">{fare_sub}</p>',
                unsafe_allow_html=True)

    notes = []
    if state["subway_sample"]:
        notes.append("지하철 노선·시간표가 시험용 가짜 데이터예요 (7호선 일부).")
    if use_bus and state["bus"] == "샘플":
        notes.append("심야버스 'N샘플'은 실제로 없는 시험용 노선이에요.")
    elif use_bus and state["bus"] == "없음":
        notes.append("심야버스 데이터가 없어서 지하철만 계산했어요.")
    if notes:
        st.warning(" ".join(notes))

# ---- 지도 ----
with st.expander("지도로 보기"):
    fig = go.Figure()
    all_lat, all_lon = [dest[0]], [dest[1]]
    for mode, line, stops in best["_segments"]:
        lat = [net.coords[p][0] for p in stops]
        lon = [net.coords[p][1] for p in stops]
        all_lat += lat
        all_lon += lon
        fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines+markers", name=f"{line}",
                                    line=dict(width=5, color=MODE_COLOR.get(mode, "#888")), marker=dict(size=6),
                                    text=[net.names[p] for p in stops], hoverinfo="text"))
    end = best["_node"]
    fig.add_trace(go.Scattermap(lat=[net.coords[end][0], dest[0]], lon=[net.coords[end][1], dest[1]],
                                mode="lines", name=best["마지막 이동"],
                                line=dict(width=4, color=MODE_COLOR[best["마지막 이동"]])))
    fig.add_trace(go.Scattermap(lat=[dest[0]], lon=[dest[1]], mode="markers", name="집",
                                marker=dict(size=14, color="#FFFFFF")))
    o = net.nodes_of(origin)[0]
    all_lat.append(net.coords[o][0])
    all_lon.append(net.coords[o][1])
    fig.update_layout(map=dict(style="carto-darkmatter", zoom=10.3,
                               center=dict(lat=sum(all_lat) / len(all_lat), lon=sum(all_lon) / len(all_lon))),
                      height=380, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=NIGHT_BG,
                      legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,.5)", font=dict(color="#fff")))
    st.plotly_chart(fig, width="stretch")

with st.expander("다른 방법과 비교"):
    cols = ["하차 위치", "경로", "첫 탑승", "대중교통 요금", "마지막 이동", "택시 요금", "총 요금", "도착 예상"]
    show = pd.concat([df.head(6), df[df["_direct"]]]).drop_duplicates(subset="하차 위치")[cols]
    st.dataframe(show, hide_index=True, width="stretch")

with st.expander("어떻게 계산하나요?"):
    st.markdown("""
- 출발 시각 이후 시간표에 남은 지하철·심야버스만 써서 각 역·정류장에 가장 빨리 닿는 시각을 구해요.
  막차가 중간역에서 끝나거나 환승할 열차가 끊긴 경우도 반영돼요. 400m 안의 역·정류장은 걸어서 갈아탈 수 있어요.
- 택시 요금은 서울 중형택시 요금표(밤 10시~새벽 4시 할증 포함)로 계산해요. 거리는 직선거리의 1.3배로 어림해서 실제와 다를 수 있어요.
- 대중교통 요금은 교통카드 기준이고, 지하철·버스 환승 요금은 단순화한 추정치예요.
- 심야버스 시각은 배차간격으로 만든 거라 실제와 몇 분 다를 수 있어요. 타기 전에 지도 앱으로 한 번 더 확인하세요.
""")
