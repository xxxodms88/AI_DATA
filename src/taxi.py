"""택시·지하철 요금 계산"""
from __future__ import annotations

import math

from src.config import (ROAD_FACTOR, SUBWAY_BASE_FARE, SUBWAY_BASE_KM, SUBWAY_EXTRA, TAXI_BASE_KM,
                        TAXI_FARE_DAY, TAXI_FARE_NIGHT20, TAXI_FARE_NIGHT40,
                        TAXI_OUTSIDE_SURCHARGE, TAXI_UNIT_M)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(lat1, lon1, lat2, lon2) -> float:
    """직선거리에 보정 계수를 곱한 추정 도로거리. (정확한 값은 길찾기 API 필요)"""
    return haversine_km(lat1, lon1, lat2, lon2) * ROAD_FACTOR


def fare_table(minute_of_day: float) -> tuple[int, int, str]:
    """탑승 시각(자정 기준 분, 24시 이후는 1440 이상 가능)의 (기본요금, 거리요금, 이름)"""
    h = int(minute_of_day // 60) % 24
    if h >= 23 or h < 2:
        return (*TAXI_FARE_NIGHT40, "심야 40%")
    if h == 22 or 2 <= h < 4:
        return (*TAXI_FARE_NIGHT20, "심야 20%")
    return (*TAXI_FARE_DAY, "일반")


def taxi_fare(km: float, board_minute: float, outside_seoul: bool = False) -> int:
    """서울 중형택시 예상 요금 (시간요금·교통상황은 반영하지 않음)."""
    base, unit, _ = fare_table(board_minute)
    extra_m = max(0.0, km * 1000 - TAXI_BASE_KM * 1000)
    fare = base + math.ceil(extra_m / TAXI_UNIT_M) * unit
    if outside_seoul:  # 시계외 할증은 주간 요금 기준으로 더해짐 (심야와 합쳐 최대 60%)
        day_base, day_unit = TAXI_FARE_DAY
        fare += (day_base + math.ceil(extra_m / TAXI_UNIT_M) * day_unit) * TAXI_OUTSIDE_SURCHARGE
    return int(round(fare, -2))  # 십원 단위에서 반올림


def subway_fare(rail_km: float) -> int:
    """지하철 거리비례 요금. 환승해도 한 번만 낸다(통합요금)."""
    if rail_km <= 0:
        return 0
    fare, prev = SUBWAY_BASE_FARE, SUBWAY_BASE_KM
    for upper, step, add in SUBWAY_EXTRA:
        if rail_km <= prev:
            break
        seg = min(rail_km, upper) - prev
        fare += math.ceil(seg / step) * add
        prev = upper
    return fare


def transit_fare(km: float, used_subway: bool, used_bus: bool) -> int:
    """대중교통 요금 (교통카드, 통합환승 단순화).

    - 버스만: 심야버스 기본요금
    - 지하철만: 지하철 거리비례 요금
    - 둘 다: 더 비싼 기본요금(심야버스) + 10km 초과 거리 추가요금
    실제 통합환승 요금 규칙은 더 복잡하니 '추정치'로 표시한다.
    """
    from src.config import NIGHT_BUS_FARE

    if not used_subway and not used_bus:
        return 0
    if used_bus and not used_subway:
        return NIGHT_BUS_FARE
    fare = subway_fare(km)
    if used_bus:
        fare += NIGHT_BUS_FARE - SUBWAY_BASE_FARE
    return fare
