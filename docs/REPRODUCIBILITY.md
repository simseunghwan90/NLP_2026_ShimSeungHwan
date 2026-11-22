# 재현 범위

HW2의 Baseline·Previous·R6V2 개발 비교 7구간과 21개 보존 결과를 사용한다. 28개 개발 구간은 시험군 표와 보정 과정의 자료이다. 독립 최종 평가 자료로 분류하지 않는다.

README의 한 명령이 다음 산출물을 생성한다. `--output`은 비어 있거나 없는 경로로 지정한다.

| 원고 대상 | 생성 파일 | 입력 |
|---|---|---|
| 개발 시험군 표 | `inventory.csv`, `inventory_table.tex` | 고정된 28개 window |
| 주요 모델 비교표 | `metrics.csv`, `grouped_metrics.csv`, `results_table.tex` | 7구간 × 3모델 결과·비교 시계열 |
| 전체 구간별 부록 표 | `complete_table.tex` | 같은 21개 결과 |
| 대표·MOVE 그림 | `figures/representative_replays.*`, `figures/move_diagnostics.*` | 보존된 실측/시뮬레이션 시계열 |
| 보정 비용 수치 | `costs.json` | 보존된 실행 색인 |

`scripts/reproduce.py`는 데이터 manifest의 상대 경로를 임시 작업 공간에 복원하고 원래 `build_data.py`, `plot.py`, `publish.py` 함수를 호출한다. 원본 논문 PDF와 로컬 연구 폴더가 필요하지 않다. 원래의 표 생성 소스는 바이트 단위로 보존한다.

수치 CSV를 `expected/`와 절대 허용오차 1e-9로 비교하고 네 LaTeX 표·매크로 파일을 바이트 단위로 대조한다. 원래 결과의 PASS 18개와 FAIL 3개를 유지한다. 그림 PDF의 생성 시각 차이는 수치 일치 판정에 사용하지 않는다.

이 명령은 보존된 평가 결과에서 표·그림을 재구성한다. 일부 RMSE는 당시 `result.json`의 평가값을 읽는다. 원시 CAN 디코딩부터 시뮬레이션·평가까지 새로 실행한 검증으로 해석하지 않는다. 물리 모델 재실행과 에이전트 보정 재실행은 별도 범위이다.

## 환경과 seed

검증 환경은 Linux, Python 3.10.12, NumPy 1.26.4, pandas 1.5.3, Matplotlib 3.5.1이다. 전이 의존성까지의 관측 버전은 `environment_observed.json`에 기록한다. 설치 명령은 새 PC에서 별도 확인해야 한다.

LLM sampling seed는 확인한 세션 기록에서 미기록이다. 전체 연구에 seed가 없었다고 쓰지 않는다. Stage 7과 creep 후보의 수치 최적화에는 `20261122`가 명시되어 있으며 해당 소스·설계 기록을 함께 보존한다. 표 재구성 경로에서는 난수 추출을 추가하지 않는다.

현재 검증 범위는 공개 사본을 이용한 로컬 격리 디렉터리 실행이다. HW2 지침의 새 컴퓨터 설치·실행 확인은 별도 남은 항목이다. 관측된 환경의 패키지를 공유한 실행을 새 컴퓨터 검증으로 표시하지 않는다.
