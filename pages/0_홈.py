"""홈: 오늘의 추천"""
from datetime import date

import plotly.express as px
import streamlit as st

from src.analysis import hourly_profile
from src.config import SEMESTERS, WEEKDAY_KO, hour_label
from src.recommend import recommend, relative_congestion
from src.ui import sidebar

st.set_page_config(page_title="숭실대입구 혼잡도", page_icon="🚇", layout="wide")
df, station, year = sidebar()

st.title("🚇 덜 붐비는 등하교 시간 찾기")
st.caption("서울교통공사 공공데이터 기반 · 시간대·요일·학기별 승하차 패턴 분석")

# ---- 오늘 조건 자동 판단 (요일 / 학기·방학) ----
today = date.today()
md = (today.month, today.day)  # 연도와 상관없이 월·일로 학기 여부 판단
in_semester = any((s.month, s.day) <= md <= (e.month, e.day)
                  for periods in SEMESTERS.values() for s, e in periods)
col1, col2, col3 = st.columns(3)
weekday = col1.selectbox("요일", WEEKDAY_KO, index=today.weekday())
period = col2.radio("기간", ["학기", "방학"], index=0 if in_semester else 1, horizontal=True)
mode = col3.radio("이동", ["등교", "하교"], horizontal=True)

c1, c2 = st.columns(2)
if mode == "등교":
    target = c1.slider("수업 시작 전 도착하고 싶은 시간대", 6, 12, 8, format="%d시대")
else:
    target = c1.slider("수업이 끝나는 시간대", 12, 22, 18, format="%d시대")
window = c2.slider("앞뒤로 몇 시간까지 조정 가능?", 1, 3, 1)

prof = hourly_profile(df, station, metric="total", weekday=weekday, period=period)
if prof["mean"].sum() == 0:
    st.info("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

rec = recommend(prof, target, window, "before" if mode == "등교" else "after")

# ---- 추천 결과 ----
st.divider()
if rec["best_hour"] == target:
    st.success(f"**{hour_label(target)}** 가 이미 가장 덜 붐비는 시간대예요. 그대로 이동하세요!")
else:
    st.success(f"**{hour_label(target)}** 대신 **{rec['best_label']}** 에 이동하면 "
               f"승하차 인원이 약 **{rec['saving_pct']}%** 적어요.")

table = rec["table"].rename(columns={"label": "시간대", "mean": "평균 승하차 인원"})
table["평균 승하차 인원"] = table["평균 승하차 인원"].round().astype(int)
table["상대혼잡도"] = (table["상대혼잡도"] * 100).round().astype(int).astype(str) + "%"
st.dataframe(table[["시간대", "평균 승하차 인원", "상대혼잡도", "수준"]],
             hide_index=True, width="stretch")

# ---- 하루 전체 그래프 ----
rc = relative_congestion(prof)
rc["추천 후보"] = rc["hour"].isin(rec["table"]["hour"]).map({True: "후보 시간대", False: "그 외"})
fig = px.bar(rc, x="label", y="mean", color="추천 후보",
             color_discrete_map={"후보 시간대": "#7A5BA6", "그 외": "#CFCFD6"},
             labels={"label": "시간대", "mean": "평균 승하차 인원"},
             title=f"{station}역 · {weekday}요일 · {period} 시간대별 평균 승하차")
st.plotly_chart(fig, width="stretch")

st.caption("※ 승하차 인원은 '역' 혼잡도이며 열차 칸 내부 혼잡도와는 다를 수 있습니다.")
