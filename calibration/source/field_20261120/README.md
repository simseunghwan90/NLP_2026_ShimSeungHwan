# 2026-11-20 실측 기반 조향·구동 후보

실제 송신 CAN 입력으로 조향 응답을 식별하고 저속 접지 재생으로 페달 맵을 보정한다. [실험 기록](../../experiments/evidence/2026-11-20_field_update/REPORT.md)과 [사전 기준](../../experiments/evidence/2026-11-20_field_update/DESIGN.md)을 따른다.

## 적용과 되돌리기

현재 실행기 기본값은 `STEER-FIELD-20261120-v2`와 `DRIVE-FIELD-20261120-v1`이다. 조향 v1의 응답 파라미터는 그대로 사용하고 구동 후보를 연결한다. 두 터미널 모두 연구 프로젝트 루트에서 실행한다.

```bash
# 터미널 1: GUI·bridge·지정 BSW를 정지/disarm 상태로 준비한다.
bash scripts/f1_field.sh simulator

# 준비 완료 메시지 뒤 터미널 2: 지정 팀 F1을 시작한다.
bash scripts/f1_field.sh drive
```

두 번째 명령은 가상 차량을 주행시킨다. 기본 목표 속도는 원본 경로 값이며 `drive --speed-cap 6 --duration 60`처럼 선택할 수 있다. 목표 속도 상한은 실제 속도를 강제 제한하지 않는다. 터미널 2의 `Ctrl+C`는 정지와 세션 전체 종료를 요청한다. 세션의 안내에 이전 스크립트 이름이 표시되어도 위 두 명령을 사용한다.

기존 격리 세션의 실행·정지 절차를 재사용한다. F1→control_adapter→can_guard→격리 vcan→연구 bridge→Unreal 경로다. F1·planning은 `experiments/team_source.json`의 `6b9d8090a79e689da698a585d3774f0d58a24e93`을 유지한다. 이후 사용자의 main BSW 갱신 요청에 따라 현재 실행의 BSW만 `experiments/bsw_main_source.json`의 로컬 main `28482309c9f9d5693b8e7ad973b1d961be779519`로 분리했다. 원격 서버 최신 main 여부는 확인 필요다. 사용자가 알려준 `bsw/feat/pad-field-test-kit-and-new-dbc`는 실측 수집 버전으로 보존한다.

main의 control_adapter·can_guard·can_bridge와 대응 메시지·차량 설정을 원본대로 사용한다. F1과 시뮬레이터 물리 파라미터는 이 갱신으로 변경하지 않는다. BSW의 조향·구동 변환표는 main 버전이므로 같은 F1 출력에서 생성되는 CAN 값은 이전 BSW와 달라질 수 있다. [변경·검증 기록](../../experiments/evidence/2026-11-20_bsw_main_update/REPORT.md)을 따른다. 기존 실행을 종료한 뒤 위 두 명령으로 다시 시작해야 새 버전이 적용된다.

새 환경에서는 `bash scripts/build_bsw_main.sh`를 먼저 실행한다. BSW만 이전 버전으로 되돌려 비교할 때는 터미널 1을 아래처럼 실행한다. 터미널 2 명령과 차량 모델은 동일하다.

```bash
RESEARCH_BSW_SOURCE_FILE="$PWD/experiments/team_source.json" \
  bash scripts/f1_field.sh simulator
```

2026-11-20 재확인 시 팀 작업 폴더는 main이며 이전 `bringup/f1_sim.sh` 파일이 없다. 그 명령의 과거 모델 선택 검증은 보존하지만 현재 실행 명령으로 안내하지 않는다. 기존 `scripts/f1_v7_neighbor_steering.sh`는 이전 조향/v7을 유지한다. 두 세션은 같은 프로젝트 잠금·제어 socket을 사용하므로 동시에 실행하지 않는다. 새 후보의 F1 폐루프 완주는 확인 필요다. 실행 기록은 `results/f1_v7_neighbor_steering/<시각_PID>/`에 모델 ID·해시와 함께 저장한다.

