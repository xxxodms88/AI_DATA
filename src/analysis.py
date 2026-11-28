"""[팀원 2] 패턴 분석: 시간대 피크 탐지, 조건별 비교, 통계 검정"""
from __future__ import annotations

import pandas as pd
from scipy import stats

from src.config import HOURS, hour_label

METRICS = {"total": "승하차 합계", "ride": "승차", "alight": "하차"}


def daily_hourly(df: pd.DataFrame, station: str) -> pd.DataFrame:
    """역 하나의 날짜 x 시간대 데이터 (환승역은 호선 합산)."""
    keys = ["date", "hour", "year", "weekday", "weekday_num", "day_type", "period", "covid"]
    d = df[df["station"] == station]
    return d.groupby(keys, as_index=False)[["ride", "alight", "total"]].sum()


def hourly_profile(df: pd.DataFrame, station: str, metric="total", **filters) -> pd.DataFrame:
    """시간대별 평균 인원. filters 예: day_type='평일', period='학기'"""
    d = daily_hourly(df, station)
    for col, val in filters.items():
        if val is not None:
            d = d[d[col] == val]
    prof = d.groupby("hour")[metric].mean().reindex(HOURS).fillna(0).reset_index()
    prof.columns = ["hour", "mean"]
    prof["label"] = prof["hour"].map(hour_label)
    return prof


def detect_peaks(profile: pd.DataFrame, quantile=0.8) -> pd.DataFrame:
    """평균 인원이 상위 (1-quantile) 구간인 시간대를 피크로 정의하고 출근/점심/퇴근으로 이름 붙인다."""
    th = profile["mean"].quantile(quantile)
    peaks = profile[profile["mean"] >= th].copy()

    def name(h):
        if 6 <= h <= 9:
            return "출근·등교"
        if 11 <= h <= 13:
            return "점심"
        if 17 <= h <= 20:
            return "퇴근·하교"
        return "기타"

    peaks["구분"] = peaks["hour"].map(name)
    return peaks.sort_values("mean", ascending=False)


def weekday_hour_matrix(df: pd.DataFrame, station: str, metric="total", **filters) -> pd.DataFrame:
    """요일 x 시간대 평균 (히트맵용)."""
    d = daily_hourly(df, station)
    for col, val in filters.items():
        if val is not None:
            d = d[d[col] == val]
    m = d.pivot_table(index="weekday_num", columns="hour", values=metric, aggfunc="mean")
    return m.reindex(columns=HOURS)


def compare_groups(df: pd.DataFrame, station: str, by: str, group_a: str, group_b: str,
                   metric="total", day_type: str | None = "평일") -> pd.DataFrame:
    """두 조건(예: 학기 vs 방학)을 시간대별로 비교하고 Welch t-검정 p값을 붙인다."""
    d = daily_hourly(df, station)
    if day_type:
        d = d[d["day_type"] == day_type]
    rows = []
    for h in HOURS:
        a = d[(d["hour"] == h) & (d[by] == group_a)][metric]
        b = d[(d["hour"] == h) & (d[by] == group_b)][metric]
        p = stats.ttest_ind(a, b, equal_var=False).pvalue if len(a) > 1 and len(b) > 1 else float("nan")
        rows.append({
            "hour": h, "label": hour_label(h),
            group_a: a.mean(), group_b: b.mean(),
            "차이(%)": (b.mean() - a.mean()) / a.mean() * 100 if a.mean() else float("nan"),
            "p값": p, "유의(p<0.05)": bool(p < 0.05) if p == p else False,
        })
    return pd.DataFrame(rows)
