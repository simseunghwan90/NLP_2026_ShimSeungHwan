"""Audit immutable inputs and full final native coverage without rerunning physics."""
import collections
import json
from pathlib import Path

from setup import ROOT, OUT, digest


def main():
    baseline = json.loads((OUT / "baseline_manifest.json").read_text())
    windows = json.loads((OUT / "windows.json").read_text())
    failures = []
    checked = {}

    def check(path, expected, context):
        path = Path(path)
        actual = digest(path) if path.is_file() else None
        checked[str(path.relative_to(ROOT))] = actual
        if actual != expected:
            failures.append(dict(context=context, path=str(path), expected=expected, actual=actual))

    for group in ["sha256", "input_sha256"]:
        for rel, expected in baseline[group].items():
            check(ROOT / rel, expected, group)

    steering_path = ROOT / "models/candidates/steering_trial03_refine_2026-11-21_R5.json"
    steering = json.loads(steering_path.read_text())
    drive_path = ROOT / steering["base_longitudinal_model"]
    project = ROOT / steering["native_project"]
    binary = project / "Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so"
    check(drive_path, steering["base_longitudinal_sha256"], "R5 drive pin")
    check(binary, steering["native_binary_sha256"], "R5 native pin")
    frozen_hashes = dict(steering_sha256=digest(steering_path), drive_sha256=digest(drive_path),
                         binary_sha256=digest(binary), windows_sha256=digest(OUT / "windows.json"))
    original_project = "simulator/variants/staged_20261121/"
    for rel, expected in baseline["sha256"].items():
        if rel.startswith(original_project + "Content/"):
            check(project / rel.removeprefix(original_project), expected, "R5 inherited assets")

    inventory = []
    final = []
    for folder in sorted((OUT / "native_replays").iterdir()):
        if not folder.is_dir():
            continue
        path = folder / "result.json"
        row = dict(folder=str(folder.relative_to(ROOT)))
        if not path.exists():
            row.update(status="INCOMPLETE", note="No result.json; retained and excluded from comparisons")
            inventory.append(row)
            continue
        result = json.loads(path.read_text())
        row.update({k: result.get(k) for k in ["label", "session", "status", "wall_started", "wall_finished",
                                               "owned_process_stopped", "error"]})
        if result.get("owned_process_stopped") is not True:
            failures.append(dict(context="owned process shutdown", folder=str(folder)))
        if result["label"] == "R5" and result["status"] == "PASS":
            final.append(result)
            for key, expected in frozen_hashes.items():
                if result.get(key) != expected:
                    failures.append(dict(context="R5 frozen pin", folder=str(folder), key=key))
            check(folder / "runner_source.py", result["source_sha256"], "captured runner")
            check(Path(result["actual_command_source"]), result["actual_command_sha256"], "actual commands")
            for key, expected in result["input_sha256"].items():
                check(OUT / "decoded" / ("20261120_" + result["session"]) / (key + ".csv"), expected, "run input")
            if result["dt_s"] != .01 or result["window"] != windows[result["session"]]:
                failures.append(dict(context="R5 time/window mismatch", folder=str(folder)))
            for file, expected in [("steering_resolved.json", frozen_hashes["steering_sha256"]),
                                   ("vehicle_resolved.json", frozen_hashes["drive_sha256"])]:
                if json.loads((folder / file).read_text())["model_sha256"] != expected:
                    failures.append(dict(context="R5 runtime model pin", folder=str(folder), file=file))
        inventory.append(row)

    counts = collections.Counter(r["session"] for r in final)
    if set(counts) != set(windows) or any(count != 1 for count in counts.values()):
        failures.append(dict(context="R5 full coverage", counts=dict(counts), expected=sorted(windows)))
    summary = json.loads((OUT / "summary_R5.json").read_text())
    if summary["flagged_cases"] or not summary["all_circle_turn_targets_met"]:
        failures.append(dict(context="R5 acceptance flags", summary=summary))
    equivalence = json.loads((OUT / "straight_stationary_equivalence_R5.json").read_text())
    for name, reports in equivalence.items():
        for filename, report in reports.items():
            if filename == "family":
                continue
            if reports['family'] == 'straight':
                # Vehicle outputs must be exact. Inverting the collinear steering-table
                # anchor can add ~1e-12 deg of float roundoff without changing dynamics.
                allowed = 1e-9 if filename == 'steering_telemetry.csv' else 0
                if not report["same_shape"] or report["max_abs_difference"] > allowed:
                    failures.append(dict(context="straight equality", session=name, file=filename, report=report))
                if filename == 'steering_telemetry.csv' and report['actuator_dynamics_max_abs_difference'] != 0:
                    failures.append(dict(context="straight actuator dynamics", session=name, report=report))
            if reports['family'] == 'stationary' and filename == 'steering_telemetry.csv':
                if not report['same_shape'] or report['actuator_dynamics_max_abs_difference'] != 0:
                    failures.append(dict(context="stationary actuator dynamics", session=name, report=report))

    output = dict(status="PASS" if not failures else "FAIL", checked_files=len(checked),
                  protected_files=len(baseline["sha256"]), original_inputs=len(baseline["input_sha256"]),
                  final_cases=len(final), final_model_hashes=frozen_hashes,
                  native_attempts=len(inventory), attempt_statuses=dict(collections.Counter(r["status"] for r in inventory)),
                  completed_labels=dict(collections.Counter(r.get("label") for r in inventory if r["status"] == "PASS")),
                  straight_exact_vehicle_output_cases=sum(r['family']=='straight' for r in equivalence.values()),
                  numerical_steering_tolerance_deg=1e-9,
                  straight_max_actual_handwheel_difference_deg=max(r['steering_telemetry.csv']['actual_handwheel_max_abs_difference_deg'] for r in equivalence.values() if r['family']=='straight'),
                  stationary_actuator_dynamics_equal_cases=sum(r['family']=='stationary' for r in equivalence.values()),
                  failures=failures, sha256=checked)
    (OUT / "native_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (OUT / "final_integrity.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "sha256"}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
