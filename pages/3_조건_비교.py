import plotly.graph_objects as go
import streamlit as st

from src.analysis import METRICS, compare_groups
from src.ui import sidebar

st.set_page_config(page_title="조건 비교", page_icon="⚖️", layout="wide")
df, station, year = sidebar(show_year=False)  # 코로나 비교는 연도를 넘나들어서 전체 기간 사용

st.title("⚖️ 조건별 비교 + 통계 검정")
COMPARISONS = {
    "학기 vs 방학": ("period", "학기", "방학", "평일"),
    "평일 vs 주말": ("day_type", "평일", "주말", None),
    "코로나 전 vs 후": ("covid", "코로나 전", "코로나 후", "평일"),
}
c1, c2 = st.columns(2)
choice = c1.radio("비교", list(COMPARISONS), horizontal=True)
metric = c2.radio("지표", list(METRICS), format_func=METRICS.get, horizontal=True)
by, a, b, day_type = COMPARISONS[choice]

res = compare_groups(df, station, by, a, b, metric, day_type)
if res[[a, b]].isna().all().any():
    st.info(f"'{a}' 또는 '{b}'에 해당하는 데이터가 없습니다. (config.py의 연도·학사일정 확인)")
    st.stop()

fig = go.Figure()
fig.add_bar(x=res["label"], y=res[a], name=a)
fig.add_bar(x=res["label"], y=res[b], name=b)
fig.update_layout(barmode="group", height=420, xaxis_title="시간대", yaxis_title="평균 인원")
st.plotly_chart(fig, width="stretch")

sig = res[res["유의(p<0.05)"]]
st.markdown(f"**{len(sig)} / {len(res)}개 시간대**에서 {a}와 {b}의 차이가 통계적으로 유의합니다 "
            f"(Welch t-검정, p < 0.05){' · 평일만 비교' if day_type else ''}.")

show = res.rename(columns={"label": "시간대"})
show[[a, b]] = show[[a, b]].round().astype(int)
show["차이(%)"] = show["차이(%)"].round(1)
show["p값"] = show["p값"].map(lambda p: f"{p:.4f}")
st.dataframe(show[["시간대", a, b, "차이(%)", "p값", "유의(p<0.05)"]],
             hide_index=True, width="stretch")
