"""막차 끊겼을 때: 지하철·심야버스로 최대한 가까이 간 뒤 택시 타서 택시비 줄이기"""
from datetime import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import TARGET_STATION
from src.night_route import plan, summary
from src.transit import Network, load_transit, parse_time

MODE_COLOR = {"지하철": "#747F00", "심야버스": "#1E5AA8", "택시": "#F2A900", "도보": "#888888"}


@st.cache_resource(show_spinner="노선·시간표 불러오는 중...")
def get_network(include_bus: bool):
    stations, timetable, state = load_transit(include_bus=include_bus)
    return Network(stations, timetable), state


st.set_page_config(page_title="막차 택시비 절약", page_icon="🚕", layout="wide")
st.title("🚕 막차 끊겼을 때 택시비 줄이기")
st.caption("지하철·심야버스로 갈 수 있는 데까지 최대한 간 다음, 남은 거리만 택시를 타면 얼마나 아낄 수 있는지 계산합니다.")

use_bus = st.toggle("심야버스(N버스) 포함", value=True)
net, state = get_network(use_bus)
if state["subway_sample"]:
    st.warning("⚠️ 샘플 노선(7호선 도봉산~가산디지털단지)과 **가짜 심야 시간표**로 동작 중입니다. "
               "`data/transit/stations.csv`, `timetable.csv`를 넣으면 실제 데이터로 바뀝니다.")
if use_bus and state["bus"] == "샘플":
    st.warning("⚠️ 심야버스도 **가상의 샘플 노선 'N샘플'**(숭실대입구역~노원역)입니다. 실제 N버스가 아니에요. "
               "`data/transit/bus_routes.csv`, `bus_schedule.csv`를 넣으면 실제 노선으로 바뀝니다.")
elif use_bus and state["bus"] == "없음":
    st.info("심야버스 데이터(`data/transit/bus_routes.csv`, `bus_schedule.csv`)가 없어 지하철만 계산합니다.")

subway_names = sorted({net.names[n] for n in net.coords if net.modes[n] == "지하철"})
c1, c2 = st.columns(2)
origin = c1.selectbox("출발역", subway_names,
                      index=subway_names.index(TARGET_STATION) if TARGET_STATION in subway_names else 0)
dep_time = c2.time_input("출발 시각", value=time(1, 0), step=300)

c3, c4 = st.columns(2)
dest_mode = c3.radio("목적지 입력", ["역 근처", "좌표 직접 입력"], horizontal=True)
if dest_mode == "역 근처":
    dest_station = c4.selectbox("목적지 근처 역", subway_names,
                                index=subway_names.index("노원") if "노원" in subway_names else 0)
    lat0, lon0 = net.coords[net.nodes_of(dest_station)[0]]
    off = st.slider("그 역에서 집까지 거리 (km, 대략)", 0.0, 5.0, 1.5, 0.5)
    dest = (lat0 + off / 111.0, lon0)  # 북쪽으로 off km 떨어진 지점으로 근사
else:
    cc1, cc2 = c4.columns(2)
    dest = (cc1.number_input("위도", value=37.6543, format="%.4f"),
            cc2.number_input("경도", value=127.0606, format="%.4f"))
    st.caption("주소 → 좌표 변환은 카카오/네이버 지도 API를 연결하면 자동으로 할 수 있어요.")

c5, c6 = st.columns(2)
outside = c5.checkbox("목적지가 서울 밖이에요 (시계외 할증 20%)")
time_value = c6.select_slider(
    "시간도 아끼고 싶다면? (1분을 몇 원으로 칠지)", options=[0, 50, 100, 200, 300, 500], value=0,
    help="0이면 무조건 가장 싼 경로. 올릴수록 조금 비싸도 빨리 도착하는 경로를 추천합니다.")

depart = parse_time(dep_time.strftime("%H:%M"))
df = plan(net, origin, dest, depart, outside, time_value)
if df.empty:
    st.error("경로를 찾지 못했습니다.")
    st.stop()

s = summary(df)
best = s["best"]
st.divider()
if best["_direct"]:
    st.info(f"지금은 대중교통을 타도 이득이 없어요. **바로 택시**가 가장 낫습니다: 약 **{best['총 요금']:,}원** "
            f"· 도착 예상 {best['도착 예상']}")
