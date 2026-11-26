"""여러 페이지에서 같이 쓰는 Streamlit 화면 요소."""
from __future__ import annotations

import streamlit as st

from src.config import TARGET_STATION
from src.data_loader import load_data


@st.cache_data(show_spinner="데이터 불러오는 중...")
def get_data():
    return load_data()


def sidebar(show_year=True):
    """사이드바: 데이터 상태 + 역/연도 선택. (df, station, year) 반환"""
    df, is_sample = get_data()
    with st.sidebar:
        if is_sample:
            st.warning("⚠️ 샘플(가짜) 데이터로 보는 중입니다.\n\n"
                       "`data/processed/subway_clean.csv`를 만들면 실제 데이터로 바뀝니다.")
        else:
            st.success("실제 데이터 사용 중")
        stations = sorted(df["station"].unique())
        default = stations.index(TARGET_STATION) if TARGET_STATION in stations else 0
        station = st.selectbox("역 선택", stations, index=default, key="station")
        year = None
        if show_year:
            years = sorted(df["year"].unique())
            year = st.selectbox("연도", ["전체"] + years, index=len(years), key="year")
            year = None if year == "전체" else year
        st.caption(f"데이터 기간: {df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}")
    if year is not None:
        df = df[df["year"] == year]
    return df, station, year
