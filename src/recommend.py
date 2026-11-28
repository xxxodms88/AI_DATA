"""[팀원 4] 덜 붐비는 시간대 추천 로직

상대 혼잡도 = 해당 시간대 평균 인원 / 그 조건에서 가장 붐비는 시간대의 평균 인원  (0~1)
"""
from __future__ import annotations

import pandas as pd

from src.config import hour_label


def relative_congestion(profile: pd.DataFrame) -> pd.DataFrame:
    p = profile.copy()
    peak = p["mean"].max()
    p["상대혼잡도"] = p["mean"] / peak if peak else 0
    return p


def level(r: float) -> str:
    if r >= 0.8:
        return "매우 혼잡"
    if r >= 0.55:
        return "혼잡"
    if r >= 0.3:
        return "보통"
    return "여유"


def recommend(profile: pd.DataFrame, target_hour: int, window: int = 2,
              direction: str = "before") -> dict:
    """target_hour(예: 1교시 9시 수업이면 8시대에 도착) 주변에서 덜 붐비는 시간대 추천.

    direction='before' : 등교 - 목표 시각과 그 이전 window 시간 중에서 고른다
    direction='after'  : 하교 - 목표 시각과 그 이후 window 시간 중에서 고른다
    """
    p = relative_congestion(profile).set_index("hour")
    if direction == "before":
        cands = [h for h in range(target_hour - window, target_hour + 1) if h in p.index]
    else:
        cands = [h for h in range(target_hour, target_hour + window + 1) if h in p.index]
    table = p.loc[cands, ["mean", "상대혼잡도"]].reset_index()
    table["label"] = table["hour"].map(hour_label)
    table["수준"] = table["상대혼잡도"].map(level)

    base = p.loc[target_hour, "mean"]
    best = table.loc[table["mean"].idxmin()]
    saving = (base - best["mean"]) / base * 100 if base else 0
    return {
        "target_hour": target_hour,
        "best_hour": int(best["hour"]),
        "best_label": best["label"],
        "saving_pct": round(float(saving), 1),
        "table": table,
    }
