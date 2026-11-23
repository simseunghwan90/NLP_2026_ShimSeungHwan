# 재현 안내

최종 논문의 Initial·Lift-refined·Ground-refined (`trial03`)·R6V2 비교 결과를 생성한다. 입력은 7개 구간의 보존된 시계열과 지표이며, Unreal 실행 없이 논문 Figure 1·2, 부록 그림 7개와 비교표를 만든다.

## 환경 준비

Linux와 Python 3.10을 사용한다. 저장소 루트에서 가상환경을 만들고 패키지를 설치한다.

```bash
# 터미널 1 · 코드 저장소 루트
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt huggingface_hub
```

## 실행

데이터 다운로드 → 결과 생성 순서로 실행한다. 데이터가 이미 `../dataset`에 있으면 다운로드를 생략한다.

```bash
# 터미널 1 · 코드 저장소 루트
.venv/bin/hf download ShimSeungHwan01/2026NLP_simulation_research --repo-type dataset --local-dir ../dataset
.venv/bin/python scripts/reproduce_paper.py --dataset ../dataset --output results/paper
```

재실행할 때는 비어 있는 출력 경로를 지정한다. 11월 22일 공개본만 받은 경우 데이터셋의 `four_stage_comparison/`도 내려받아야 한다.

## 결과와 검증 범위

| 출력 | 내용 |
|---|---|
| `figures/figure1_development.*` | 네 단계의 원선회·가속–타력–제동 응답 |
| `figures/figure2_feedback.*` | Ground-refined와 R6V2의 MOVE s2 응답 |
| `figures/additional_*` | 7개 구간의 개별 응답 |
| `stage_summary_table.tex`, `all_window_tables.tex` | 대표 지표와 28개 개별 결과 |
| `appendix_summary_table.tex`, `appendix_lat3_table.tex` | 논문 부록 비교표 |
| `verification.json` | 입력 해시·공통 관측값·표 대조 결과 |

[scripts/reproduce_paper.py](../scripts/reproduce_paper.py)는 입력 58개의 해시를 [고정 목록](../paper_results/input_manifest.json)과 대조한 뒤, 논문에 사용한 그림·표 생성 코드를 출력 폴더에서 실행한다. 생성한 표 4개는 [논문 기준 파일](../paper_results/)과 바이트 단위로 비교한다. 그림은 PNG·PDF 각각 9개를 생성한다. 렌더러에 따른 차이가 있어 그림 파일의 바이트 일치는 실행 통과 조건에 포함하지 않는다.

원시 CAN 디코딩, 시뮬레이터 재생, 파라미터 추정을 다시 수행하는 절차는 아니다. 지표는 저장된 비교 CSV를 사용하며, 공통 관측값·시간축과 회전수 오차의 정의를 검사한다. 28개 실행에는 접지 검사 PASS 25개와 Initial의 FAIL 3개가 포함된다.

## 모델과 환경

최종 모델의 설정과 해시는 [모델 색인](../paper_results/model_index.json)에 있다. Ground-refined는 `trial03`이며, 앞선 비교의 `Previous`와 다르다. 이 비교는 보정과 모델 선택에 사용한 개발 데이터의 결과이다.

기록된 환경은 Linux, Python 3.10.12, NumPy 1.26.4, pandas 1.5.3, Matplotlib 3.5.1이다. 패키지 기록은 [environment_observed.json](../environment_observed.json)에 있다.

| 항목 | 기록 |
|---|---|
| LLM sampling seed | 세션 기록에 없음 |
| Stage 7·creep 후보 수치 최적화 | `20261122` |
| 표·그림 생성 | 난수 추출 없음 |

확인 필요: 새 컴퓨터에서의 의존성 설치와 Unreal 전체 재생.

## 앞선 3모델 비교

`expected/`와 `scripts/reproduce.py`는 Baseline·Previous·R6V2의 21개 결과를 생성하는 기존 비교용 자료이다. 최종 논문의 4모델 결과는 위 `scripts/reproduce_paper.py`를 사용한다. 과거 결과가 필요하면 다음 명령을 실행한다.

```bash
# 터미널 1 · 코드 저장소 루트
.venv/bin/python scripts/reproduce.py --dataset ../dataset --output results/legacy_three_models
```
