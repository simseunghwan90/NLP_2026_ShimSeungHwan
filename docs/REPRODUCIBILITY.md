# 재현 안내

[README의 명령](../README.md#표와-그림-재현)으로 논문에 사용한 표와 그림을 생성한다. 입력은 28개 개발 구간의 목록과 7개 구간에 대한 Baseline·Previous·R6V2의 재생 결과이다.

## 출력 파일

모든 파일은 `--output` 경로에 저장한다. 기본 경로는 `results/hw2`이며, 이미 파일이 있으면 새 경로를 지정한다.

| 논문 자료 | 출력 파일 |
|---|---|
| 개발 시험 목록 | `inventory.csv`, `inventory_table.tex` |
| 모델 비교표 | `metrics.csv`, `grouped_metrics.csv`, `results_table.tex` |
| 전체 21개 결과 | `complete_table.tex` |
| 본문 수치 | `numeric_macros.tex` |
| 대표 구간·MOVE 분석 그림 | `figures/representative_replays.*`, `figures/move_diagnostics.*` |
| 보정 비용 | `costs.json` |
| 재현 검사 결과 | `verification.json` |

## 재현하는 내용

`scripts/reproduce.py`는 데이터셋의 파일 해시를 검사하고 표·그림 생성 코드를 실행한다. 데이터셋의 경로 정보는 임시 디렉터리에서 복원하므로 원래 연구 폴더나 논문 PDF는 필요하지 않다.

이 절차는 저장된 평가 결과를 사용한다. 일부 RMSE는 각 실행의 `result.json`에서 읽으며, CAN 디코딩·시뮬레이션·모델 보정은 다시 실행하지 않는다. 재생 기록 21개에는 PASS 18개와 FAIL 3개가 포함된다.

생성한 CSV 3개는 [기준 결과](../expected/)와 절대 허용오차 `1e-9`로 비교한다. LaTeX 파일 4개는 내용이 정확히 같은지, `costs.json`은 값이 같은지 검사한다. PDF 생성 시각은 비교에서 제외한다.

## 환경과 seed

기존 재현 검사에 사용한 환경은 Linux, Python 3.10.12, NumPy 1.26.4, pandas 1.5.3, Matplotlib 3.5.1이다. 전체 패키지 버전은 [environment_observed.json](../environment_observed.json)에 기록했다.

| 항목 | 기록 |
|---|---|
| LLM sampling seed | 세션 기록에 없음 |
| Stage 7·creep 후보 수치 최적화 | `20261122` |
| 표·그림 생성 | 난수 추출 없음 |

공개 파일만 사용하는 로컬 재현 검사는 통과했다. 확인 필요: 새 컴퓨터에서의 의존성 설치와 실행.

## 비교 모델

Baseline은 실측 보정 전 차량 설정을 공통 맵과 계측 빌드에서 실행한 모델이다. Previous는 `STEER-FIELD-20261120-v2`와 `DRIVE-FIELD-20261120-v1`을 사용한다. R6V2는 이번 비교에서 선택한 보정 모델이다. 설정 파일과 해시는 [model_definitions.json](../expected/model_definitions.json)에 있다.

이 비교에는 보정과 모델 선택에 사용한 개발 자료를 사용한다. 독립 주행 데이터에 대한 최종 평가는 포함하지 않는다.
