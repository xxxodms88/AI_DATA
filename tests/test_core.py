"""핵심 로직 테스트: python -m pytest -q"""
import pandas as pd

from src.analysis import compare_groups, detect_peaks, hourly_profile
from src.clustering import cluster_stations, station_ratio_vectors
from src.data_loader import add_features
from src.preprocess import clean, parse_hour, standardize
from src.recommend import recommend
from src.sample_data import make_sample

DF = add_features(make_sample(years=(2019, 2021)))


def test_parse_hour():
    assert parse_hour("05~06") == 5
    assert parse_hour("06시이전") == 5
    assert parse_hour("24시이후") == 24
    assert parse_hour("08시-09시 승차인원") == 8


def test_standardize_format_a():
    raw = pd.DataFrame({
        "날짜": ["2019-03-04"] * 2, "호선": ["7호선"] * 2, "역번호": [2738] * 2,
        "역명": ["숭실대입구(살피재)"] * 2, "구분": ["승차", "하차"],
        "05~06": [10, 3], "08~09": [1000, 2000],
    })
    out = clean(standardize(raw))
    row = out[out["hour"] == 8].iloc[0]
    assert row["station"] == "숭실대입구" and row["ride"] == 1000 and row["alight"] == 2000


def test_standardize_format_b():
    raw = pd.DataFrame({"사용월": [202105], "호선명": ["7"], "지하철역": ["숭실대입구"],
                        "08시-09시 승차인원": [5], "08시-09시 하차인원": [7]})
    out = clean(standardize(raw))
    assert out.iloc[0]["date"] == pd.Timestamp("2021-05-01") and out.iloc[0]["line"] == "7호선"


def test_profile_and_peaks():
    prof = hourly_profile(DF, "숭실대입구", day_type="평일")
    assert len(prof) == 20 and prof["mean"].gt(0).all()
    assert not detect_peaks(prof).empty


def test_recommend_picks_min():
    prof = hourly_profile(DF, "숭실대입구", day_type="평일")
    rec = recommend(prof, 8, 2)
    assert rec["best_hour"] in (6, 7, 8)
    assert rec["saving_pct"] >= 0


def test_compare_semester():
    res = compare_groups(DF, "숭실대입구", "period", "학기", "방학")
    assert res["유의(p<0.05)"].any()


def test_clustering():
    X = station_ratio_vectors(DF)
    result, centers = cluster_stations(X, 3)
    assert set(result["station"]) == set(X.index) and len(centers) == 3


# ---------------- 막차 택시비 기능 ----------------
from src.night_route import plan, summary  # noqa: E402
from src.taxi import subway_fare, taxi_fare  # noqa: E402
from src.transit import Network, load_transit, parse_time  # noqa: E402


def test_taxi_fare_table():
    assert taxi_fare(1.0, parse_time("12:00")) == 4800        # 기본거리 이내
    assert taxi_fare(1.0, parse_time("23:30")) == 6700        # 심야 40%
    assert taxi_fare(1.0, parse_time("22:30")) == 5800        # 심야 20%
    assert taxi_fare(1.6 + 0.131, parse_time("12:00")) == 4900
    assert taxi_fare(5, parse_time("01:00"), outside_seoul=True) > taxi_fare(5, parse_time("01:00"))


def test_subway_fare():
    assert subway_fare(0) == 0 and subway_fare(10) == 1550
    assert subway_fare(10.1) == 1650 and subway_fare(15) == 1650 and subway_fare(15.1) == 1750


def test_parse_time_after_midnight():
    assert parse_time("00:10") == 1450 and parse_time("24:10") == 1450 and parse_time("23:50") == 1430


def _tiny_network():
    """A - B - C 한 줄 + B에서 다른 호선 X로 환승 가능한 작은 노선"""
    st = pd.DataFrame([
        ("1호선", "A", 0, 37.50, 127.00), ("1호선", "B", 1, 37.52, 127.00), ("1호선", "C", 2, 37.54, 127.00),
        ("2호선", "B", 0, 37.52, 127.00), ("2호선", "X", 1, 37.52, 127.05),
    ], columns=["line", "station", "seq", "lat", "lon"])
    tt = pd.DataFrame([
        ("t1", "1호선", "A", "23:50"), ("t1", "1호선", "B", "23:55"), ("t1", "1호선", "C", "24:00"),
        ("t2", "1호선", "A", "24:10"), ("t2", "1호선", "B", "24:15"),          # 막차는 B까지만
        ("u1", "2호선", "B", "24:01"), ("u1", "2호선", "X", "24:06"),           # 환승 막차
    ], columns=["trip_id", "line", "station", "time"])
    tt["time"] = tt["time"].map(parse_time)
    return Network(st, tt)


def test_last_train_cuts_route():
    net = _tiny_network()
    arr, _ = net.earliest_arrivals("A", parse_time("23:45"))
    assert arr[("1호선", "C")] == parse_time("24:00")
    assert arr[("2호선", "X")] == parse_time("24:06")            # 23:55 B 도착 + 환승 5분 <= 24:01
    arr, _ = net.earliest_arrivals("A", parse_time("24:05"))
    assert arr[("1호선", "B")] == parse_time("24:15")
    assert arr[("1호선", "C")] == float("inf")                     # 막차가 B에서 끝남
    assert arr[("2호선", "X")] == float("inf")                     # 환승 열차도 이미 끊김


