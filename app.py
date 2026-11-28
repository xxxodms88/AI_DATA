"""앱 시작 파일. 실행: streamlit run app.py

화면을 추가하려면 views/ 에 파일을 만들고 아래 목록에 한 줄 추가하세요.
"""
import streamlit as st

st.set_page_config(page_title="숭실대입구 언제 탈까", page_icon="🚇", layout="centered",
                   initial_sidebar_state="collapsed")

pg = st.navigation({
    "": [
        st.Page("views/0_홈.py", title="언제 탈까", icon=":material/schedule:", default=True),
        st.Page("views/5_막차_택시비.py", title="막차 놓쳤을 때", icon=":material/local_taxi:"),
    ],
    "분석 근거": [
        st.Page("views/1_혼잡도_히트맵.py", title="요일·시간 히트맵", icon=":material/grid_on:"),
        st.Page("views/2_시간대_피크.py", title="붐비는 시간대", icon=":material/show_chart:"),
        st.Page("views/3_조건_비교.py", title="학기·주말·코로나 비교", icon=":material/compare_arrows:"),
        st.Page("views/4_역_유형_분석.py", title="역 유형 분류", icon=":material/hub:"),
    ],
}, position="top")
pg.run()

# 화면 읽기 프로그램이 한국어로 읽도록 <html lang="ko"> 지정 (Streamlit 기본값은 en, DESIGN.md 7장)
import streamlit.components.v1 as components  # noqa: E402

components.html("<script>window.parent.document.documentElement.lang = 'ko';</script>", height=0)
