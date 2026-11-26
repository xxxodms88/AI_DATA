"""지하철 노선·시간표 데이터 + 막차 반영 최단 도착 탐색 (Connection Scan Algorithm)

실제 데이터 형식 (data/transit/ 에 저장, 팀에서 공공데이터를 변환)
    stations.csv : line, station, seq, lat, lon
        - 서울교통공사 '1~8호선 역사 좌표(위경도) 정보' (서울 열린데이터광장 OA-22534)
    timetable.csv : trip_id, line, station, time
        - 서울교통공사 역별 열차 운행 시각표에서 22시 이후 열차만 뽑아 변환
        - trip_id = 열차번호(+방향), time = 'HH:MM' (자정 넘으면 '24:10' 또는 '00:10' 둘 다 가능)
        - 막차가 중간역에서 끝나는(행선지가 짧은) 열차도 시각표에 그대로 들어가 있어야 한다.

파일이 없으면 7호선(도봉산~가산디지털단지) 샘플로 동작한다.
  - 샘플 좌표: 공개 gist(jhj0517/korean-subway-station-list) 기반 근사값
  - 샘플 시간표: 가짜! (막차 시각·행선지를 그럴듯하게 만든 값)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import TRANSFER_MIN
from src.taxi import haversine_km

TRANSIT_DIR = Path(__file__).resolve().parent.parent / "data" / "transit"
DAY_START_MIN = 4 * 60  # 04시 이전 시각은 '전날 밤의 연장'으로 본다
CHANGE_MIN = 2          # 같은 역에서 다른 열차로 갈아탈 때 필요한 시간

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
def load_transit() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """(stations, timetable, 샘플 여부)"""
    sp, tp = TRANSIT_DIR / "stations.csv", TRANSIT_DIR / "timetable.csv"
    if sp.exists() and tp.exists():
        stations = pd.read_csv(sp)
        tt = pd.read_csv(tp)
        tt["time"] = tt["time"].map(parse_time)
        return stations, tt, False
    tt = sample_timetable()
    tt["time"] = tt["time"].map(parse_time)
    return sample_stations(), tt, True


# ------------------------------------------------------------------ 탐색
@dataclass
class Network:
    stations: pd.DataFrame
    timetable: pd.DataFrame
    coords: dict = field(init=False)
    connections: list = field(init=False)
    transfers: dict = field(init=False)

    def __post_init__(self):
        self.coords = {(r.line, r.station): (r.lat, r.lon) for r in self.stations.itertuples()}
        conns = []
        for trip, g in self.timetable.sort_values("time").groupby("trip_id", sort=False):
            g = g.sort_values("time")
            nodes = list(zip(g["line"], g["station"]))
            times = list(g["time"])
            for i in range(len(nodes) - 1):
                conns.append((times[i], times[i + 1], nodes[i], nodes[i + 1], trip))
        self.connections = sorted(conns, key=lambda c: (c[0], c[1]))
        by_name: dict[str, list] = {}
        for node in self.coords:
            by_name.setdefault(node[1], []).append(node)
        self.transfers = {n: [o for o in by_name[n[1]] if o != n] for n in self.coords}

    def nodes_of(self, station: str):
        return [n for n in self.coords if n[1] == station]

    def earliest_arrivals(self, origin: str, depart: float) -> tuple[dict, dict]:
        """출발역·출발시각에서 각 (호선, 역)에 가장 빨리 도착하는 시각과 경로 정보.

        Connection Scan Algorithm: 시간순으로 정렬한 '역 A -> 역 B 구간 운행' 목록을 한 번 훑는다.
        막차가 끊긴 구간은 시간표에 운행이 없으므로 자연스럽게 도달할 수 없게 된다.
        """
        arr = {n: math.inf for n in self.coords}
        prev: dict = {}
        for n in self.nodes_of(origin):
            arr[n] = depart
            prev[n] = None
        for n in self.nodes_of(origin):  # 출발역에서 다른 호선으로 환승
            for o in self.transfers[n]:
                arr[o] = min(arr[o], depart + TRANSFER_MIN)
                prev.setdefault(o, ("transfer", n))

        rides = {n: 0 for n in arr}  # 그 노드까지 탄 열차 수 (적을수록 좋음)
        trip_board: dict = {}  # trip -> (탑승 역, 탑승 시각, 그때까지 탄 열차 수)
        for dep, art, a, b, trip in self.connections:
            if dep < depart:
                continue
            ra = arr.get(a, math.inf)
            if ra < math.inf:
                # 다른 열차에서 내려 갈아타면 승강장 이동 시간이 필요하다
                need = ra + (CHANGE_MIN if prev.get(a) and prev[a][0] == "ride" else 0)
                if need <= dep and (trip not in trip_board or rides[a] < trip_board[trip][2]):
                    trip_board[trip] = (a, dep, rides[a])
            if trip in trip_board and art < arr.get(b, math.inf):
                arr[b] = art
                board_node, board_time, n_rides = trip_board[trip]
                prev[b] = ("ride", trip, board_node, board_time)
                rides[b] = n_rides + 1
                for o in self.transfers.get(b, []):
                    if art + TRANSFER_MIN < arr[o]:
                        arr[o] = art + TRANSFER_MIN
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
                             "board_time": board_time})
                node = board_node
        return legs[::-1]

    def ride_stops(self, trip: str, a, b) -> list:
        """열차 trip이 a에서 b까지 지나는 역 노드 목록 (지도·거리 계산용)."""
        g = self.timetable[self.timetable["trip_id"] == trip].sort_values("time")
        nodes = list(zip(g["line"], g["station"]))
        i, j = nodes.index(a), nodes.index(b)
        return nodes[i:j + 1]
