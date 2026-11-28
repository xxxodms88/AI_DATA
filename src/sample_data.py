"""실제 CSV가 준비되기 전에 앱을 돌려 보기 위한 '가짜' 샘플 데이터 생성기.

※ 이 데이터는 분석 결과가 아닙니다. 역 유형별로 그럴듯한 모양만 흉내 낸 값입니다.
   data/processed/subway_clean.csv 가 생기면 앱은 자동으로 실제 데이터를 사용합니다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import COMPARE_STATIONS, HOURS, SEMESTERS

_H = np.array(HOURS, dtype=float)


def _bump(center, width, amp):
    return amp * np.exp(-0.5 * ((_H - center) / width) ** 2)


# 역 유형별 평일 시간대 모양 (승차, 하차)
_WEEKDAY = {
    "주거형": (_bump(7.8, 1.0, 1.0) + _bump(18.5, 2.5, 0.25) + 0.05,
               _bump(19.0, 1.6, 0.8) + _bump(8, 1.5, 0.15) + 0.05),
    "업무형": (_bump(18.6, 1.2, 1.0) + _bump(12.5, 1.0, 0.2) + 0.05,
               _bump(8.4, 0.9, 1.0) + _bump(13, 1.0, 0.2) + 0.05),
    "대학가형": (_bump(7.8, 1.0, 0.45) + _bump(17.5, 2.0, 0.7) + _bump(13, 1.5, 0.3) + 0.05,
               _bump(8.6, 1.0, 0.8) + _bump(10.5, 1.2, 0.35) + _bump(19, 2, 0.3) + 0.05),
}
_WEEKEND = (_bump(14.5, 3.5, 0.45) + 0.04, _bump(15, 3.5, 0.45) + 0.04)


def _is_semester(dates: pd.DatetimeIndex) -> np.ndarray:
    out = np.zeros(len(dates), dtype=bool)
    for periods in SEMESTERS.values():
        for start, end in periods:
            out |= (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    return out


def make_sample(years=(2019, 2021), seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31", freq="D")
    dates = dates[dates.year.isin(years)]
    weekend = dates.dayofweek.values >= 5
    semester = _is_semester(dates)
    covid = np.isin(dates.year, [2020, 2021])

    frames = []
    for i, (station, (line, kind)) in enumerate(COMPARE_STATIONS.items()):
        scale = rng.uniform(1500, 6000)
        ride_wd, alight_wd = _WEEKDAY[kind]
        ride = np.where(weekend[:, None], _WEEKEND[0], ride_wd)
        alight = np.where(weekend[:, None], _WEEKEND[1], alight_wd)

        factor = np.ones(len(dates))
        if kind == "대학가형":
            factor *= np.where(semester, 1.0, 0.6)
        factor *= np.where(covid, 0.72, 1.0)
        night = np.where(covid[:, None] & (_H >= 21), 0.6, 1.0)

        noise = lambda: rng.normal(1.0, 0.08, size=ride.shape).clip(0.5)
        ride = ride * factor[:, None] * night * scale * noise()
        alight = alight * factor[:, None] * night * scale * noise()

        frames.append(pd.DataFrame({
            "date": np.repeat(dates.values, len(HOURS)),
            "line": line,
            "station": station,
            "hour": np.tile(HOURS, len(dates)),
            "ride": ride.ravel().round().astype(int),
            "alight": alight.ravel().round().astype(int),
        }))
    return pd.concat(frames, ignore_index=True)
