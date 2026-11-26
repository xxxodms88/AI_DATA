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
