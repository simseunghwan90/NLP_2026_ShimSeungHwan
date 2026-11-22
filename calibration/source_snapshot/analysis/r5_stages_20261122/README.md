# R5 후속 후보 재생

터미널 1에서 아래 순서로 실행한다. 완료한 동일 후보·입력·바이너리 재생은 보존본을 사용한다.
```bash
cd /home/simseunghwan/a1_git/a1_sim_research
.venv/bin/python analysis/r5_stages_20261122/run.py R6V2 ALL --steering models/candidates/steering_r5_stages_2026-11-22_R6V2.json
.venv/bin/python analysis/r5_stages_20261122/metrics.py
.venv/bin/python analysis/r5_stages_20261122/audit.py R6V2
```
[입력·절차·격리](WORKFLOW.md) · [최종 결과](../../experiments/evidence/2026-11-22_r5_stages/REPORT.md)
