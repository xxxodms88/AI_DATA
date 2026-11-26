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
    assert s["best"]["하차역"] == "B" and s["saving"] > 0


def test_sample_network_runs():
    stations, tt, _ = load_transit()
    net = Network(stations, tt)
    df = plan(net, "숭실대입구", net.coords[("7호선", "노원")], parse_time("00:20"))
    assert not df.empty and df.iloc[0]["총 요금"] <= df[df["_direct"]]["총 요금"].min()
