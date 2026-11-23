# A1 Simulator

[Download](https://github.com/simseunghwan90/NLP_2026_ShimSeungHwan/releases) · [Dataset](https://huggingface.co/datasets/ShimSeungHwan01/2026NLP_simulation_research)

논문의 차량 응답 비교에 사용한 Unreal Engine 4.27 프로젝트이다. 이 폴더에는 소스와 설정을 제공하며, Content·플러그인·Linux 모듈을 포함한 프로젝트는 Release에서 받는다.

| 프로젝트 | 비교 모델 |
|---|---|
| [lat3_three_models_20261122](projects/lat3_three_models_20261122/) | Baseline, Previous |
| [r5_creep_viscous_20261122](projects/r5_creep_viscous_20261122/) | R6V2 |

Release에는 2026-11-10 초기 모델 아카이브도 포함한다. 비교 모델별 설정과 해시는 [model_definitions.json](../expected/model_definitions.json)에 있다.

## 사용 환경

프로젝트를 열려면 별도로 설치한 UE4.27이 필요하다. 엔진과 빌드 캐시는 배포본에 포함하지 않는다. 독립 실행 게임 패키지는 아직 제공하지 않는다.

표·그림 재현에는 Unreal이 필요하지 않다. [루트 README](../README.md)의 명령을 사용한다.

확인 필요: 새 머신에서의 프로젝트 빌드·실행과 전체 입력 재생 절차.
