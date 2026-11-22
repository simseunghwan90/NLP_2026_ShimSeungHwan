# 11월 14일 리프트 자료와 물리 응답 보정

원본 검토는 [리프트 검토](../../experiments/evidence/2026-11-14_lift_review/README.md)에 둔다. 후속 물리 보정의 가설·실패·비교 결과는 [설계](../../experiments/evidence/2026-11-14_lift_calibration/DESIGN.md)와 [보고서](../../experiments/evidence/2026-11-14_lift_calibration/REPORT.md)에 둔다.

## 실행 경계

후속 실시간 운용은 [v7 차량으로 F1 주행](F1_LIVE.md)을 따른다. 아래는 고정 CAN 기록 재생의 경계와 명령이다.

실측 `0x210` 수신 명령을 Unreal 차량 입력 경계에서 재생한다. 실제 CAN 송신·실차 제어 서비스를 실행하지 않는다. ROS/BSW를 다시 통과시키지 않으므로 BSW 변환을 중복 적용하지 않는다. 이는 물리 모델의 개발 시험이며 전체 ROS 통합·실차 내부 명령 수락·전체 경로 평가를 대신하지 않는다.

`ResearchReplay` 옵션이 있을 때만 연구용 구현을 활성화한다. 같은 후보를 `lift=true`이면 앞바퀴 접지·후륜 부상 지그에서, `lift=false`이면 지면에서 실행한다. 실제 접촉과 물리 clock을 telemetry로 확인한다. 기본 실행은 기존 물리를 유지한다. 후보 파일은 기존 bridge의 `RESEARCH_RESPONSE_FILE`과 스키마가 다르므로 그 환경변수에 넣지 않는다.

브레이크 위치 8%는 사용자 확인 운용 조건이다. 후보의 잔류 저항 Nm는 타력 응답에서 얻은 유효 추정이며 8%에서 직접 환산하지 않는다. 회생·마찰·구동계 손실을 구분하지 않는다. 모터 관성도 실측 사양으로 확정하지 않는다.

## 재현

프로젝트 루트에서 실행한다. Python 환경은 루트 requirements에 추가로 numpy/pandas/scipy/matplotlib을 필요로 한다. 기존 `.venv`에서 실행한 버전은 각 `result.json`과 증거 환경 기록에 남긴다.

```bash
bash simulator/scripts/build.sh
.venv/bin/python -m unittest discover -s analysis/lift_20261114 -p 'test_*.py' -v

.venv/bin/python analysis/lift_20261114/replay.py run \
  experiments/evidence/2026-11-14_lift_calibration/inputs/LIFT-STEP-COAST_run9_r3.json \
  models/candidates/lift_2026-11-14_v7.json \
  reproduce_v7_65 --fast

.venv/bin/python analysis/lift_20261114/report.py
```

실행 ID `reproduce_v7_65`는 새 이름이어야 한다. 기존 결과가 있으면 중단해 덮어쓰지 않는다. 결과는 `experiments/evidence/2026-11-14_lift_calibration/runs/<ID>/`에 저장한다. RPC 포트는 41614이며 별도 offscreen 프로세스만 시작·종료한다. 기존 GUI를 조작하지 않는다. 한 번에 한 시험을 실행한다. `--fast`는 고정 물리 dt를 유지하며 벽시계 대기와 렌더 해상도만 줄인다. 생략하면 실시간에 맞춰 재생한다.

`replay.py prepare`는 원본 candump와 요청 CSV에서 입력 구간을 처음 추출하는 명령이다. 이미 보존한 `inputs/`가 있으면 중단한다. 입력 manifest의 해시와 고정 시간 구간을 사용한다. 실제 wheel 값은 비교 파일로만 읽으며 native physics 설정에는 주입하지 않는다.

## 파일

- `replay.py`: 정확한 DBC 단위 확인, 입력 추출, 소유한 Unreal 프로세스 실행·회수, 지그·clock·RPM 검사.
- `initialize_candidates.py`: 60/70% 개발 자료의 단순 근사로 초기 후보를 만든다. 근사 적합 결과와 실제 Unreal 결과를 구분한다. 이미 사용한 후보는 덮어쓰지 말고 새 버전으로 만든다.
- `batch.py`: 보존한 JSON 실행 목록을 순차 수행한다. 실행 디렉터리가 이미 있으면 중단한다.
- `report.py`: 실행 결과와 실제 CAN을 시간 이동 없이 대조하고 PNG/PDF·수치 표를 만든다.
- `test_replay.py`: CAN byte·단위·시간 역행·잘못된 입력 맵/관성 검사.

`result.json`의 `PASS`는 실행·접촉·유한 값·시간 검사 통과이다. 후보의 물리 적합 채택 여부는 보고서의 판정을 따른다. 실패한 service-brake 구현(v1/v2)과 sleep이 켜졌던 첫 지그 실행은 비교용 채택 결과에서 제외한다.
