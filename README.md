# A1 차량 시뮬레이터 보정 연구

Python 3.10 환경에서 실행한다. 데이터셋은 이 코드 폴더와 나란한 `../dataset`에 둔다.
```bash
# 터미널 1 · 이 저장소 루트
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/reproduce.py --dataset ../dataset --output results/hw2
```
설치 → 재생성 순서로 실행한다. [표·환경·범위](docs/REPRODUCIBILITY.md) · [구조](docs/STRUCTURE.md) · [시뮬레이터](simulator/README.md)