else:
    how = "걸어서" if best["마지막 이동"] == "도보" else f"택시 {best['택시 거리(km)']}km"
    st.success(
        f"**{best['첫 탑승']}** 탑승: {best['경로']} → **{best['하차 위치']}** {best['하차 시각']} 하차 → {how}\n\n"
        f"총 약 **{best['총 요금']:,}원** · 도착 예상 {best['도착 예상']} (약 {best['소요(분)']}분)"
        + (f" · 바로 택시({s['direct_fare']:,}원)보다 **{s['saving']:,}원 절약**" if s["direct_fare"] else "")
    )

# ---- 지도 ----
fig = go.Figure()
all_lat, all_lon = [dest[0]], [dest[1]]
for mode, line, stops in best["_segments"]:
    lat = [net.coords[p][0] for p in stops]
    lon = [net.coords[p][1] for p in stops]
    all_lat += lat
    all_lon += lon
    fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines+markers", name=f"{line} ({mode})",
                                line=dict(width=5, color=MODE_COLOR.get(mode, "#555")), marker=dict(size=6),
                                text=[net.names[p] for p in stops], hoverinfo="text"))
end = best["_node"]
fig.add_trace(go.Scattermap(lat=[net.coords[end][0], dest[0]], lon=[net.coords[end][1], dest[1]],
                            mode="lines", name=best["마지막 이동"],
                            line=dict(width=4, color=MODE_COLOR[best["마지막 이동"]])))
fig.add_trace(go.Scattermap(lat=[dest[0]], lon=[dest[1]], mode="markers", name="목적지",
                            marker=dict(size=14, color="#E4572E")))
o = net.nodes_of(origin)[0]
fig.add_trace(go.Scattermap(lat=[net.coords[o][0]], lon=[net.coords[o][1]], mode="markers", name="출발",
                            marker=dict(size=14, color="#7A5BA6")))
all_lat.append(net.coords[o][0])
all_lon.append(net.coords[o][1])
fig.update_layout(map=dict(style="carto-positron", zoom=10.5,
                           center=dict(lat=sum(all_lat) / len(all_lat), lon=sum(all_lon) / len(all_lon))),
                  height=480, margin=dict(l=0, r=0, t=0, b=0), legend=dict(x=0.01, y=0.99))
st.plotly_chart(fig, width="stretch")

# ---- 후보 비교표 ----
st.subheader("내릴 곳별 비교 (추천 순)")
cols = ["하차 위치", "경로", "첫 탑승", "하차 시각", "대중교통 요금", "마지막 이동", "택시 거리(km)", "할증",
        "택시 요금", "총 요금", "도착 예상", "소요(분)"]
show = pd.concat([df.head(8), df[df["_direct"]]]).drop_duplicates(subset="하차 위치")[cols]
st.dataframe(show, hide_index=True, width="stretch")

with st.expander("계산 방법과 한계"):
    st.markdown("""
- **탐색**: 출발 시각 이후 시간표에 남아 있는 지하철·심야버스만으로 각 역·정류장에 가장 빨리 도착하는 시각을 구합니다
  (Connection Scan 알고리즘). 막차가 중간역에서 끝나거나 환승 열차가 끊긴 경우도 자동으로 반영됩니다.
  400m 이내 역·정류장끼리는 걸어서 갈아탈 수 있게 했습니다.
- **심야버스**: 첫차·막차·배차간격으로 운행 시각을 만들어 쓰기 때문에 실제 도착 시각과 몇 분 차이가 날 수 있습니다.
- **택시 요금**: 서울 중형택시 요금표(심야 할증 22~04시 포함). 거리는 직선거리 × 1.3 추정이고,
  저속 주행 시간요금은 반영하지 않습니다.
- **대중교통 요금**: 교통카드 기준. 지하철+버스 통합환승 요금은 단순화한 추정치입니다.
- 요금·막차·배차 정보는 바뀔 수 있으니 실제 이용 전 카카오맵/네이버지도로 다시 확인하세요.
""")
