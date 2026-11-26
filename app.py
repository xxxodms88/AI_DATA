"""앱 시작 파일. 실행: streamlit run app.py

페이지를 추가하려면 pages/ 에 파일을 만들고 아래 목록에 한 줄 추가하세요.
"""
import streamlit as st

pg = st.navigation([
    st.Page("pages/0_홈.py", title="홈 · 오늘의 추천", icon="🚇", default=True),
    st.Page("pages/1_혼잡도_히트맵.py", title="혼잡도 히트맵", icon="🗓️"),
    st.Page("pages/2_시간대_피크.py", title="시간대 피크", icon="📈"),
    st.Page("pages/3_조건_비교.py", title="조건 비교", icon="⚖️"),
    st.Page("pages/4_역_유형_분석.py", title="역 유형 분석", icon="🧭"),
])
pg.run()
