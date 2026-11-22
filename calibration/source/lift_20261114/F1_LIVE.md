# v7 차량으로 F1 주행

두 터미널을 사용한다. 첫 명령은 v7 GUI·bridge·실제 BSW를 정지/disarm 상태로 준비한다. 두 번째 명령이 기존 팀 F1/planning을 같은 격리 세션에 연결해 **가상 차량을 자동 주행**시킨다.

터미널 1:

```bash
cd /home/simseunghwan/a1_git/a1_sim_research
bash scripts/f1_v7.sh simulator
```

`시뮬레이터 준비 완료` 메시지 뒤 터미널 2에서 실행한다.

```bash
cd /home/simseunghwan/a1_git/a1_sim_research
bash scripts/f1_v7.sh drive
```

- 기본은 `YonginSLAMFrame`, 동일 좌표의 팀 Yongin 1 m margin 경로, 목표 속도 상한 6 m/s이다. 속도 상한은 F1 참조 경로에 적용하며 실제 차량 속도의 강제 제한이 아니다.
- 터미널 2의 `F1 주행 시작` 뒤 주행한다. 터미널 2에서 `Ctrl+C`로 disarm·정지를 확인하고 시뮬레이터를 포함한 세션 전체를 종료한다. 재실행은 터미널 1부터 한다. GUI를 닫거나 터미널 1을 중단해도 세션을 종료한다.
- 입력/상태가 끊기거나 경로 거리가 기존 planner 한계 3 m를 넘으면 정지하고 실패를 기록한다. 자동으로 fault를 지우고 재출발하지 않는다.
- 기존 연구 시뮬레이터가 실행 중이면 시작을 거부한다. 사용자가 기존 연구 실행을 종료한 뒤 실행한다. 다른 프로젝트의 GUI를 조작하지 않는다.
- RPC 41615, ROS domain 79, localhost-only, 새 network namespace의 `vcan79`를 사용한다. host의 vcan 준비나 sudo는 필요하지 않다. 사용자 namespace가 허용된 이 PC에서 검증한다.
- 매 실행 자료는 `results/f1_v7/<시각_PID>/`에 별도로 저장한다. `operation.csv`, `operation.json`, `vehicle_telemetry.csv`, `vehicle_resolved.json`, `resolved.json`, `result.json`과 각 프로세스 로그를 남긴다.

두 번째 명령에서 실행 길이와 목표 속도를 선택할 수 있다.

```bash
bash scripts/f1_v7.sh drive --speed-cap 6 --duration 60
```

기존 한 명령 자동 실행도 유지한다. 두 터미널 방식과 동시에 실행하지 않는다.

```bash
bash scripts/f1_v7.sh
bash scripts/f1_v7.sh --offscreen --duration 20
```

## 적용 구조

팀 F1 → 조향/가감속 ROS 명령 → 팀 control_adapter → can_guard → 격리 vcan → 연구 bridge → Unreal v7 순서이다. F1과 BSW는 지정 팀 커밋 그대로 사용한다.

두 번째 터미널은 프로젝트의 로컬 UNIX socket으로 시작/정지를 요청한다. F1/ROS 프로세스는 첫 번째 세션의 동일 network namespace에서 실행한다. 별도 host CAN이나 직접 RPC 제어기를 시작하지 않는다. 두 터미널 검증은 [분리 실행 기록](../../experiments/evidence/2026-11-14_v7_f1_split/REPORT.md)을 따른다.

여기서 같은 BSW 로직은 고정한 팀 커밋 `6b9d8090a79e689da698a585d3774f0d58a24e93`의 원본 control_adapter/can_guard를 사용한다는 뜻이다. 현재 실차 PC에 배포된 커밋·설정까지 같다는 의미는 아니다. 실차 배포 버전은 별도 확인한다.

`ResearchVehicle` 옵션은 기존 v7의 토크곡선·관성·저항·적분 설정을 적용한다. bridge는 CAN 가속 %를 0~1로만 전달하고 native v7이 pedal map을 한 번 적용한다. 두 곳에서 pedal map/지연을 함께 적용하면 연결을 거부한다. 후보 ID와 해시를 native 설정에서 대조한다. 조향·서비스 브레이크·기어와 BSW의 정지 계약을 바꾸지 않는다. 기존 직접 RPC F1의 보정된 throttle을 이 입력에 혼용하지 않는다.

기록 재생은 기존 `ResearchReplay`로 유지한다. live 실행은 ROS 실시간 운용을 위해 기존 실시간 clock/frame 정책을 사용하므로 기록 재생의 고정 0.01 s와 구분한다. 실제 `dt_s`는 native telemetry에 남긴다. 후보 파라미터 재적합이나 하드웨어 지연 보정을 수행하지 않는다.

## 재빌드

현재 PC에서는 빌드했다. 새 설치나 소스 변경 후 다음을 실행한다.

```bash
bash simulator/scripts/build.sh
bash scripts/build.sh
bash scripts/build_f1.sh
```

`build_f1.sh`는 팀의 기존 `prepare_assets.py`로 누락된 원본 에셋만 복원하고 원본 SHA-256을 검사한다. 팀 F1과 planning을 연구 ROS overlay에 설치한다. 기존 F1 체크포인트·알고리즘·BSW 소스는 수정하지 않는다.

검증 결과와 실패는 [운용 기록](../../experiments/evidence/2026-11-14_v7_f1_live/REPORT.md)에 둔다. 이 실행은 보정 모델의 폐루프 운용 확인이며 완주나 실차 일치를 보증하지 않는다.
