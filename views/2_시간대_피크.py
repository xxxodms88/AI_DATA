import plotly.graph_objects as go
import streamlit as st

from src.analysis import METRICS, detect_peaks, hourly_profile
from src.ui import GREY_SERIES, NAVY, PACKED, choice, sidebar

df, station, year = sidebar()

st.title("시간대별 승하차와 피크")
c1, c2, c3 = st.columns(3)
day_type = choice("요일 구분", ["평일", "주말"], container=c1)
period = choice("기간", ["전체", "학기", "방학"], container=c2)
q = c3.slider("피크 기준 (상위 %)", 10, 40, 20, step=5)
period = None if period == "전체" else period

fig = go.Figure()
# 주인공은 승하차 합계 한 줄. 승차·하차는 회색 얇은 선으로 (DESIGN.md 6장)
for metric, dash in (("ride", "solid"), ("alight", "dot")):
    p = hourly_profile(df, station, metric, day_type=day_type, period=period)
    fig.add_scatter(x=p["label"], y=p["mean"], mode="lines", name=METRICS[metric],
                    line=dict(color=GREY_SERIES, width=1.5, dash=dash))
total = hourly_profile(df, station, "total", day_type=day_type, period=period)
peaks = detect_peaks(total, quantile=1 - q / 100)
fig.add_scatter(x=total["label"], y=total["mean"], mode="lines", name=METRICS["total"],
                line=dict(color=NAVY, width=3))
fig.add_scatter(x=peaks["label"], y=peaks["mean"], mode="markers", name="피크",
                marker=dict(symbol="circle", size=10, color=PACKED))
fig.update_layout(height=400, xaxis_title="시간대", yaxis_title="평균 인원", hovermode="x unified")
st.plotly_chart(fig, width="stretch")

st.subheader("피크 시간대 정리표")
out = peaks.rename(columns={"label": "시간대", "mean": "평균 승하차 합계"})
out["평균 승하차 합계"] = out["평균 승하차 합계"].round().astype(int)
st.dataframe(out[["시간대", "구분", "평균 승하차 합계"]], hide_index=True, width="stretch")
