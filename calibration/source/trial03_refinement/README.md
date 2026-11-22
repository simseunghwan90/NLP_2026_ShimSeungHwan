```bash
# 터미널 1 · /home/simseunghwan/a1_git/a1_sim_research
.venv/bin/python analysis/trial03_refinement/run_geometry.py R5 LAT5_L_s1 LAT5_L_s2 MOVE_LAT2_1_s2 MOVE_LAT2_2_s1 MOVE_LAT3_Apos_s2 LON5_Aneg_v50_s1 LONK_Apos_v30_s1 LONK_Aneg_v30_s1 LON2_Aneg_s1 LON2_Apos_s1 LAT3_Apos_s1 LAT3_Apos_s2 LAT3_Aneg_s1 LAT4_L150_s1 LAT4_R150_s2 LAT4_L75_s1 LAT4_R75_s1 LAT4_L120_s1 LAT4_R120_s1 LAT1_s1 SELFCHECK_s1 SELFCHECK_s2 --steering models/candidates/steering_trial03_refine_2026-11-21_R5.json
.venv/bin/python analysis/trial03_refinement/metrics.py
.venv/bin/python analysis/trial03_refinement/summarize.py R5
```
각 명령 완료 후 다음 명령을 실행한다. 동일 해시의 기존 PASS는 보존한다. [빌드·구조·검사](WORKFLOW.md) · [결과·한계](../../experiments/evidence/2026-11-21_trial03_refinement/REPORT.md)
