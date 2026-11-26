# 🚇 숭실대입구역 혼잡 패턴 분석 앱

서울교통공사 공공데이터로 숭실대입구역(7호선)의 시간대·요일·학기별 승하차 패턴을 분석하고, **덜 붐비는 등하교 시간대**를 추천하는 Streamlit 앱입니다.

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 이 열립니다.
`data/processed/subway_clean.csv`가 없으면 **샘플(가짜) 데이터**로 실행됩니다. 실제 분석에 쓰면 안 됩니다.

## 실제 데이터 넣기 (팀원 1)

1. 원본 CSV를 `data/raw/`에 넣습니다. (용량이 커서 git에는 올리지 않습니다.)
   - 서울교통공사 **역별 일별 시간대별 승하차인원** (1~8호선, 2008~2021)
   - 서울 열린데이터광장 **지하철 호선별 역별 시간대별 승하차 인원** (월 단위)
2. 전처리 실행:
   ```bash
   python -m src.preprocess data/raw --out data/processed/subway_clean.csv
   ```
   인코딩(cp949/utf-8), 컬럼명, 역명(`숭실대입구(살피재)` → `숭실대입구`), 호선 표기를 자동으로 통일합니다.
   기본으로 `src/config.py`의 비교 대상 역만 저장합니다. 전체 역은 `--all-stations`.
3. 앱을 다시 실행하면 사이드바에 "실제 데이터 사용 중"이 표시됩니다.

## 폴더 구조와 담당

```
app.py                   # 앱 시작 파일 (페이지 목록)
pages/
  0_홈.py                # 오늘의 추천 (요일·학기 자동 판단 → 덜 붐비는 시간대)
  1_혼잡도_히트맵.py      # 요일 × 시간대 히트맵
  2_시간대_피크.py        # 시간대별 승하차 그래프 + 피크 탐지
  3_조건_비교.py          # 학기/방학 · 평일/주말 · 코로나 전후 + t-검정
  4_역_유형_분석.py       # K-means 역 유형 분류 + 엘보우
src/
  config.py              # 대상 역, 학사일정, 코로나 기준 연도  ← 먼저 확인!
  preprocess.py          # [팀원 1] 수집·병합·정제
  data_loader.py         # 정제 데이터 로드 + 요일/학기/코로나 변수 생성
  analysis.py            # [팀원 2] 피크 탐지, 조건 비교, 통계 검정
  clustering.py          # [팀원 3] 비율 벡터, 엘보우, K-means
  recommend.py           # [팀원 4] 상대 혼잡도, 추천 로직
  sample_data.py         # 개발용 가짜 데이터
  ui.py                  # 공통 사이드바
tests/test_core.py       # python -m pytest -q
```

## 팀에서 꼭 고쳐야 할 것

- [ ] `src/config.py`의 `SEMESTERS`: 지금은 **예시 날짜**입니다. 숭실대 학사일정으로 바꿔 주세요.
- [ ] `src/config.py`의 `COMPARE_STATIONS`: 비교 대상 역 목록과 예상 유형을 확정해 주세요.
- [ ] 실제 CSV를 받으면 `preprocess.py`가 컬럼을 잘 인식하는지 확인해 주세요. (못 읽은 파일은 `SKIP`으로 표시됩니다.)
- [ ] `clustering.name_cluster()`의 자동 유형 이름 규칙이 실제 데이터에서도 상식적인지 검토해 주세요.

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 GitHub에 push합니다.
2. https://share.streamlit.io 에서 저장소를 선택하고 Main file에 `app.py`를 지정합니다.
3. 실제 데이터로 배포하려면 정제된 `subway_clean.csv`(비교 대상 역만, 용량 작음)를 `.gitignore` 예외로 커밋하세요.

## 한계

- 승하차 인원은 **역 혼잡도**이며 열차 칸 내부 혼잡도와는 다를 수 있습니다.
- 시간대별 일 단위 데이터는 2021년까지가 중심입니다. 앱에 데이터 기간이 표시됩니다.