연구 루트에서 현재 선택만 확인한다. dry-run은 프로세스를 실행하거나 CAN을 송신하지 않는다.

```bash
python3 analysis/neighbor_steering/launch.py --map TestPad \
  --output simulator/local/neighbor_steering/selection_check --dry-run
```

이전 차량은 모델 파일을 명시하여 실행한다. 새 조향과 이전 v7 구동의 조합은 `steering_field_2026-11-20_v1.json`이다.

```bash
python3 analysis/neighbor_steering/launch.py --map TestPad \
  --output simulator/local/neighbor_steering/previous_vehicle \
  --steering-model models/candidates/steering_neighbor_2026-11-17_v1.json
```

기본 선택을 되돌릴 때는 `analysis/neighbor_steering/launch.py`의 `MODEL`을 이전 JSON 경로로 바꾼다. 변경 전 실행기 사본은 증거 폴더 `before_update/`에 보존한다.

## 재현

원본 압축파일 SHA-256과 추출 경로의 모든 파일을 대조한다. `RAW`는 경로 순회·링크가 없는 것으로 확인해 추출한 폴더를 뜻한다. 기존 결과는 덮어쓰지 않는다.

```bash
source /opt/ros/humble/setup.bash
python3 analysis/field_20261120/intake.py --raw-root /path/to/RAW \
  --output /tmp/field_intake_repeat
python3 analysis/field_20261120/fit_steering.py \
  --output /tmp/field_fit_repeat --model-output /tmp/field_steering_repeat.json
python3 -m pytest -q analysis/field_20261120/test_field.py
```

피팅은 보존된 `decoded/`를 입력으로 사용하고 실제 native `SteeringDynamics.h`를 C++ 라이브러리로 빌드한다. NumPy·Pandas·SciPy·pytest와 g++가 필요하다. 반복 시 새 출력 경로를 사용한다.

별도 검증 사본은 `simulator/variants/field_20261120`이다. 새 환경에서는 아래 rsync로 생성한다. 사본이 이미 있으면 다시 복사하지 않는다. 해시는 `project_snapshot.json`과 대조한다.

```bash
rsync -a --exclude=local --exclude=Saved --exclude=Intermediate --exclude=DerivedDataCache \
  simulator/variants/neighbor_steering/ simulator/variants/field_20261120/
python3 analysis/field_20261120/replay.py lat1 --previous
python3 analysis/field_20261120/replay.py lat1
python3 analysis/field_20261120/replay.py move \
  --model models/candidates/steering_field_2026-11-20_v2.json
python3 analysis/field_20261120/replay.py lat3 \
  --model models/candidates/steering_field_2026-11-20_v2.json
```

재생은 TestPad·고정 0.01s·자체 offscreen 프로세스에서 수행하며 CAN 장치를 열지 않는다. GPU/localhost RPC 실행 권한이 필요하다. 실행별 입력·해시·resolved 설정·telemetry·결과를 `native_replays/`에 저장한다. 시작 각도는 처음 feedback으로 한 번 설정하고 이후 실측 상태를 주입하거나 시간축을 이동하지 않는다.

## 한계

조향은 정지 ±20° handwheel 자료다. 지연은 CAN→feedback의 유효 모델 값이며 순수 하드웨어 지연이 아니다. 조향비 12.6과 140°/s 제한은 기존 가정이다. 정적 유격·반복 진동은 완전히 재현하지 않는다.

구동은 약 0–2.8m/s 접지 개발 구간의 페달 맵이다. 토크·관성·잔류 저항은 유지하지만 페달 맵이 달라 기존 리프트 일치가 자동으로 유지되지 않는다. 특히 m8 저입력 구간의 과속 예측이 남는다. 제동 응답·고속·노면 경사·전체 궤적·폐루프 완주·독립 최종 평가는 확인 필요다.
