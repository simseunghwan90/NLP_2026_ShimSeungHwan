# 2026-11-21 실차 자료 후속 보정

`FIELD-CAL-20261121-01`은 이전 `STEER-FIELD-20261120-v2` / `DRIVE-FIELD-20261120-v1`에서 이어지는 개발 회차다. course3를 제외한 새 LAT·LON 기록으로 선택형 조향 기하·타력·제동 후보를 구현하고 실제 CAN 명령을 Unreal에 재생한다. 채택 여부와 수치는 [결과 보고서](../../experiments/evidence/2026-11-21_field_followup/REPORT.md)를 따른다. 기존 F1/MPC 기본 모델을 자동 교체하지 않는다.

2026-11-21 후속 작업은 [단계별 누적 보정 계획](../../PLAN.md#7-latlon-단계별-누적-보정)을 따른다. 데이터 구간을 먼저 판정하고 정지 조향→기하→저속 구동→제동→고속 구동·타력→주행 중 조향→복합 경로 순서로 진행한다. 아래 명령과 고정 구간은 기존 회차의 재현용이며 새 계획의 전체 경로 평가를 대신하지 않는다.

## 자료와 코드

- 원본은 `data/bsw_test_bags_20261120.zip`, `data/20261120_LON5_Aneg_v50_s1.zip`이다. `intake.py`가 안전 경로·SHA-256·중복·MCAP 스키마를 기록하고 ROS 환경에서 별도 사본을 디코딩한다. 이미 존재하는 raw 폴더에는 다시 추출하지 않는다.
- `analyze.py`는 시간·스키마·CAN 경계와 유효 조향 기하를 진단한다. `geometry_diagnostic.json`의 candidate는 초기 **선형 진단**이며 실제 native 후보의 비선형 표와 구분한다.
- `candidates.py`는 LAT4 L/R150·L/R75 관측으로 기하 후보를 만든다. `models/candidates/*2026-11-21*`의 시행된 파일은 해시와 함께 보존한다. trial 설명의 정정은 [DESIGN.md](../../experiments/evidence/2026-11-21_field_followup/DESIGN.md)에 둔다.
- native 작업 사본은 `simulator/variants/field_20261121`이다. `SteeringGeometry.h`, `ResearchSteering.*`, `ResearchReplay.*`와 복사본 TestPad 크기만 관련 물리 변경 범위다. 이전 프로젝트와 원본은 보존한다.
- 고정 구간은 evidence의 `windows.json`, `windows_regression.json`이다. 시작 명령이 없는 앞부분을 제외한 변경은 `window_coverage_changes.json`에 남긴다. 비정지 시작 LON1과 시각 역전 S03은 재생에서 제외한다.

## 고정 입력 재현

연구 루트에서 실행한다. 별도 offscreen 프로세스와 프로젝트 잠금을 사용하며 CAN 장치를 열지 않는다. native 출력의 `PASS`는 접지·유한값·10ms timestep·완전 종료를 뜻한다. 모델의 채택 판정은 보고서를 따른다.

```bash
bash analysis/field_20261121/build.sh
python3 analysis/field_20261121/batch.py \
  --cases LON5_Aneg_v50_s1 LAT3_Apos_s1 MOVE_LAT2_1_s2 MOVE_LAT2_2_s1 MOVE_LAT3_Apos_s2 \
  --models previous geometry trial03 driveonly03
.venv/bin/python analysis/field_20261121/summarize.py
.venv/bin/python analysis/field_20261121/geometry_check.py
```

`previous`는 이전 전체 모델, `geometry`는 새 조향 기하만 적용한 모델이다. `trial01/02/03`은 새 기하와 각 구동 후보의 조합, `driveonly03`은 이전 조향과 trial03 구동의 조합이다. 각 실행은 새로운 timestamp 폴더에 명령·설정·해시·전체 telemetry·실패를 남긴다. `summarize.py`는 모든 시도를 `all_native_runs.csv`, 사례/모델별 최근 정상 재생을 `comparison.csv`에 기록한다.

실측 초기 위치·heading 한 번만 사용한다. 명령 시각을 옮기거나 이후 실측 상태를 주입하지 않는다. 궤적은 rear axle 기준 계약을 사용하지만 당시 센서 외부변환 전체를 독립 검증하지 못했으므로 개발 진단으로 해석한다. 실험 결과를 보고 구간을 바꾸거나 새 실행이 기존 결과를 덮어쓰지 않는다.

## 실제 BSW 연결 확인

다음 명령은 모델 파일과 native 바이너리 해시를 명시하고 기존 팀 MPC·arbiter·BSW·can_guard를 격리 network namespace의 `vcan79`에 연결한다. 연구용 BSW를 구현하지 않는다. 원본 `scripts/mpc_field.sh`의 기본 모델 선택은 유지한다.

```bash
bash analysis/field_20261121/mpc_probe.sh \
  --steering experiments/evidence/2026-11-21_field_followup/integration_model.json \
  --offscreen --duration 8
```

이 짧은 연결 시험은 실차 일치·경로 완주·독립 평가를 증명하지 않는다. 결과 원본은 `results/mpc_field/<실행 ID>`에 생성하며 보존할 실행은 해당 evidence로 복사한다. 기존 GUI와 실제 CAN은 조작하지 않는다.

## 회귀 검사

```bash
source scripts/env.sh
source ros_ws/install_bsw_main/local_setup.bash
python3 -m pytest -q \
  analysis/field_20261121/test_geometry.py \
  analysis/lift_20261114/test_replay.py \
  analysis/field_20261120/test_field.py \
  analysis/field_20261120/test_bsw_main.py \
  ros_ws/src/simulator_bridge/test analysis/mpc_field/test_interface.py
```

현재 기본 선택은 이전 모델이며 별도 되돌리기 작업이 필요하지 않다. 이번 선택형 기능을 사용하는 실행은 이 문서의 명시적 후보 명령으로 한정한다. 원본·후보·실패 기록을 삭제하지 않는다.
