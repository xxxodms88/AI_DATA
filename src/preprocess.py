"""[팀원 1] 데이터 수집·전처리

서울교통공사 / 서울 열린데이터광장 CSV를 읽어 하나의 형식(long format)으로 통일한다.

통일 형식 (한 행 = 역 x 날짜 x 시간대)
    date(datetime), line(str), station(str), hour(int 5~24), ride(int), alight(int)

지원하는 원본 형식
    A. 역별 일별 시간대별 승하차인원 (2008~2021)
       날짜 | 호선 | 역번호 | 역명 | 구분(승차/하차) | 05~06 | 06~07 | ... | 24~
    B. 지하철 호선별 역별 시간대별 승하차 인원 (월 단위)
       사용월 | 호선명 | 지하철역 | 04시-05시 승차인원 | 04시-05시 하차인원 | ...

사용법 (터미널)
    python -m src.preprocess data/raw --out data/processed/subway_clean.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from src.config import HOURS

ENCODINGS = ["cp949", "utf-8-sig", "utf-8", "euc-kr"]

DATE_COLS = ["날짜", "사용일자", "일자", "수송일자", "사용월", "date"]
LINE_COLS = ["호선", "호선명", "노선명", "line"]
STATION_COLS = ["역명", "지하철역", "역사명", "station"]
KIND_COLS = ["구분", "승하차구분"]


def read_csv_any_encoding(path: str | Path) -> pd.DataFrame:
    """연도마다 다른 인코딩(cp949/utf-8)을 차례로 시도해서 읽는다."""
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, thousands=",")
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise ValueError(f"인코딩을 알 수 없는 파일: {path}") from last_err


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.strip(): c for c in df.columns}
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    return None


def parse_hour(col: str) -> int | None:
    """'05~06', '05시-06시', '06시이전', '24시이후', '05시-06시 승차인원' -> 시작 시각"""
    s = str(col).replace(" ", "")
    if "이전" in s:
        return 5
    m = re.search(r"(\d{1,2})", s)
    if not m:
        return None
    h = int(m.group(1))
    if "이후" in s:
        return 24
    h = 24 if h in (0, 24) else h
    return max(5, min(24, h))  # 04시대는 05시대로, 01시 이후는 24시대로 합침


def parse_dates(s: pd.Series) -> pd.Series:
    """'2021-05-03', '20210503', 20210503 -> 날짜 / 월 단위 '202105' -> 2021-05-01"""
    digits = s.astype(str).str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
    digits = digits.where(digits.str.len() != 6, digits + "01")
    return pd.to_datetime(digits, format="%Y%m%d", errors="coerce")


def normalize_station(name: str) -> str:
    """'숭실대입구(살피재)' / '숭실대입구역' -> '숭실대입구'"""
    s = re.sub(r"\(.*?\)", "", str(name)).strip()
    return re.sub(r"역$", "", s) if len(s) > 2 else s


def normalize_line(line) -> str:
    """'7', 7, '7호선', '07호선' -> '7호선'"""
    m = re.search(r"(\d+)", str(line))
    return f"{int(m.group(1))}호선" if m else str(line).strip()


def _hour_columns(df: pd.DataFrame, keyword: str | None = None) -> dict[str, int]:
    out = {}
    for c in df.columns:
        if keyword and keyword not in str(c):
            continue
        if re.search(r"\d{1,2}\s*(시|~|-)", str(c)) or "이전" in str(c) or "이후" in str(c):
            h = parse_hour(c)
            if h is not None:
                out[c] = h
    return out


def standardize(raw: pd.DataFrame) -> pd.DataFrame:
    """원본 DataFrame 하나를 통일 형식으로 바꾼다."""
    raw = raw.rename(columns=lambda c: str(c).strip())
    date_c = _find_col(raw, DATE_COLS)
    line_c = _find_col(raw, LINE_COLS)
    sta_c = _find_col(raw, STATION_COLS)
    kind_c = _find_col(raw, KIND_COLS)
    if not (date_c and line_c and sta_c):
        raise ValueError(f"날짜/호선/역명 컬럼을 찾지 못함: {list(raw.columns)[:10]}")

    id_cols = [date_c, line_c, sta_c]

    if kind_c:  # 형식 A: 승차/하차가 행으로 나뉜 wide 형식
        hour_map = _hour_columns(raw)
        long = raw.melt(id_vars=id_cols + [kind_c], value_vars=list(hour_map),
                        var_name="hour_col", value_name="count")
        long["hour"] = long["hour_col"].map(hour_map)
        long["kind"] = long[kind_c].astype(str).str.contains("하차").map({True: "alight", False: "ride"})
        long = long.pivot_table(index=id_cols + ["hour"], columns="kind",
                                values="count", aggfunc="sum").reset_index()
    else:  # 형식 B: 'OO시-OO시 승차인원' / '... 하차인원' 컬럼
        parts = []
        for kw, name in [("승차", "ride"), ("하차", "alight")]:
            hour_map = _hour_columns(raw, kw)
            p = raw.melt(id_vars=id_cols, value_vars=list(hour_map),
                         var_name="hour_col", value_name=name)
            p["hour"] = p["hour_col"].map(hour_map)
            parts.append(p.groupby(id_cols + ["hour"], as_index=False)[name].sum())
        long = parts[0].merge(parts[1], on=id_cols + ["hour"], how="outer")

    long = long.rename(columns={date_c: "date", line_c: "line", sta_c: "station"})
    long["date"] = parse_dates(long["date"])
    long["line"] = long["line"].map(normalize_line)
    long["station"] = long["station"].map(normalize_station)
    for c in ("ride", "alight"):
        long[c] = pd.to_numeric(long.get(c, 0), errors="coerce")
    return long[["date", "line", "station", "hour", "ride", "alight"]]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """결측·이상치 정리 + 중복 합치기."""
    df = df.dropna(subset=["date", "station", "hour"])
    df = df[df["hour"].isin(HOURS)]
    df[["ride", "alight"]] = df[["ride", "alight"]].fillna(0).clip(lower=0)
    # 같은 역·날짜·시간대가 여러 파일에 있으면 합산 (환승역 호선별 행은 line으로 구분됨)
    df = df.groupby(["date", "line", "station", "hour"], as_index=False)[["ride", "alight"]].sum()

    # 이상치: 역·시간대별로 중앙값의 10배를 넘는 값은 중앙값으로 대체
    for c in ("ride", "alight"):
        med = df.groupby(["station", "hour"])[c].transform("median")
        outlier = (med > 0) & (df[c] > med * 10)
        df.loc[outlier, c] = med[outlier]
    df[["ride", "alight"]] = df[["ride", "alight"]].round().astype(int)
    return df.sort_values(["station", "date", "hour"]).reset_index(drop=True)


def build_dataset(raw_dir: str | Path, stations: list[str] | None = None) -> pd.DataFrame:
    """raw_dir 안의 모든 CSV를 읽어서 병합·정제한다."""
    frames = []
    for path in sorted(Path(raw_dir).glob("*.csv")):
        try:
            frames.append(standardize(read_csv_any_encoding(path)))
            print(f"  OK  {path.name}")
        except ValueError as e:
            print(f"  SKIP {path.name}: {e}")
    if not frames:
        raise FileNotFoundError(f"{raw_dir}에서 읽을 수 있는 CSV가 없습니다.")
    df = pd.concat(frames, ignore_index=True)
    if stations:
        df = df[df["station"].isin(stations)]
    return clean(df)


def main():
    from src.config import COMPARE_STATIONS

    ap = argparse.ArgumentParser(description="지하철 승하차 CSV 통합·정제")
    ap.add_argument("raw_dir", help="원본 CSV 폴더 (예: data/raw)")
    ap.add_argument("--out", default="data/processed/subway_clean.csv")
    ap.add_argument("--all-stations", action="store_true", help="비교 대상 역만이 아니라 전체 역 저장")
    args = ap.parse_args()

    stations = None if args.all_stations else list(COMPARE_STATIONS)
    df = build_dataset(args.raw_dir, stations)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {args.out} ({len(df):,}행, 역 {df['station'].nunique()}개)")


if __name__ == "__main__":
    main()
