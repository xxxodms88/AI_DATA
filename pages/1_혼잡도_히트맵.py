import plotly.express as px
import streamlit as st

from src.analysis import METRICS, weekday_hour_matrix
from src.config import WEEKDAY_KO, hour_label
from src.ui import sidebar

st.set_page_config(page_title="혼잡도 히트맵", page_icon="🗓️", layout="wide")
df, station, year = sidebar()

st.title("🗓️ 요일 × 시간대 히트맵")
c1, c2 = st.columns(2)
metric = c1.radio("지표", list(METRICS), format_func=METRICS.get, horizontal=True)
period = c2.radio("기간", ["전체", "학기", "방학"], horizontal=True)

m = weekday_hour_matrix(df, station, metric, period=None if period == "전체" else period)
m.index = [WEEKDAY_KO[i] for i in m.index]
m.columns = [hour_label(h) for h in m.columns]

fig = px.imshow(m.round(), aspect="auto", color_continuous_scale="Purples",
                labels={"x": "시간대", "y": "요일", "color": "평균 인원"}, text_auto=".0f")
fig.update_layout(height=450)
st.plotly_chart(fig, width="stretch")
st.caption("색이 진할수록 붐비는 구간입니다.")
