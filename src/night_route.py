"""막차 이후 택시비 최소화 플래너

아이디어: 출발역에서 지하철로 갈 수 있는 '모든 역'을 후보로 두고,
          (지하철 요금 + 그 역에서 목적지까지 택시 요금)이 가장 싼 역에서 내린다.
          목적지 가까이까지 지하철이 남아 있으면 택시 구간이 짧아져 요금이 크게 줄어든다.
"""
from __future__ import annotations

import math

import pandas as pd

from src.config import TAXI_SPEED_KMH, TAXI_WAIT_MIN, WALK_KM, WALK_SPEED_KMH
from src.taxi import fare_table, haversine_km, road_km, subway_fare, taxi_fare
from src.transit import Network, fmt_time


def _rail_km(net: Network, legs: list[dict]) -> tuple[float, list]:
    km, points = 0.0, []
    for leg in legs:
        if leg["type"] != "탑승":
            continue
        stops = net.ride_stops(leg["trip"], leg["from"], leg["to"])
        for a, b in zip(stops, stops[1:]):
            km += haversine_km(*net.coords[a], *net.coords[b])
        points.extend(stops)
    return km, points


def plan(net: Network, origin: str, dest: tuple[float, float], depart: float,
         outside_seoul: bool = False) -> pd.DataFrame:
    """후보 경로표 (총비용 오름차순). 첫 행이 추천 경로."""
    arr, prev = net.earliest_arrivals(origin, depart)
    rows = []
    seen = {}
    for node, t in arr.items():
        if math.isinf(t):
            continue
        name = node[1]
        if name in seen and seen[name] <= t:
            continue
        seen[name] = t
        legs = net.path_to(prev, node)
        rail_km, points = _rail_km(net, legs)
        rides = [l for l in legs if l["type"] == "탑승"]
        if name != origin and not rides:  # 환승만 하고 이동 안 한 경우
            continue

        last_km = road_km(*net.coords[node], *dest)
        if last_km <= WALK_KM:
            mode, fare_t, end = "도보", 0, t + last_km / WALK_SPEED_KMH * 60
            surcharge = "-"
        else:
            board = t + TAXI_WAIT_MIN
            mode = "택시"
            fare_t = taxi_fare(last_km, board, outside_seoul)
            end = board + last_km / TAXI_SPEED_KMH * 60
            surcharge = fare_table(board)[2]
        fare_s = subway_fare(rail_km)
        rows.append({
            "하차역": name if rides else f"{name} (바로 택시)",
            "지하철 탑승": fmt_time(rides[0]["board_time"]) if rides else "-",
            "하차 시각": fmt_time(t) if rides else "-",
            "지하철 거리(km)": round(rail_km, 1),
            "지하철 요금": fare_s,
            "마지막 이동": mode,
            "택시 거리(km)": round(last_km, 1) if mode == "택시" else 0.0,
            "할증": surcharge,
            "택시 요금": fare_t,
            "총 요금": fare_s + fare_t,
            "도착 예상": fmt_time(end),
            "_end": end,
            "_direct": not rides,
            "_node": node,
            "_points": points,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["총 요금", "_end"]).reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    best = df.iloc[0]
    direct = df[df["_direct"]]
    direct_fare = int(direct["총 요금"].min()) if not direct.empty else None
    return {
        "best": best,
        "direct_fare": direct_fare,
        "saving": (direct_fare - int(best["총 요금"])) if direct_fare is not None else 0,
    }
