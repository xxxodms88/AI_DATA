import plotly.express as px
import streamlit as st

from src.analysis import METRICS, weekday_hour_matrix
from src.config import WEEKDAY_KO, hour_label
from src.ui import CONGESTION_SCALE, sidebar

df, station, year = sidebar()

st.title("요일 × 시간대 히트맵")
c1, c2 = st.columns(2)
metric = c1.radio("지표", list(METRICS), format_func=METRICS.get, horizontal=True)
period = c2.radio("기간", ["전체", "학기", "방학"], horizontal=True)

m = weekday_hour_matrix(df, station, metric, period=None if period == "전체" else period)
m.index = [WEEKDAY_KO[i] for i in m.index]
m.columns = [hour_label(h) for h in m.columns]
m = m.T  # 휴대폰 세로 화면에 맞게: 시간대가 아래로, 요일이 옆으로

fig = px.imshow(m.round(), aspect="auto", color_continuous_scale=CONGESTION_SCALE,
                labels={"x": "요일", "y": "시간대", "color": "평균 인원"})
fig.update_xaxes(side="top", title=None)
fig.update_yaxes(title=None)
fig.update_layout(height=640, coloraxis_colorbar=dict(orientation="h", y=-0.06, thickness=10, title=""))
st.plotly_chart(fig, width="stretch")
st.caption("붉을수록 붐비는 시간이에요. 칸을 누르면 평균 인원이 보여요.")
