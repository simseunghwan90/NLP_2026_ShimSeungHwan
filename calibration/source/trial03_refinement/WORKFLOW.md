# trial03 응답 보정 절차

원본 trial03과 이전 M0를 보존하고 원선회의 속도·반경·누적 회전량을 분리해 수정한다. [실험 설계](../../experiments/evidence/2026-11-21_trial03_refinement/design.json)와 단계별 가설을 먼저 기록한다. native `PASS`는 고정 입력 재생과 실행 검사의 통과이며 모델 채택과 구분한다.

## 데이터와 재생

`setup.py`는 입력과 초기 모델을 동결한 일회성 준비이다. 기존 실험에 다시 실행하지 않는다. 이동 19구간과 정지 3구간을 고정한다. 2초 안정화·3초 초기 조향 준비 후 기록된 입력을 연속 재생한다. 초기 이후 실측 위치·속도·방향을 주입하거나 시간과 궤적을 사후 정렬하지 않는다. 데이터 역할과 제외 규칙은 [DATA.md](../../experiments/evidence/2026-11-21_trial03_refinement/DATA.md)를 따른다.

`metrics.py`는 모든 후보에 같은 실측 품질 마스크를 사용하고 구동·타력·제동·이동 지표를 따로 계산한다. 원선회 회전량은 unwrap한 방향각으로 계산하여 한 바퀴 부족을 놓치지 않는다. 종점과 전체 위치 오차도 유지한다. 기준점은 GNSS 메시지의 선언된 후륜축과 native 뒷바퀴 중점이다. 실차 센서 외부변환은 독립 검증되지 않았다.

## 격리와 빌드

| 실행기 | 프로젝트 | RPC 포트 |
| --- | --- | --- |
| `run.py` / T0 | `staged_20261121` | 41659 |
| `run_refined.py` / R1 | `refine_20261121` | 41669 |
| `run_map.py` / R2 | `refine_map_20261121` | 41679 |
| `run_geometry.py` / R3~R5 | `refine_geometry_20261121` | 41689 |

모두 `simulator/variants/` 아래 별도 프로젝트와 잠금·출력 경로를 사용한다. 사용자 GUI·기본 선택·MPC·BSW는 유지한다. CPU/GPU는 공유하므로 벽시계 실행 시간은 달라질 수 있다. 물리 시간 간격 0.01초와 출력 완전성을 별도로 검사한다.

저장소 루트에서 `bash analysis/trial03_refinement/build.sh`는 R1 전용 프로젝트, `bash analysis/trial03_refinement/build_map.sh`는 R2 전용 프로젝트를 빌드한다. 실행 중인 프로젝트를 빌드하지 않는다. R3~R5 프로젝트는 R2의 검증된 바이너리와 에셋을 복사하고 모델 표만 바꾼 사본이다. 보존된 R5 바이너리와 모델 해시는 [선택 기록](../../experiments/evidence/2026-11-21_trial03_refinement/selected_model.json)에서 확인한다. 재빌드해 해시가 바뀌면 같은 실험으로 간주하지 않는다.

## 검사와 그림

저장소 루트에서 실행한다. 이름이 같은 테스트 모듈의 수집 충돌을 피하기 위해 기존 검사와 새 검사를 별도 Python 프로세스로 실행한다.

```bash
.venv/bin/python -m pytest analysis/trial03_refinement -q
.venv/bin/python -m pytest analysis/staged_20261121 analysis/field_20261120 -q
.venv/bin/python analysis/trial03_refinement/assess.py R5
.venv/bin/python analysis/trial03_refinement/plots.py R5
.venv/bin/python analysis/trial03_refinement/audit.py
```

`summarize.py`는 22구간이 모두 없으면 중단하며, 동일 가중치의 구간별 평균과 직진·정지 출력의 동등성을 내보낸다. `audit.py`는 원본과 입력 해시, 실행 당시 모델·바이너리·소스, 완료·실패·미완료 시도를 점검한다. 실행기 중단 후 미완료 폴더를 지우지 않으며 같은 고정 후보로 다시 실행한다.

`force_fit.py`의 가속도 근사는 후보 제안에만 사용한다. 손실표는 개발 자료의 유효 응답 보정이며 실제 토크·질량·마찰의 독립 식별이 아니다. 작은 조향각 표와 구동 손실표를 차례로 바꾸고 실패를 보존한다. 보정에 노출된 자료를 논문의 비공개 최종 평가로 다시 부르지 않는다.
