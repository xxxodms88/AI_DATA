"""지하철 노선·시간표 데이터 + 막차 반영 최단 도착 탐색 (Connection Scan Algorithm)

실제 데이터 형식 (data/transit/ 에 저장, 팀에서 공공데이터를 변환)
    stations.csv : line, station, seq, lat, lon
        - 서울교통공사 '1~8호선 역사 좌표(위경도) 정보' (서울 열린데이터광장 OA-22534)
    timetable.csv : trip_id, line, station, time
        - 서울교통공사 역별 열차 운행 시각표에서 22시 이후 열차만 뽑아 변환
        - trip_id = 열차번호(+방향), time = 'HH:MM' (자정 넘으면 '24:10' 또는 '00:10' 둘 다 가능)
        - 막차가 중간역에서 끝나는(행선지가 짧은) 열차도 시각표에 그대로 들어가 있어야 한다.

심야버스는 src/bus.py 참고 (같은 시간표 형식으로 바꿔서 함께 탐색한다).

파일이 없으면 7호선(도봉산~가산디지털단지) 샘플로 동작한다.
  - 샘플 좌표: 공개 gist(jhj0517/korean-subway-station-list) 기반 근사값
  - 샘플 시간표: 가짜! (막차 시각·행선지를 그럴듯하게 만든 값)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import TRANSFER_MIN, WALK_SPEED_KMH
from src.taxi import haversine_km

TRANSIT_DIR = Path(__file__).resolve().parent.parent / "data" / "transit"
DAY_START_MIN = 4 * 60  # 04시 이전 시각은 '전날 밤의 연장'으로 본다
CHANGE_MIN = 2          # 같은 역에서 다른 열차로 갈아탈 때 필요한 시간
WALK_TRANSFER_KM = 0.4  # 이 거리 이내 정류장·역은 걸어서 환승 가능
WALK_DETOUR = 1.2       # 걷는 길 우회 계수

_LINE7 = [
    ("도봉산", 37.6893, 127.0462), ("수락산", 37.6778, 127.0554), ("마들", 37.6653, 127.0576),
    ("노원", 37.6543, 127.0606), ("중계", 37.6451, 127.0641), ("하계", 37.6359, 127.0682),
    ("공릉", 37.6258, 127.0729), ("태릉입구", 37.6173, 127.0749), ("먹골", 37.6105, 127.0778),
    ("중화", 37.6026, 127.0793), ("상봉", 37.5961, 127.0862), ("면목", 37.5885, 127.0877),
    ("사가정", 37.5810, 127.0885), ("용마산", 37.5738, 127.0868), ("중곡", 37.5656, 127.0842),
    ("군자", 37.5571, 127.0795), ("어린이대공원", 37.5480, 127.0746), ("건대입구", 37.5407, 127.0702),
    ("자양", 37.5316, 127.0667), ("청담", 37.5193, 127.0533), ("강남구청", 37.5171, 127.0413),
    ("학동", 37.5142, 127.0317), ("논현", 37.5110, 127.0219), ("반포", 37.5082, 127.0118),
    ("고속터미널", 37.5048, 127.0049), ("내방", 37.4875, 126.9936), ("이수", 37.4860, 126.9816),
    ("남성", 37.4846, 126.9713), ("숭실대입구", 37.4960, 126.9532), ("상도", 37.5025, 126.9483),
    ("장승배기", 37.5049, 126.9390), ("신대방삼거리", 37.4995, 126.9271), ("보라매", 37.4997, 126.9208),
    ("신풍", 37.5001, 126.9096), ("대림", 37.4930, 126.8958), ("남구로", 37.4861, 126.8873),
    ("가산디지털단지", 37.4816, 126.8826),
]


def parse_time(s) -> float:
    """'23:50' -> 1430, '00:10' / '24:10' -> 1450 (자정 넘으면 1440 이상)"""
    if isinstance(s, (int, float)):
        m = float(s)
    else:
        h, mi = str(s).strip().split(":")[:2]
        m = int(h) * 60 + int(mi)
    return m + 1440 if m < DAY_START_MIN else m


def fmt_time(m: float) -> str:
    m = int(round(m)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


# ------------------------------------------------------------------ 샘플 데이터
def sample_stations() -> pd.DataFrame:
    return pd.DataFrame([{"line": "7호선", "station": n, "seq": i, "lat": la, "lon": lo}
                         for i, (n, la, lo) in enumerate(_LINE7)])


def sample_timetable() -> pd.DataFrame:
    """가짜 심야 시간표: 22:00부터 10분 간격, 마지막 몇 대는 중간역까지만 가는 열차."""
    st = sample_stations()
    seg = [haversine_km(*st.iloc[i][["lat", "lon"]], *st.iloc[i + 1][["lat", "lon"]])
           for i in range(len(st) - 1)]
    run = [d / 33 * 60 + 0.5 for d in seg]  # 표정속도 33km/h + 정차 30초
    names = list(st["station"])

    # (방향, 출발역 index, 종착역 index, 출발 시각 목록)
    plans = []
    full_up = [22 * 60 + i * 10 for i in range(0, 13)]  # 22:00 ~ 24:00 가산 -> 도봉산
    plans.append(("상", len(names) - 1, 0, full_up))
    plans.append(("상", len(names) - 1, names.index("건대입구"), [24 * 60 + 10]))
    plans.append(("상", len(names) - 1, names.index("고속터미널"), [24 * 60 + 20]))
    full_dn = [22 * 60 + i * 10 for i in range(0, 12)]  # 22:00 ~ 23:50 도봉산 -> 가산
    plans.append(("하", 0, len(names) - 1, full_dn))
    plans.append(("하", 0, names.index("이수"), [24 * 60]))
    plans.append(("하", names.index("건대입구"), names.index("숭실대입구"), [24 * 60 + 15]))

    rows = []
    for direction, a, b, starts in plans:
        step = 1 if b > a else -1
        for k, t0 in enumerate(starts):
            trip = f"S{direction}{a:02d}{b:02d}_{k}"
            t = t0
            for i in range(a, b + step, step):
                rows.append({"trip_id": trip, "line": "7호선", "station": names[i],
                             "time": round(t, 1)})
                if i != b:
                    t += run[min(i, i + step)]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 데이터 로드
def load_transit(include_bus: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(stations, timetable, 상태) - 상태: {'subway_sample': bool, 'bus': '실제'|'샘플'|'없음'}

    stations 컬럼: line, station(노드 ID), name(화면 표시 이름), lat, lon
    지하철은 station = name = 역명, 버스는 station = 정류소 ID(ARS), name = 정류소명
    """
    sp, tp = TRANSIT_DIR / "stations.csv", TRANSIT_DIR / "timetable.csv"
    if sp.exists() and tp.exists():
        stations, tt, subway_sample = pd.read_csv(sp), pd.read_csv(tp), False
    else:
        stations, tt, subway_sample = sample_stations(), sample_timetable(), True
    tt["time"] = tt["time"].map(parse_time)
    if "name" not in stations:
        stations["name"] = stations["station"]
    stations["mode"] = "지하철"

    bus_state = "없음"
    if include_bus:
        from src.bus import load_bus

        bus = load_bus(allow_sample=subway_sample)
        if bus is not None:
            bus_st, bus_tt, bus_state = bus
            stations = pd.concat([stations, bus_st], ignore_index=True)
            tt = pd.concat([tt, bus_tt], ignore_index=True)
    stations["station"] = stations["station"].astype(str)
    tt["station"] = tt["station"].astype(str)
    return stations, tt, {"subway_sample": subway_sample, "bus": bus_state}


