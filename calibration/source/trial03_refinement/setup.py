"""Freeze the user-selected trial03 and fixed development windows."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/evidence/2026-11-21_trial03_refinement"
STAGED = ROOT / "experiments/evidence/2026-11-21_staged_calibration"
FOLLOW = ROOT / "experiments/evidence/2026-11-21_field_followup"

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def save(path, obj):
    with Path(path).open("x") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")

def main():
    OUT.mkdir(exist_ok=False)
    (OUT / "decoded").symlink_to(FOLLOW / "decoded", target_is_directory=True)
    windows = json.loads((STAGED / "windows_v2.json").read_text())
    # Keep exactly the earlier declared long maneuvers; no outcome-based trimming.
    old = json.loads((FOLLOW / "windows.json").read_text())
    for name in ["LON5_Aneg_v50_s1", "LONK_Apos_v30_s1", "LONK_Aneg_v30_s1"]:
        w = dict(old[name])
        source = FOLLOW / "lon5_raw_210.csv" if name.startswith("LON5") else FOLLOW / "decoded" / ("20261120_" + name) / "commands.csv"
        w.update(command_source=str(source.relative_to(ROOT)), command_sha256=digest(source),
                 duration_s=w["end_s"]-w["start_s"], role="development_regression")
        windows[name] = w
    (OUT / "lon5_raw_210.csv").symlink_to(FOLLOW / "lon5_raw_210.csv")
    save(OUT / "windows.json", windows)
    files = [ROOT / "models/candidates" / n for n in [
        "steering_field_2026-11-21_trial03.json", "drive_field_2026-11-21_trial03.json",
        "steering_field_2026-11-20_v2.json", "drive_field_2026-11-20_v1.json"]]
    files += [ROOT / p for p in ["PLAN.md", "experiments/team_source.json", "experiments/bsw_main_source.json",
                               "analysis/staged_20261121/replay.py", "analysis/staged_20261121/launch.py",
                               "analysis/staged_20261121/validation.py", "analysis/main_launch/common.py"]]
    project = ROOT / "simulator/variants/staged_20261121"
    files += list((project / "Plugins/AirSim/Source/Vehicles/Car").glob("Research*.*"))
    files += list((project / "Plugins/AirSim/Source/Vehicles/Car").glob("Steering*.h"))
    hashes = {}
    for p in files:
        dst = OUT / "before" / p.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        hashes[str(p.relative_to(ROOT))] = digest(p)
    for rel in ["Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so", "Content/Maps/TestPad/TestPad.umap",
                "Content/Vehicles/A1/CarPawn.uasset", "Content/Vehicles/A1/ChassisPhysics.uasset",
                "Content/Vehicles/A1/FrontWheel.uasset", "Content/Vehicles/A1/RearWheel.uasset"]:
        p = project / rel
        hashes[str(p.relative_to(ROOT))] = digest(p)
    inputs = {}
    for n,w in windows.items():
        for p in [ROOT / w["command_source"], *[(OUT/"decoded"/("20261120_"+n)/(k+".csv")).resolve() for k in ["commands","feedback","state","odom"]]]:
            inputs[str(p.relative_to(ROOT))] = digest(p)
    save(OUT / "baseline_manifest.json", dict(parent="trial03", previous_reference="M0", sha256=hashes, input_sha256=inputs,
         paper_baseline=False, user_instruction="trial03에서 좌우 원선회 원인을 분리하고 단계적으로 개선한다. 방향 오차 약 2도 증가는 허용하되 큰 종점/회전수 악화를 제한한다.",
         inference="Exact served model and reasoning settings unavailable; no subagents", physical_experiments=0))
    save(OUT / "design.json", dict(
        experiment="TRIAL03-REFINE-20261121", parent="trial03", fixed_reference="previous M0",
        scope="Diagnose circles; adjust one evidenced response group at a time; preserve high-speed, coast and brake benefit",
        fit=["LAT4_L150_s1","LAT4_R150_s2","LAT4_L75_s1","LAT4_R75_s1"],
        checks=["LAT4_L120_s1","LAT4_R120_s1","LAT5_L_s1","LAT5_L_s2","LAT3_Apos_s2","LAT3_Aneg_s1"],
        final_regression=["LAT3_Apos_s1","LON2_Aneg_s1","LON2_Apos_s1","MOVE_LAT2_1_s2","MOVE_LAT2_2_s1","MOVE_LAT3_Apos_s2","LON5_Aneg_v50_s1","LONK_Apos_v30_s1","LONK_Aneg_v30_s1"],
        phases="Replay whole window once. Fit steady powered samples only: previous input acc>0 and brake=0 throughout +/-0.5s; valid fixed-RTK state, vx>0.5, steering feedback change<1.5deg/1s; exclude 0.1s neighborhood of state gaps>0.1s. Score powered, coast, braking, moving and whole-window errors separately.",
        acceptance=dict(primary="At least 10% improvement in equal-case circle cumulative-turn absolute error or moving-speed RMSE with the other not materially worse; fit and check groups reported separately",
            heading_added_deg=2.0, heading_scope="Straight checks; circle rotations use unwrapped turn count, with wrapped heading retained as diagnostic",
            circle_turn_error_added_max=.10, circle_turn_absolute_target=.10,
            speed_error_added="max(10% parent, 0.05m/s)",
            endpoint_or_position_added="max(10% parent error, 1m), and <10m added in every case",
            intermediate="Exploratory descendants may repair a flagged tradeoff; never silently promote a failed candidate",
            baseline_unacceptable="Passing no-regression does not establish absolute fidelity; residuals and absolute turn targets must be reported",
            source="Provisional development policy based on user tradeoffs, not measured sensor uncertainty; declared before new native results"),
        native=dict(project=str(project.relative_to(ROOT)),dt_s=.01,warmup_s=2,preparation_s=3,no_state_injection=True,no_posthoc_alignment=True),
        limits="All data previously exposed development data. No independent final evaluation, real CAN or user GUI. No change to BSW, commands or safety. Body changes require a separate hypothesis."
    ))
    print(OUT)

if __name__ == "__main__":
    main()
