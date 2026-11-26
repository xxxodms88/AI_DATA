"""막차 이후 택시비 최소화 플래너

아이디어: 출발역에서 지하철로 갈 수 있는 '모든 역'을 후보로 두고,
          (지하철 요금 + 그 역에서 목적지까지 택시 요금)이 가장 싼 역에서 내린다.
          목적지 가까이까지 지하철이 남아 있으면 택시 구간이 짧아져 요금이 크게 줄어든다.
"""
from __future__ import annotations

import math

import pandas as pd

from src.config import TAXI_SPEED_KMH, TAXI_WAIT_MIN, WALK_KM, WALK_SPEED_KMH
from src.taxi import fare_table, haversine_km, road_km, taxi_fare, transit_fare
from src.transit import Network, fmt_time


def _ride_info(net: Network, legs: list[dict]) -> tuple[float, list, str, list]:
    """(이동 거리 km, 지도용 구간 [(수단, 노선, [노드...])], 경로 설명, 구간별 시각 목록)"""
    km, segments, desc, timed = 0.0, [], [], []
    for leg in legs:
        if leg["type"] != "탑승":
            continue
        stops = net.ride_stops(leg["trip"], leg["from"], leg["to"], leg["board_time"])
        for a, b in zip(stops, stops[1:]):
            km += haversine_km(*net.coords[a], *net.coords[b])
        segments.append((leg["mode"], leg["line"], stops))
        desc.append(f"{leg['line']} {net.names[leg['from']]}→{net.names[leg['to']]}")
        trip_times = net.trip_stops[leg["trip"]]
        i = next(k for k, (n, t) in enumerate(trip_times) if n == leg["from"] and t >= leg["board_time"] - 1e-6)
        alight = next(t for n, t in trip_times[i + 1:] if n == leg["to"])
        timed.append({"line": leg["line"], "mode": leg["mode"], "from": net.names[leg["from"]],
                      "to": net.names[leg["to"]], "board": fmt_time(leg["board_time"]), "alight": fmt_time(alight)})
    return km, segments, " / ".join(desc), timed


def plan(net: Network, origin: str, dest: tuple[float, float], depart: float,
         outside_seoul: bool = False, time_value: float = 0.0) -> pd.DataFrame:
    """후보 경로표. 첫 행이 추천 경로.

    time_value: 1분을 몇 원으로 칠지. 0이면 순수하게 가장 싼 경로,
                크게 할수록 조금 비싸도 빨리 도착하는 경로를 고른다.
    """
    arr, prev = net.earliest_arrivals(origin, depart)
    best: dict = {}  # 같은 이름(환승역의 여러 호선)은 가장 빨리 도착한 노드만
    for node, t in arr.items():
        name = net.names[node]
        if not math.isinf(t) and (name not in best or t < arr[best[name]]):
            best[name] = node
    rows = []
    for name, node in best.items():
        t = arr[node]
        legs = net.path_to(prev, node)
        ride_km, segments, desc, timed = _ride_info(net, legs)
        rides = [l for l in legs if l["type"] == "탑승"]
        used_bus = any(l["mode"] != "지하철" for l in rides)
        used_subway = any(l["mode"] == "지하철" for l in rides)
        if name != origin and not rides:  # 걷기만 하고 차를 안 탄 경우
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
        fare_s = transit_fare(ride_km, used_subway, used_bus)
        rows.append({
            "하차 위치": name if rides else f"{name} (바로 택시)",
            "경로": desc or "-",
            "첫 탑승": fmt_time(rides[0]["board_time"]) if rides else "-",
            "하차 시각": fmt_time(t) if rides else "-",
            "대중교통 거리(km)": round(ride_km, 1),
            "대중교통 요금": fare_s,
            "심야버스": "O" if used_bus else "",
            "마지막 이동": mode,
            "택시 거리(km)": round(last_km, 1) if mode == "택시" else 0.0,
            "할증": surcharge,
            "택시 요금": fare_t,
            "총 요금": fare_s + fare_t,
            "도착 예상": fmt_time(end),
            "소요(분)": int(round(end - depart)),
            "_end": end,
            "_score": fare_s + fare_t + time_value * (end - depart),
            "_direct": not rides,
            "_node": node,
            "_segments": segments,
            "_legs": timed,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["_score", "총 요금", "_end"]).reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    best = df.iloc[0]
    direct = df[df["_direct"]]
    direct_fare = int(direct["총 요금"].min()) if not direct.empty else None
    return {
        "best": best,
        "direct_fare": direct_fare,
        "saving": (direct_fare - int(best["총 요금"])) if direct_fare is not None else 0,
    }
