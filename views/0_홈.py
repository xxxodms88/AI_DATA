"""언제 탈까: 역명판 + 혼잡 판정 + 덜 붐비는 시간 추천"""
import pandas as pd
import streamlit as st

from src.analysis import hourly_profile
from src.config import SEMESTERS, TARGET_STATION, WEEKDAY_KO, hour_label
from src.recommend import recommend
from src.ui import base_css, congestion_strip, get_data, level_of, now_kst, sample_note, station_sign

base_css()
df, is_sample = get_data()
now = now_kst()

# 답(위)을 먼저 보여주고 조건 바꾸기(아래)는 접어 둔다. 위젯 값이 먼저 필요해서 자리를 미리 잡는다.
answer = st.container()
settings = st.expander("역·요일·시간 바꾸기")

with settings:
    stations = sorted(df["station"].unique())
    if "station" not in st.session_state:
        st.session_state["station"] = TARGET_STATION if TARGET_STATION in stations else stations[0]
    station = st.selectbox("역", stations, key="station")
    c1, c2 = st.columns(2)
    weekday = c1.selectbox("요일", WEEKDAY_KO, index=now.weekday())
    md = (now.month, now.day)
    in_semester = any((s.month, s.day) <= md <= (e.month, e.day)
                      for periods in SEMESTERS.values() for s, e in periods)
    period = c2.radio("기간", ["학기", "방학"], index=0 if in_semester else 1, horizontal=True)
    mode = st.radio("어디로", ["학교 가는 길", "집 가는 길"], horizontal=True,
                    index=0 if now.hour < 13 else 1)
    if mode == "학교 가는 길":
        target = st.slider("이 시간대에 역에 도착하려고 해요", 6, 12, 8, format="%d시대")
    else:
        target = st.slider("이 시간대에 수업이 끝나요", 12, 22, 18, format="%d시대")
    window = st.slider("몇 시간까지 당기거나 미룰 수 있나요?", 1, 3, 1)

prof = hourly_profile(df, station, metric="total", weekday=weekday, period=period)

with answer:
    line = df.loc[df["station"] == station, "line"].iloc[0] if "line" in df else None
    station_sign(station, line)
    if prof["mean"].sum() == 0:
        st.markdown('<p class="verdict">이 조건의 데이터가 없어요</p>', unsafe_allow_html=True)
        st.markdown('<p class="advice">아래에서 역이나 요일을 바꿔 보세요.</p>', unsafe_allow_html=True)
    else:
        rec = recommend(prof, target, window, "before" if mode == "학교 가는 길" else "after")
        ratio = float(prof.set_index("hour").loc[target, "mean"] / prof["mean"].max())
        word, _ = level_of(ratio)
        st.markdown(f'<p class="verdict">{weekday}요일 {target}시대는 {word}</p>', unsafe_allow_html=True)
        if rec["best_hour"] == target:
            advice = f"{period} 중에는 {hour_label(target)}가 앞뒤 시간보다 덜 붐벼요. 그대로 가면 됩니다."
        else:
            when = "일찍" if rec["best_hour"] < target else "늦게"
            advice = (f"{abs(rec['best_hour'] - target)}시간 {when} <b>{rec['best_label']}</b>에 타면 "
                      f"승하차 인원이 <b>{rec['saving_pct']:.0f}%</b> 적어요.")
        st.markdown(f'<p class="advice">{advice}</p>', unsafe_allow_html=True)
        congestion_strip(prof, target_hour=target, best_hour=rec["best_hour"])

        with st.expander("숫자로 보기"):
            t = rec["table"].rename(columns={"label": "시간대", "mean": "평균 승하차(명)"})
            t["평균 승하차(명)"] = t["평균 승하차(명)"].round().astype(int)
            t["가장 붐비는 시간 대비"] = (t["상대혼잡도"] * 100).round().astype(int).astype(str) + "%"
            st.dataframe(pd.DataFrame(t[["시간대", "평균 승하차(명)", "가장 붐비는 시간 대비"]]),
                         hide_index=True, width="stretch")
        st.caption("승하차 인원으로 본 역 혼잡도예요. 열차 칸 안의 혼잡도와는 다를 수 있어요.")
    sample_note(is_sample)
