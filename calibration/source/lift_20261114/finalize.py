"""Audit and preserve the frozen development comparison, without changing models."""
import difflib
import json
from pathlib import Path
import shutil
import tarfile

import numpy as np
import pandas as pd

from replay import EVIDENCE, ROOT, hash_file


def finalize():
    freeze = json.loads((EVIDENCE / "development_freeze.json").read_text())
    for model, expected in freeze["models_sha256"].items():
        assert hash_file(ROOT / f"models/candidates/lift_2026-11-14_{model}.json") == expected
    assert hash_file(EVIDENCE / "batch_final.json") == freeze["batch_sha256"]
    rows = json.loads((EVIDENCE / "batch_final.json").read_text())
    rows += json.loads((EVIDENCE / "batch_coverage.json").read_text())
    names = [r["name"] for r in rows] + ["v7_ground_75"]
    planned = {r["name"]: r for r in rows}
    results = []
    for name in names:
        folder = EVIDENCE / "runs" / name
        r = json.loads((folder / "result.json").read_text())
        cfg = json.loads((folder / "replay.json").read_text())
        physics = json.loads((folder / "resolved.json").read_text())
        assert r["status"] == "PASS" and r["exit_code"] == 0, name
        model_key = "baseline60" if name.startswith("baseline60_") else "v7"
        assert r["model_sha256"] == freeze["models_sha256"][model_key], name
        if name in planned:
            assert r["source_case_sha256"] == hash_file(ROOT / planned[name]["case"]), name
        assert physics["low_speed_vehicle_substeps"] == 60, name
        f = pd.read_csv(folder / "telemetry.csv")
        assert np.isfinite(f.to_numpy()).all() and np.all(np.diff(f.t_s) > 0), name
        assert np.max(abs(f.dt_s-.01)) < 1e-5, name
        if not cfg["lift"]:
            assert max(r["contact_air_fraction"].values()) < .01, name
        else:
            assert min(r["contact_air_fraction"][w] for w in ["rl_air", "rr_air"]) > .999, name
            assert max(r["contact_air_fraction"][w] for w in ["fl_air", "fr_air"]) < .01, name
        for rel, expected in r["artifact_sha256"].items():
            assert hash_file(ROOT / rel) == expected, (name, rel)
        results.append({"name": name, "duration_s": cfg["duration_s"], "status": r["status"],
                        "frames": len(f), "dt_s": .01, "low_speed_substeps": physics["low_speed_vehicle_substeps"]})

    metrics = pd.read_csv(EVIDENCE / "lift_metrics.csv").set_index("run")
    comparison = []
    for suffix in ["step_r2", "step_r4", "step_r3", "step_r1", "ramp_r1", "ramp_r2", "ramp_r3", "hold"]:
        b, c = metrics.loc["baseline60_"+suffix], metrics.loc["v7_"+suffix]
        comparison.append(dict(case=c["case"], suffix=suffix, baseline_rmse=float(b.rmse), candidate_rmse=float(c.rmse),
                               reduction_pct=float((1-c.rmse/b.rmse)*100)))
    reduction = 100*(1-np.mean([r["candidate_rmse"] for r in comparison[:2]])/np.mean([r["baseline_rmse"] for r in comparison[:2]]))
    decision = {"candidate": "v7", "baseline": "baseline60", "partition": "development, not final evaluation",
                "fitting_cases_mean_rmse_reduction_pct": reduction,
                "lift_acceptance_60_70_65": bool(reduction >= 50 and comparison[2]["candidate_rmse"] < comparison[2]["baseline_rmse"]),
                "all_cases": comparison, "validated_runs": results, "physical_trials_added": 0,
                "limits": ["Candidate selection is for offline recorded-command replay", "Low-pedal remaining mismatch is reported, not refitted after freeze", "Ground diagnostic is acceleration-domain comparison, not full recorded trajectory"]}
    (EVIDENCE / "decision.json").write_text(json.dumps(decision, indent=2)+"\n")

    text = ["<!-- MEASURED_RESULTS_BEGIN -->", "## 개발 비교 수치", "",
            f"60/70% 적합 두 회차의 평균 RPM RMSE가 초기 대비 {reduction:.2f}% 감소했다. 65% 개발 확인 회차도 개선해 사전 정의한 무부하 판정을 통과했다. 이는 해당 RPM 응답의 개발 비교이다.", "",
            "| 입력/회차 | 초기 RPM RMSE | v7 RPM RMSE | 감소율 |", "| --- | ---: | ---: | ---: |"]
    labels = ["60% 적합", "70% 적합", "65% 개발 확인", "55% 개발 확인", "ramp 1", "ramp 2", "ramp 3", "속도 유지"]
    for label, r in zip(labels, comparison):
        text.append(f"| {label} | {r['baseline_rmse']:.2f} | {r['candidate_rmse']:.2f} | {r['reduction_pct']:.2f}% |")
    text += ["", "지면 합성 입력의 가속도 응답을 실제 개발 표본의 `a+g*grade`와 대조한다. 공통 지원 범위만 사용한다.", "",
             "| 자료 | 공통/전체 표본 | 초기 MAE (m/s²) | v7 MAE (m/s²) |", "| --- | ---: | ---: | ---: |"]
    ground = json.loads((EVIDENCE / "ground_metrics.json").read_text())
    for name, r in ground.items():
        values = r["mean_abs_error_mps2"]
        text.append(f"| {name} | {r['common_supported_samples']}/{r['total_samples']} | {values['baseline60']:.4f} | {values['v7']:.4f} |")
    text += ["", "10 RPM 최초 도달까지의 시간도 별도로 남긴다. 아래는 첫 가속 CAN 이후 시간이며, 차량 내부 지연의 단독 추정값이 아니다.", "",
             "| 입력 | 실측 (s) | v7 (s) |", "| --- | ---: | ---: |"]
    for suffix, label in [("step_r2", "60%"), ("step_r4", "70%"), ("step_r3", "65%")]:
        m = metrics.loc["v7_"+suffix]
        cfg = json.loads((EVIDENCE / "runs" / ("v7_"+suffix) / "replay.json").read_text())
        on = next(row[0] for row in cfg["commands"] if row[1] > 0)
        text.append(f"| {label} | {m.real_t10-on:.3f} | {m.sim_t10-on:.3f} |")
    text += ["", "최초 회전은 후보가 실측보다 이르다. 낮은 페달의 상승·유지에도 잔차가 남는다. 현재 입력 맵과 일정 유효 저항이 저입력 속도 의존성을 충분히 설명한다고 판단하지 않는다. 이 잔차를 제거하려고 고정 비교 후 모델을 다시 맞추지 않았다.", "",
             f"고정 비교와 속도 범위 보완을 합친 {len(results)}개 실행에서 접촉·clock·유한 값·종료·고정 해시를 검사했다. 실차 물리 실험 추가 비용은 0회이다.", "<!-- MEASURED_RESULTS_END -->", ""]
    report = EVIDENCE / "REPORT.md"
    existing = report.read_text()
    block = "\n".join(text)
    if "<!-- MEASURED_RESULTS_BEGIN -->" in existing:
        start = existing.index("<!-- MEASURED_RESULTS_BEGIN -->")
        end = existing.index("<!-- MEASURED_RESULTS_END -->") + len("<!-- MEASURED_RESULTS_END -->")
        existing = existing[:start]+block+existing[end:]
    else:
        existing = existing.replace("## 구현", block+"\n## 구현", 1)
    report.write_text(existing)

    for folder in (EVIDENCE / "runs").iterdir():
        for filename in ["runtime.log", "physics.json"]:
            source = ROOT / "simulator/local/lift_calibration" / folder.name / filename
            if source.is_file():
                shutil.copy2(source, folder / ("native_"+filename))

    car = "simulator/Plugins/AirSim/Source/Vehicles/Car/"
    patch = []
    with tarfile.open(EVIDENCE / "before_change.tar") as archive:
        for file in ["CarPawnSimApi.h", "CarPawnSimApi.cpp", "ResearchReplay.h", "ResearchReplay.cpp"]:
            rel = car+file
            try:
                original = archive.extractfile(rel).read().decode().splitlines(keepends=True)
            except KeyError:
                original = []
            current = (ROOT / rel).read_text().splitlines(keepends=True)
            patch.extend(difflib.unified_diff(original, current, fromfile="a/"+rel if original else "/dev/null", tofile="b/"+rel))
    (EVIDENCE / "physics_changes.patch").write_text("".join(patch))
    files = [ROOT / (car+name) for name in ["CarPawnSimApi.h", "CarPawnSimApi.cpp", "ResearchReplay.h", "ResearchReplay.cpp"]]
    files += sorted((ROOT / "analysis/lift_20261114").glob("*.py"))
    files += sorted((ROOT / "models/candidates").glob("lift_*.json"))
    files += [ROOT / "simulator/Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so", ROOT / "simulator/Binaries/Linux/libUE4Editor-Blocks.so"]
    with tarfile.open(EVIDENCE / "final_implementation.tar", "w") as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    manifest = {str(p.relative_to(ROOT)): hash_file(p) for p in files}
    manifest["final_implementation.tar"] = hash_file(EVIDENCE / "final_implementation.tar")
    (EVIDENCE / "final_implementation_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps({"validated_runs": len(results), "fit_rmse_reduction_pct": reduction, "lift_accepted": decision["lift_acceptance_60_70_65"]}, indent=2))


if __name__ == "__main__":
    finalize()
