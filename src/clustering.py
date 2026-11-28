"""[팀원 3] 역 유형 분류: 시간대별 승하차 '비율' 벡터 + K-means"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from src.config import HOURS


def station_ratio_vectors(df: pd.DataFrame, day_type="평일") -> pd.DataFrame:
    """역마다 [승차 비율 20개 | 하차 비율 20개] 벡터.

    이용객 규모가 역마다 달라서, 하루 승차(하차) 합계로 나눈 비율로 정규화한다.
    """
    d = df[df["day_type"] == day_type] if day_type else df
    g = d.groupby(["station", "hour"])[["ride", "alight"]].mean().reset_index()
    ride = g.pivot(index="station", columns="hour", values="ride").reindex(columns=HOURS).fillna(0)
    alight = g.pivot(index="station", columns="hour", values="alight").reindex(columns=HOURS).fillna(0)
    ride = ride.div(ride.sum(axis=1), axis=0)
    alight = alight.div(alight.sum(axis=1), axis=0)
    ride.columns = [f"승차_{h}" for h in HOURS]
    alight.columns = [f"하차_{h}" for h in HOURS]
    return pd.concat([ride, alight], axis=1).fillna(0)


def elbow(X: pd.DataFrame, k_range=range(2, 8), seed=42) -> pd.DataFrame:
    """k별 inertia(군집 내 거리 제곱합). 꺾이는 지점을 k로 고른다."""
    ks = [k for k in k_range if k < len(X)]
    inertia = [KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X).inertia_ for k in ks]
    return pd.DataFrame({"k": ks, "inertia": inertia})


def name_cluster(center: pd.Series) -> str:
    """군집 중심의 모양으로 이름을 '자동 추정'한다. (결과는 사람이 꼭 확인!)

    - 아침(7~9시)에 승차 비율이 높으면 주거형 (집에서 나가는 역)
    - 아침에 하차, 저녁(17~19시)에 승차 비율이 높으면 업무형
    - 둘 다 아니면 대학가형/혼합형 (낮 시간대 분산)
    """
    morning_ride = sum(center[f"승차_{h}"] for h in (7, 8, 9))
    morning_alight = sum(center[f"하차_{h}"] for h in (7, 8, 9))
    evening_ride = sum(center[f"승차_{h}"] for h in (17, 18, 19))
    if morning_ride > 0.35 and morning_ride > morning_alight * 1.5:
        return "주거형"
    if morning_alight > 0.35 and evening_ride > 0.35:
        return "업무형"
    return "대학가형/혼합형"


def cluster_stations(X: pd.DataFrame, k=3, seed=42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(역별 결과표, 군집 중심) 반환."""
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
    centers = pd.DataFrame(km.cluster_centers_, columns=X.columns)
    names = {i: name_cluster(centers.loc[i]) for i in centers.index}
    # 같은 이름이 겹치면 번호를 붙여 구분
    seen: dict[str, int] = {}
    for i, n in names.items():
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[i] = f"{n} {seen[n]}"
    centers["유형"] = centers.index.map(names)
    result = pd.DataFrame({"station": X.index, "cluster": km.labels_})
    result["유형"] = result["cluster"].map(names)
    dist = np.linalg.norm(X.values - km.cluster_centers_[km.labels_], axis=1)
    result["중심과의 거리"] = dist.round(4)
    return result.sort_values(["cluster", "중심과의 거리"]).reset_index(drop=True), centers
