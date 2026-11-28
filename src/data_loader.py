"""정제된 데이터를 불러오고 분석용 파생 변수(요일·주말·학기/방학·코로나 전후)를 붙인다."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import COVID_AFTER_YEARS, COVID_BEFORE_YEARS, SEMESTERS, WEEKDAY_KO

PROCESSED_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "subway_clean.csv"


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["weekday_num"] = df["date"].dt.dayofweek
    df["weekday"] = df["weekday_num"].map(dict(enumerate(WEEKDAY_KO)))
    df["day_type"] = df["weekday_num"].map(lambda d: "주말" if d >= 5 else "평일")

    sem = pd.Series(False, index=df.index)
    for periods in SEMESTERS.values():
        for start, end in periods:
            sem |= df["date"].between(pd.Timestamp(start), pd.Timestamp(end))
    df["period"] = sem.map({True: "학기", False: "방학"})

    df["covid"] = "기타"
    df.loc[df["year"].isin(COVID_BEFORE_YEARS), "covid"] = "코로나 전"
    df.loc[df["year"].isin(COVID_AFTER_YEARS), "covid"] = "코로나 후"
    df["total"] = df["ride"] + df["alight"]
    return df


def load_data() -> tuple[pd.DataFrame, bool]:
    """(데이터, 샘플 여부)를 반환. 정제 CSV가 없으면 샘플 데이터를 만든다."""
    if PROCESSED_PATH.exists():
        return add_features(pd.read_csv(PROCESSED_PATH)), False
    from src.sample_data import make_sample

    return add_features(make_sample()), True
