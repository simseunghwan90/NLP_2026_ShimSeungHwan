# 최종 논문 결과

2026년 11월 23일 원고의 Initial·Lift-refined·Ground-refined (`trial03`)·R6V2 비교 자료이다. 7개 재생 구간의 결과 28개를 포함한다.

| 경로 | 내용 |
|---|---|
| [figures/](figures/) | 본문 Figure 1·2와 부록의 7개 구간 그림, PNG·PDF |
| [evidence/metrics_all_windows.csv](evidence/metrics_all_windows.csv) | 구간별 속도·위치 RMSE, 종점·회전수 오차와 실행 상태 |
| [evidence/table2_metrics.csv](evidence/table2_metrics.csv) | LAT3의 3구간 평균을 포함한 요약 수치 |
| [model_index.json](model_index.json), [models/](models/) | 공개 폴더 기준 설정 경로와 SHA-256 |
| [evidence/model_definitions.json](evidence/model_definitions.json) | 모델의 의미와 연구 당시 설정 경로 |
| [evidence/figure_sources.json](evidence/figure_sources.json) | 그림에 사용한 실행·CSV·바이너리의 해시 |
| [input_manifest.json](input_manifest.json) | 그림·표 생성에 필요한 데이터셋 파일 58개의 해시 |

시계열 CSV와 실행 로그는 데이터셋의 `four_stage_comparison/`에 있다. [재현 안내](../docs/REPRODUCIBILITY.md)에 따라 저장된 자료로 그림과 표를 생성한다.

Initial은 초기 차량 설정을 공통 맵과 계측 빌드에서 재생한 모델이다. 2026년 11월 10일 초기 실행 파일 자체의 결과를 뜻하지 않는다. 28개 중 Initial의 원선회·재배치 결과 3개는 접지 검사 실패로 표시한다. 모든 비교는 개발 자료를 사용한다.
