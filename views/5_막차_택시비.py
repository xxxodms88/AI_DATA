"""막차 끊겼을 때: 지하철로 최대한 가까이 간 뒤 택시 타서 택시비 줄이기"""
from datetime import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import TARGET_STATION
from src.night_route import plan, summary
from src.transit import Network, load_transit, parse_time


@st.cache_resource(show_spinner="노선·시간표 불러오는 중...")
def get_network():
    stations, timetable, is_sample = load_transit()
    return Network(stations, timetable), is_sample


st.set_page_config(page_title="막차 택시비 절약", page_icon="🚕", layout="wide")
net, is_sample = get_network()

st.title("🚕 막차 끊겼을 때 택시비 줄이기")
st.caption("지하철로 갈 수 있는 데까지 최대한 간 다음, 남은 거리만 택시를 타면 얼마나 아낄 수 있는지 계산합니다.")
if is_sample:
    st.warning("⚠️ 샘플 노선(7호선 도봉산~가산디지털단지)과 **가짜 심야 시간표**로 동작 중입니다. "
               "`data/transit/stations.csv`, `timetable.csv`를 넣으면 실제 데이터로 바뀝니다.")

station_names = sorted({n for _, n in net.coords})
c1, c2 = st.columns(2)
origin = c1.selectbox("출발역", station_names,
                      index=station_names.index(TARGET_STATION) if TARGET_STATION in station_names else 0)
dep_time = c2.time_input("출발 시각", value=time(0, 10), step=300)

c3, c4 = st.columns(2)
dest_mode = c3.radio("목적지 입력", ["역 근처", "좌표 직접 입력"], horizontal=True)
if dest_mode == "역 근처":
    dest_station = c4.selectbox("목적지 근처 역", station_names, index=station_names.index("노원")
                                if "노원" in station_names else 0)
    node = next(n for n in net.coords if n[1] == dest_station)
    lat0, lon0 = net.coords[node]
    off = st.slider("그 역에서 집까지 거리 (km, 대략)", 0.0, 5.0, 1.5, 0.5)
    dest = (lat0 + off / 111.0, lon0)  # 북쪽으로 off km 떨어진 지점으로 근사
else:
    cc1, cc2 = c4.columns(2)
    dest = (cc1.number_input("위도", value=37.6543, format="%.4f"),
            cc2.number_input("경도", value=127.0606, format="%.4f"))
    st.caption("주소 → 좌표 변환은 카카오/네이버 지도 API를 연결하면 자동으로 할 수 있어요.")
outside = st.checkbox("목적지가 서울 밖이에요 (시계외 할증 20%)")

depart = parse_time(dep_time.strftime("%H:%M"))
df = plan(net, origin, dest, depart, outside)
if df.empty:
    st.error("경로를 찾지 못했습니다.")
    st.stop()

s = summary(df)
best = s["best"]
st.divider()
if best["_direct"]:
    st.info(f"지금은 지하철을 타도 이득이 없어요. **바로 택시**가 가장 저렴합니다: 약 **{best['총 요금']:,}원**")
else:
    how = "걸어서" if best["마지막 이동"] == "도보" else f"택시 {best['택시 거리(km)']}km"
    st.success(
        f"**{best['지하철 탑승']}** 지하철 탑승 → **{best['하차역']}역** {best['하차 시각']} 하차 → {how}\n\n"
        f"총 약 **{best['총 요금']:,}원** · 도착 예상 {best['도착 예상']}"
        + (f" · 바로 택시({s['direct_fare']:,}원)보다 **{s['saving']:,}원 절약**" if s["direct_fare"] else "")
    )

# ---- 지도 ----
fig = go.Figure()
pts = best["_points"]
if pts:
    lat = [net.coords[p][0] for p in pts]
    lon = [net.coords[p][1] for p in pts]
    fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines+markers", name="지하철",
                                line=dict(width=5, color="#747F00"), marker=dict(size=6),
                                text=[p[1] for p in pts], hoverinfo="text"))
end_node = best["_node"]
fig.add_trace(go.Scattermap(lat=[net.coords[end_node][0], dest[0]], lon=[net.coords[end_node][1], dest[1]],
                            mode="lines", name=best["마지막 이동"], line=dict(width=4, color="#F2A900")))
fig.add_trace(go.Scattermap(lat=[dest[0]], lon=[dest[1]], mode="markers", name="목적지",
                            marker=dict(size=14, color="#E4572E")))
o = next(n for n in net.coords if n[1] == origin)
fig.add_trace(go.Scattermap(lat=[net.coords[o][0]], lon=[net.coords[o][1]], mode="markers", name="출발",
                            marker=dict(size=14, color="#7A5BA6")))
all_lat = [net.coords[o][0], dest[0]] + [net.coords[p][0] for p in pts]
all_lon = [net.coords[o][1], dest[1]] + [net.coords[p][1] for p in pts]
fig.update_layout(map=dict(style="carto-positron", zoom=10.5,
                           center=dict(lat=sum(all_lat) / len(all_lat), lon=sum(all_lon) / len(all_lon))),
                  height=480, margin=dict(l=0, r=0, t=0, b=0), legend=dict(x=0.01, y=0.99))
st.plotly_chart(fig, width="stretch")

# ---- 후보 비교표 ----
st.subheader("내릴 역별 비교 (총 요금 낮은 순)")
cols = ["하차역", "지하철 탑승", "하차 시각", "지하철 요금", "마지막 이동", "택시 거리(km)", "할증",
        "택시 요금", "총 요금", "도착 예상"]
show = pd.concat([df.head(8), df[df["_direct"]]]).drop_duplicates(subset="하차역")[cols]
st.dataframe(show, hide_index=True, width="stretch")

with st.expander("계산 방법과 한계"):
    st.markdown("""
- **탐색**: 출발 시각 이후 시간표에 남아 있는 열차만으로 각 역에 가장 빨리 도착하는 시각을 구합니다
  (Connection Scan 알고리즘). 막차가 중간역에서 끝나면 그 뒤 구간은 자동으로 후보에서 빠집니다.
- **택시 요금**: 서울 중형택시 요금표(심야 할증 22~04시 포함)로 계산합니다. 거리는 직선거리 × 1.3으로 추정한
  값이라 실제와 다를 수 있고, 저속 주행 시 붙는 시간요금은 반영하지 않습니다.
- **지하철 요금**: 교통카드 기준 기본요금 + 거리 추가요금입니다.
- **아직 안 되는 것**: 심야버스(N버스)·일반 버스는 포함되지 않습니다. ODsay 대중교통 API 같은 외부 API를
  연결하면 버스까지 넣을 수 있습니다.
- 요금·막차 시각은 바뀔 수 있으니 실제 이용 전 카카오맵/네이버지도로 다시 확인하세요.
""")
