"""심야버스(N버스)를 지하철과 같은 시간표 형식으로 바꿔서 함께 탐색한다.

필요한 파일 (data/transit/)
    bus_routes.csv   : route, seq, stop_id, stop_name, lat, lon     (노선별 정류장 순서·좌표)
    bus_schedule.csv : route, first, last, headway_min              (기점 첫차·막차 시각, 배차간격)

bus_routes.csv 만들기
    서울 열린데이터광장 '서울시 버스노선별 정류장 정보' CSV를 받아서
        python -m src.bus convert 받은파일.csv --routes N13 N16 N61
    처럼 필요한 N버스 노선만 뽑는다. (좌표가 위경도(WGS84)인 파일이어야 함)
    bus_schedule.csv 는 첫 실행 때 기본값(23:30 / 03:50 / 30분)으로 틀을 만들어 주니,
    서울버스 앱·서울시 버스정보 사이트에서 노선별 첫차·막차·배차간격을 확인해 고쳐 넣는다.

배차간격 기반이라 실제 버스 도착 시각과는 몇 분씩 차이가 날 수 있다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.taxi import haversine_km

TRANSIT_DIR = Path(__file__).resolve().parent.parent / "data" / "transit"
BUS_SPEED_KMH = 25      # 심야 버스 평균 주행 속도
BUS_DWELL_MIN = 0.5     # 정류장 정차 시간
ROAD_FACTOR_BUS = 1.25  # 정류장 사이 직선거리 -> 도로거리

# 샘플(가짜) 심야버스: 숭실대입구역 ~ 노원역을 7호선과 비슷하게 잇는 '가상의' 노선
_SAMPLE_PATH = ["숭실대입구", "남성", "이수", "고속터미널", "논현", "강남구청", "청담", "건대입구",
                "군자", "중곡", "상봉", "먹골", "태릉입구", "공릉", "하계", "중계", "노원"]


def _hhmm(s) -> float:
    from src.transit import parse_time

    return parse_time(s)


def build_timetable(routes: pd.DataFrame, schedule: pd.DataFrame,
                    mode: str = "심야버스") -> tuple[pd.DataFrame, pd.DataFrame]:
    """노선·배차 정보 -> (stations, timetable) (transit.Network 형식)"""
    routes = routes.copy()
    routes["stop_id"] = routes["stop_id"].astype(str)
    stations = (routes.drop_duplicates(["route", "stop_id"])
                .rename(columns={"route": "line", "stop_id": "station", "stop_name": "name"})
                [["line", "station", "name", "lat", "lon"]])
    stations["mode"] = mode

    rows = []
    for sch in schedule.itertuples():
        r = routes[routes["route"] == sch.route].sort_values("seq")
        if r.empty:
            continue
        run = [0.0]
        pts = list(zip(r["lat"], r["lon"]))
        for a, b in zip(pts, pts[1:]):
            km = haversine_km(*a, *b) * ROAD_FACTOR_BUS
            run.append(run[-1] + km / BUS_SPEED_KMH * 60 + BUS_DWELL_MIN)
        t, last, k = _hhmm(sch.first), _hhmm(sch.last), 0
        while t <= last + 1e-6:
            trip = f"{sch.route}_{k}"
            for stop, dt in zip(r["stop_id"], run):
                rows.append({"trip_id": trip, "line": sch.route, "station": stop, "time": round(t + dt, 1)})
            t += float(sch.headway_min)
            k += 1
    return stations, pd.DataFrame(rows, columns=["trip_id", "line", "station", "time"])


def sample_bus() -> tuple[pd.DataFrame, pd.DataFrame]:
    """가짜 노선 'N샘플' (왕복). 정류장은 지하철역에서 약 60m 떨어진 곳에 둔다."""
    from src.transit import _LINE7

    coords = {n: (la, lo) for n, la, lo in _LINE7}
    path = _SAMPLE_PATH + _SAMPLE_PATH[-2::-1]  # 노원에서 다시 숭실대입구로
    routes = pd.DataFrame([
        {"route": "N샘플", "seq": i, "stop_id": f"NS{i:02d}", "stop_name": f"{n}역",
         "lat": coords[n][0], "lon": coords[n][1] + 0.0007}
        for i, n in enumerate(path)
    ])
    schedule = pd.DataFrame([{"route": "N샘플", "first": "23:40", "last": "03:30", "headway_min": 30}])
    return build_timetable(routes, schedule)


def load_bus(allow_sample: bool) -> tuple[pd.DataFrame, pd.DataFrame, str] | None:
    rp, sp = TRANSIT_DIR / "bus_routes.csv", TRANSIT_DIR / "bus_schedule.csv"
    if rp.exists() and sp.exists():
        st, tt = build_timetable(pd.read_csv(rp), pd.read_csv(sp))
        tt["time"] = tt["time"].astype(float)
        return st, tt, "실제"
    if allow_sample:
        st, tt = sample_bus()
        return st, tt, "샘플"
    return None


# ------------------------------------------------------------------ 변환 스크립트
_COLS = {
    "route": ["노선명", "ROUTE_NM", "노선번호", "노선"],
    "seq": ["순번", "SEQ", "STATION_ORD", "정류소순번", "정류장순번"],
    "stop_id": ["ARS-ID", "ARS_ID", "ARSID", "정류소번호", "NODE_ID", "표준ID"],
    "stop_name": ["정류소명", "정류장명", "STATION_NM", "NODE_NM", "역명"],
    "lon": ["X좌표", "GPS_X", "X", "경도"],
    "lat": ["Y좌표", "GPS_Y", "Y", "위도"],
}


def convert(src_csv: str, routes: list[str], out_dir: Path = TRANSIT_DIR) -> Path:
    from src.preprocess import read_csv_any_encoding

    raw = read_csv_any_encoding(src_csv).rename(columns=lambda c: str(c).strip())
    mapping = {}
    for key, cands in _COLS.items():
        found = next((c for c in cands if c in raw.columns), None)
        if not found:
            raise SystemExit(f"'{key}' 컬럼을 찾지 못했습니다. 파일 컬럼: {list(raw.columns)}")
        mapping[found] = key
    df = raw.rename(columns=mapping)[list(_COLS)]
    df["route"] = df["route"].astype(str).str.strip()
    df = df[df["route"].isin(routes)]
    if df.empty:
        raise SystemExit(f"노선 {routes}를 찾지 못했습니다.")
    if not (df["lat"].between(33, 39).all() and df["lon"].between(124, 132).all()):
        raise SystemExit("좌표가 위경도(WGS84)가 아닌 것 같습니다. 위경도 좌표가 들어 있는 파일을 받아 주세요.")

    out_dir.mkdir(parents=True, exist_ok=True)
    rp = out_dir / "bus_routes.csv"
    df.sort_values(["route", "seq"]).to_csv(rp, index=False, encoding="utf-8-sig")
    sp = out_dir / "bus_schedule.csv"
    if not sp.exists():
        pd.DataFrame([{"route": r, "first": "23:30", "last": "03:50", "headway_min": 30}
                      for r in sorted(df["route"].unique())]).to_csv(sp, index=False, encoding="utf-8-sig")
        print(f"{sp} 틀을 만들었습니다. 노선별 첫차·막차·배차간격을 실제 값으로 고쳐 주세요!")
    print(f"저장 완료: {rp} (노선 {df['route'].nunique()}개, 정류장 {len(df)}개)")
    return rp


def main():
    ap = argparse.ArgumentParser(description="심야버스 노선 데이터 변환")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="서울시 버스노선별 정류장 정보 CSV -> bus_routes.csv")
    c.add_argument("csv")
    c.add_argument("--routes", nargs="+", required=True, help="예: N13 N16 N61")
    args = ap.parse_args()
    convert(args.csv, args.routes)


if __name__ == "__main__":
    main()