def test_plan_prefers_subway_then_taxi():
    net = _tiny_network()
    dest = (37.60, 127.00)                                         # C보다 더 북쪽
    df = plan(net, "A", dest, parse_time("24:05"))
    s = summary(df)
    assert s["best"]["하차 위치"] == "B" and s["saving"] > 0


def test_sample_network_runs():
    stations, tt, _ = load_transit()
    net = Network(stations, tt)
    df = plan(net, "숭실대입구", net.coords[("7호선", "노원")], parse_time("00:20"))
    assert not df.empty and df.iloc[0]["총 요금"] <= df[df["_direct"]]["총 요금"].min()


# ---------------- 심야버스 ----------------
from src.bus import build_timetable, convert, sample_bus  # noqa: E402
from src.taxi import transit_fare  # noqa: E402


def test_bus_timetable_from_headway():
    routes = pd.DataFrame([("N1", 0, "100", "가", 37.50, 127.0), ("N1", 1, "101", "나", 37.51, 127.0)],
                          columns=["route", "seq", "stop_id", "stop_name", "lat", "lon"])
    sch = pd.DataFrame([{"route": "N1", "first": "23:30", "last": "00:30", "headway_min": 30}])
    st, tt = build_timetable(routes, sch)
    assert tt["trip_id"].nunique() == 3                      # 23:30, 24:00, 24:30
    assert set(st["name"]) == {"가", "나"} and (st["mode"] == "심야버스").all()


def test_subway_then_walk_to_night_bus():
    """지하철로 B까지 간 뒤 근처 정류장(80m)까지 걸어가 심야버스로 갈아타는 경로를 찾는다."""
    sub_st = pd.DataFrame([("1호선", "A", 0, 37.50, 127.00), ("1호선", "B", 1, 37.52, 127.00)],
                          columns=["line", "station", "seq", "lat", "lon"])
    sub_st["name"], sub_st["mode"] = sub_st["station"], "지하철"
    sub_tt = pd.DataFrame([("t1", "1호선", "A", "24:00"), ("t1", "1호선", "B", "24:05")],
                          columns=["trip_id", "line", "station", "time"])
    routes = pd.DataFrame([("N9", 0, "900", "B정류장", 37.5207, 127.0), ("N9", 1, "901", "먼곳", 37.62, 127.0)],
                          columns=["route", "seq", "stop_id", "stop_name", "lat", "lon"])
    bus_st, bus_tt = build_timetable(routes, pd.DataFrame(
        [{"route": "N9", "first": "24:10", "last": "24:10", "headway_min": 30}]))
    tt = pd.concat([sub_tt.assign(time=sub_tt["time"].map(parse_time)), bus_tt], ignore_index=True)
    net = Network(pd.concat([sub_st, bus_st], ignore_index=True), tt)

    arr, prev = net.earliest_arrivals("A", parse_time("23:55"))
    far = ("N9", "901")
    assert arr[far] < float("inf")
    legs = net.path_to(prev, far)
    assert [l["type"] for l in legs] == ["탑승", "환승", "탑승"]
    df = plan(net, "A", (37.625, 127.0), parse_time("23:55"))
    best = df.iloc[0]
    assert best["하차 위치"] == "먼곳" and best["심야버스"] == "O"
    assert best["대중교통 요금"] == transit_fare(best["대중교통 거리(km)"], True, True)


def test_transit_fare_combos():
    assert transit_fare(5, False, True) == 2500
    assert transit_fare(5, True, False) == 1550
    assert transit_fare(12, True, True) == 2600


def test_time_value_prefers_faster():
    stations, tt, _ = load_transit()
    net = Network(stations, tt)
    dest = net.coords[("7호선", "노원")]
    cheap = plan(net, "숭실대입구", dest, parse_time("00:20"), time_value=0).iloc[0]
    fast = plan(net, "숭실대입구", dest, parse_time("00:20"), time_value=500).iloc[0]
    assert cheap["총 요금"] <= fast["총 요금"] and fast["소요(분)"] <= cheap["소요(분)"]


def test_sample_bus_loop_is_consistent():
    st, tt = sample_bus()
    assert tt.groupby("trip_id")["time"].apply(lambda s: s.is_monotonic_increasing).all()


def test_convert_bus_csv(tmp_path):
    src = tmp_path / "raw.csv"
    pd.DataFrame({"노선명": ["N61", "N61", "100"], "순번": [1, 2, 1], "ARS-ID": ["1", "2", "3"],
                  "정류소명": ["가", "나", "다"], "X좌표": [126.9, 126.91, 127.0], "Y좌표": [37.5, 37.51, 37.6]}
                 ).to_csv(src, index=False, encoding="cp949")
    out = convert(str(src), ["N61"], tmp_path)
    df = pd.read_csv(out)
    assert list(df["stop_name"]) == ["가", "나"] and (tmp_path / "bus_schedule.csv").exists()


def test_convert_bus_xlsx(tmp_path):
    src = tmp_path / "raw.xlsx"
    pd.DataFrame({"노선ID": [1, 1], "노선명": ["N61", "N61"], "순번": [1, 2], "NODE_ID": [10, 11],
                  "ARS_ID": ["01001", "01002"], "정류소명": ["가", "나"],
                  "X좌표": [126.9, 126.91], "Y좌표": [37.5, 37.51]}).to_excel(src, index=False)
    out = convert(str(src), ["N61"], tmp_path)
    assert list(pd.read_csv(out)["stop_name"]) == ["가", "나"]
