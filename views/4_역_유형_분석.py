import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.clustering import cluster_stations, elbow, station_ratio_vectors
from src.config import COMPARE_STATIONS, HOURS, hour_label
from src.ui import GREY_SERIES, OLIVE, sidebar

df, station, year = sidebar()

st.title("역 유형 분류 (K-means)")
st.caption("역마다 이용객 규모가 달라서 '하루 중 몇 %가 그 시간대에 타고 내리는지' 비율로 비교합니다. (평일 기준)")

X = station_ratio_vectors(df, "평일")
if len(X) < 3:
    st.info("군집화하려면 역이 3개 이상 필요해요. 비교 대상 역을 늘려 보세요.")
    st.stop()

with st.expander("① 엘보우 기법으로 k 정하기", expanded=False):
    e = elbow(X)
    st.plotly_chart(px.line(e, x="k", y="inertia", markers=True), width="stretch")
    st.caption("그래프가 급하게 꺾이는 지점의 k가 적당합니다.")

k = st.slider("군집 개수 k", 2, min(7, len(X) - 1), 3)
result, centers = cluster_stations(X, k)

my = result[result["station"] == station]
if not my.empty:
    st.success(f"**{station}역**은 **{my.iloc[0]['유형']}** 군집에 속합니다.")

st.subheader("② 군집별 시간대 패턴 (군집 중심)")
labels = [hour_label(h) for h in HOURS]
c1, c2 = st.columns(2)
my_type = my.iloc[0]["유형"] if not my.empty else None
dashes = iter(["dot", "dash", "dashdot", "longdash", "longdashdot", "solid"])
styles = {t: (dict(color=OLIVE, width=3) if t == my_type else dict(color=GREY_SERIES, width=1.5, dash=next(dashes)))
          for t in centers["유형"]}  # 숭실대입구역이 속한 유형만 강조 (DESIGN.md 6장)
for col, kind in ((c1, "승차"), (c2, "하차")):
    col.markdown(f"**{kind} 비율 (%)**")
    fig = go.Figure()
    for _, row in centers.iterrows():
        fig.add_scatter(x=labels, y=[row[f"{kind}_{h}"] * 100 for h in HOURS],
                        mode="lines", name=row["유형"], line=styles[row["유형"]])
    fig.update_layout(height=360, hovermode="x unified")
    col.plotly_chart(fig, width="stretch")

st.subheader("③ 역별 군집 결과")
result["예상 유형(config)"] = result["station"].map(lambda s: COMPARE_STATIONS.get(s, ("", "-"))[1])
st.dataframe(result, hide_index=True, width="stretch")
st.caption("‘유형’ 이름은 군집 중심 모양으로 자동 추정한 값입니다. 예상 유형과 비교해 상식적인지 꼭 확인하세요.")