# ------------------------------------------------------------------ 탐색
def _walk_min(km: float) -> float:
    return km * WALK_DETOUR / WALK_SPEED_KMH * 60 + 1  # +1분: 출구·횡단보도


@dataclass
class Network:
    stations: pd.DataFrame
    timetable: pd.DataFrame
    coords: dict = field(init=False)
    names: dict = field(init=False)
    modes: dict = field(init=False)
    connections: list = field(init=False)
    transfers: dict = field(init=False)
    trip_stops: dict = field(init=False)

    def __post_init__(self):
        st = self.stations.copy()
        if "name" not in st:
            st["name"] = st["station"]
        if "mode" not in st:
            st["mode"] = "지하철"
        st["station"] = st["station"].astype(str)
        self.coords = {(r.line, r.station): (r.lat, r.lon) for r in st.itertuples()}
        self.names = {(r.line, r.station): r.name for r in st.itertuples()}
        self.modes = {(r.line, r.station): r.mode for r in st.itertuples()}

        tt = self.timetable.copy()
        tt["station"] = tt["station"].astype(str)
        conns, self.trip_stops = [], {}
        for trip, g in tt.sort_values("time").groupby("trip_id", sort=False):
            g = g.sort_values("time", kind="stable")
            nodes = list(zip(g["line"], g["station"]))
            times = list(g["time"])
            self.trip_stops[trip] = list(zip(nodes, times))
            for i in range(len(nodes) - 1):
                conns.append((times[i], times[i + 1], nodes[i], nodes[i + 1], trip))
        self.connections = sorted(conns, key=lambda c: (c[0], c[1]))
        self.transfers = self._build_transfers()

    def _build_transfers(self) -> dict:
        """환승(걷기) 연결: 같은 이름 = TRANSFER_MIN, 그 밖에 WALK_TRANSFER_KM 이내 노드끼리 걷기."""
        out: dict = {n: {} for n in self.coords}
        by_name: dict = {}
        for n, name in self.names.items():
            by_name.setdefault(name, []).append(n)
        for group in by_name.values():
            for a in group:
                for b in group:
                    if a != b:
                        out[a][b] = TRANSFER_MIN
        # 가까운 노드끼리 (격자로 나눠서 주변 칸만 비교)
        cell = 0.005  # 약 500m
        grid: dict = {}
        for n, (la, lo) in self.coords.items():
            grid.setdefault((int(la / cell), int(lo / cell)), []).append(n)
        for (gx, gy), nodes in grid.items():
            near = [m for dx in (-1, 0, 1) for dy in (-1, 0, 1) for m in grid.get((gx + dx, gy + dy), [])]
            for a in nodes:
                for b in near:
                    if a == b or a[0] == b[0]:
                        continue
                    km = haversine_km(*self.coords[a], *self.coords[b])
                    if km <= WALK_TRANSFER_KM:
                        t = max(_walk_min(km), 2.0)
                        out[a][b] = min(out[a].get(b, math.inf), t)
        return out

    def nodes_of(self, name: str):
        return [n for n, nm in self.names.items() if nm == name]

    def earliest_arrivals(self, origin: str, depart: float) -> tuple[dict, dict]:
        """출발지(표시 이름)·출발시각에서 각 노드에 가장 빨리 도착하는 시각과 경로 정보.

        Connection Scan Algorithm: 시간순으로 정렬한 'A -> B 구간 운행'(지하철·버스) 목록을 한 번 훑는다.
        막차가 끊긴 구간은 시간표에 운행이 없으므로 자연스럽게 도달할 수 없게 된다.
        """
        arr = {n: math.inf for n in self.coords}
        prev: dict = {}
        rides = {n: 0 for n in arr}  # 그 노드까지 탄 차량 수 (적을수록 좋음)
        for n in self.nodes_of(origin):
            arr[n] = depart
            prev[n] = None
        for n in self.nodes_of(origin):  # 출발지에서 걸어서 갈 수 있는 다른 호선·정류장
            for o, w in self.transfers[n].items():
                if depart + w < arr[o]:
                    arr[o] = depart + w
                    prev[o] = ("transfer", n)

        trip_board: dict = {}  # trip -> (탑승 노드, 탑승 시각, 그때까지 탄 차량 수)
        for dep, art, a, b, trip in self.connections:
            if dep < depart:
                continue
            ra = arr.get(a, math.inf)
            if ra < math.inf:
                # 다른 차에서 내려 같은 자리에서 갈아타도 이동 시간이 필요하다
                need = ra + (CHANGE_MIN if prev.get(a) and prev[a][0] == "ride" else 0)
                if need <= dep and (trip not in trip_board or rides[a] < trip_board[trip][2]):
                    trip_board[trip] = (a, dep, rides[a])
            if trip in trip_board and art < arr.get(b, math.inf):
                arr[b] = art
                board_node, board_time, n_rides = trip_board[trip]
                prev[b] = ("ride", trip, board_node, board_time)
                rides[b] = n_rides + 1
                for o, w in self.transfers.get(b, {}).items():
                    if art + w < arr[o]:
                        arr[o] = art + w
                        prev[o] = ("transfer", b)
                        rides[o] = rides[b]
        return arr, prev

    def path_to(self, prev: dict, node) -> list[dict]:
        """도착 노드까지의 구간(탑승/환승) 목록."""
        legs = []
        while prev.get(node) is not None:
            p = prev[node]
            if p[0] == "transfer":
                legs.append({"type": "환승", "from": p[1], "to": node})
                node = p[1]
            else:
                _, trip, board_node, board_time = p
                legs.append({"type": "탑승", "trip": trip, "from": board_node, "to": node,
                             "board_time": board_time, "mode": self.modes.get(board_node, "지하철"),
                             "line": board_node[0]})
                node = board_node
        return legs[::-1]

    def ride_stops(self, trip: str, a, b, board_time: float | None = None) -> list:
        """차량 trip이 a에서 b까지 지나는 노드 목록 (지도·거리 계산용). 순환 노선도 처리."""
        stops = self.trip_stops[trip]
        i = next(k for k, (n, t) in enumerate(stops)
                 if n == a and (board_time is None or t >= board_time - 1e-6))
        j = next(k for k in range(i + 1, len(stops)) if stops[k][0] == b)
        return [n for n, _ in stops[i:j + 1]]
