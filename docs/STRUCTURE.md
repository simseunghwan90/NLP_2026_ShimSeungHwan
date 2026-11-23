# 코드 구성

| 경로 | 내용 |
|---|---|
| [scripts/reproduce.py](../scripts/reproduce.py) | 표·그림 생성 및 기준 결과 대조 |
| [analysis/](../analysis/) | 지표 집계, 표 작성, 시각화 코드 |
| [models/](../models/) | 차량 응답 파라미터와 보정 후보 |
| [expected/](../expected/) | 논문에 사용한 표·그림, 모델 정의, 비교 구간 |
| [simulator/projects/](../simulator/projects/) | Unreal 프로젝트 소스와 설정 |
| [calibration/](../calibration/) | 보정 단계별 코드와 당시 작업 사본 |

CAN·rosbag·DBC·실행 로그는 [데이터셋](https://huggingface.co/datasets/ShimSeungHwan01/2026NLP_simulation_research)에, Unreal 에셋과 Linux 모듈은 [Release](https://github.com/simseunghwan90/NLP_2026_ShimSeungHwan/releases)에 둔다.

## 보정 기록 읽기

`calibration/source/`는 리프트 시험, 실차 응답 보정, trial03 후속 작업의 코드이다. `calibration/source_snapshot/`은 단계별 보정 작업 당시의 사본이다. 가설과 실험 결과는 데이터셋의 `calibration/`에, 에이전트 대화와 사람의 개입은 `agent_records/`에 있다.

이 기록에는 당시 경로와 실행 명령이 남아 있다. 새 환경에서 표와 그림을 생성할 때는 루트 README의 명령을 사용한다. 보정 스크립트 전체를 다시 실행하는 절차는 제공하지 않는다.

## 라이선스

확인 필요: 이 배포본의 공개 라이선스와 제3자 코드·에셋의 재배포 조건. 포함된 외부 자료는 각 원본의 라이선스를 따른다.
