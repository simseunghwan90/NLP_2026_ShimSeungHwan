# 코드 구성

| 경로 | 내용 |
|---|---|
| [paper_results/](../paper_results/README.md) | 최종 논문의 4모델 그림·지표·설정·입력 해시 |
| [scripts/reproduce_paper.py](../scripts/reproduce_paper.py) | 최종 논문 그림·표 생성과 기준 표 대조 |
| [analysis/four_stage_20261123/](../analysis/four_stage_20261123/) | 원고에 사용한 시각화·표 생성 코드 |
| [models/](../models/) | 보정 과정에서 사용한 차량 응답 파라미터와 후보 |
| [simulator/projects/](../simulator/projects/) | 보관된 Unreal 프로젝트 소스와 설정 |
| [calibration/](../calibration/) | 보정 단계별 코드와 당시 작업 사본 |
| [expected/](../expected/), [scripts/reproduce.py](../scripts/reproduce.py) | 앞선 Baseline·Previous·R6V2의 3모델 비교 |

CAN·rosbag·DBC·실행 로그와 최종 4모델 시계열은 [데이터셋](https://huggingface.co/datasets/ShimSeungHwan01/2026NLP_simulation_research)에, Unreal 에셋과 Linux 모듈은 [Release](https://github.com/simseunghwan90/NLP_2026_ShimSeungHwan/releases/tag/v0.1.0)에 둔다.

## 보정 기록 읽기

`calibration/source/`는 리프트 시험, 실차 응답 보정, trial03 후속 작업의 코드이다. `calibration/source_snapshot/`은 단계별 보정 작업 당시의 사본이다. 가설과 실험 결과는 데이터셋의 `calibration/`에, 에이전트 대화와 사람의 개입은 `agent_records/`에 있다.

이 기록에는 당시 경로와 실행 명령이 남아 있다. 공개 파일로 최종 논문 그림과 표를 생성하는 절차는 [재현 안내](REPRODUCIBILITY.md)를 따른다.

## 라이선스

확인 필요: 이 배포본의 공개 라이선스와 제3자 코드·에셋의 재배포 조건. 포함된 외부 자료는 각 원본의 라이선스를 따른다.
