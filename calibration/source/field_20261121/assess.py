"""Report declared development checks without promoting a speed-only candidate."""

import json

import pandas as pd
from intake import OUT


def main():
    data = pd.read_csv(OUT / "comparison.csv").set_index(["session", "label"])
    regression = ["MOVE_LAT2_1_s2", "MOVE_LAT2_2_s1", "LAT3_Apos_s1", "MOVE_LAT3_Apos_s2"]
    new_cases = ["LON5_Aneg_v50_s1", "LONK_Apos_v30_s1", "LONK_Aneg_v30_s1", "LON2_Apos_s1", "LON2_Aneg_s1"]
    decision = {"default_changed": False, "decision": "reject global replacement; preserve development candidates"}
    decision["candidate_status"] = {
        "geometry": "preserve diagnostic candidate; MOVE_LAT2_2 endpoint regression",
        "trial01": "reject global replacement; LAT3 speed RMSE regression exceeds 5 percent",
        "trial02": "reject; worse high-speed and existing MOVE speed RMSE",
        "trial03": "preserve longitudinal development candidate; endpoint and heading regressions",
        "driveonly03": "preserve ablation; LAT3 and LONK endpoint regressions",
    }
    blocks = [
        "속력 RMSE 단위는 m/s다. previous는 이번 작업 직전 채택 모델이며 논문 초기 baseline과 구분한다.",
        "| 구간 | previous | trial03 | 감소율 |\n| --- | ---: | ---: | ---: |",
    ]
    for case in new_cases + regression:
        old, new = data.loc[(case, "previous"), "rmse_mps"], data.loc[(case, "trial03"), "rmse_mps"]
        blocks.append(f"| {case} | {old:.3f} | {new:.3f} | {(1 - new / old) * 100:.1f}% |")
    old_mean = float(sum(data.loc[(c, "previous"), "rmse_mps"] for c in new_cases) / len(new_cases))
    new_mean = float(sum(data.loc[(c, "trial03"), "rmse_mps"] for c in new_cases) / len(new_cases))
    decision["new_five_cases_mean_rmse_mps"] = {"previous": old_mean, "trial03": new_mean}
    blocks.append(
        f"\n새 종방향 5개 고정 구간의 사례별 RMSE 단순 평균은 {old_mean:.3f}→{new_mean:.3f}m/s "
        f"({(1 - new_mean / old_mean) * 100:.1f}% 감소)다. 모두 개발 자료이며 독립 평가가 아니다."
    )
    blocks.append("\n| 기존 회귀 종점 오차(m) | previous | trial03 | driveonly03 |\n| --- | ---: | ---: | ---: |")
    for case in regression:
        values = [float(data.loc[(case, label), "endpoint_m"]) for label in ("previous", "trial03", "driveonly03")]
        blocks.append(f"| {case} | " + " | ".join(f"{v:.3f}" for v in values) + " |")
    decision["regression"] = {}
    for label in ("trial03", "driveonly03"):
        checks = {}
        for metric in ("rmse_mps", "endpoint_m", "heading_endpoint_deg"):
            changes = {
                case: float(data.loc[(case, label), metric] / data.loc[(case, "previous"), metric] - 1)
                for case in regression
            }
            checks[metric] = {
                "relative_changes": changes,
                "more_than_5pct_worse": [case for case, value in changes.items() if value > 0.05],
            }
        decision["regression"][label] = checks
    blocks.append("\n| 조향 확인 구간 | 이전 곡률 RMSE(1/m) | 기하 후보 | 감소율 |\n| --- | ---: | ---: | ---: |")
    geometry = pd.read_csv(OUT / "native_geometry_check.csv").set_index(["session", "label"])
    for case in ("LAT4_L120_s1", "LAT4_R120_s1", "LAT3_Apos_s2"):
        old = geometry.loc[(case, "previous"), "curvature_rmse_per_m"]
        new = geometry.loc[(case, "geometry"), "curvature_rmse_per_m"]
        blocks.append(f"| {case} | {old:.6f} | {new:.6f} | {(1 - new / old) * 100:.1f}% |")
    blocks.append(
        "\n곡률은 동일 시각의 1초 진단 표본에서 비교한다. native chassis 경로의 곡률과 실측 rear-axle yaw/vx를 사용하므로 "
        "전체 rear-axle 궤적 평가와 구분한다. [원자료](native_geometry_check.csv)를 보존한다."
    )
    (OUT / "decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    (OUT / "RESULTS.md").write_text("\n".join(blocks) + "\n")
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
