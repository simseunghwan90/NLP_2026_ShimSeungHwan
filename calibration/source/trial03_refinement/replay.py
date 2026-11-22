"""Full-maneuver staged replay, derived from the preserved follow-up runner."""

import argparse
import importlib.util
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from validation import validate_case

import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "field_20261121"))
from analyze import load
from intake import ROOT, digest

OUT = ROOT / "experiments/evidence/2026-11-21_trial03_refinement"
PROJECT = ROOT / "simulator/variants/refine_20261121"
LOADED_SOURCE = Path(__file__).read_bytes()


def prepare_windows():
    windows = {}
    sessions = [
        "LAT4_L150_s1",
        "LAT4_R150_s2",
        "LAT4_L120_s1",
        "LAT4_R120_s1",
        "LAT4_L75_s1",
        "LAT4_R75_s1",
        "LAT3_Apos_s2",
        "LAT3_Aneg_s1",
        "LON1_Apos_v8_s1",
        "LON2_Apos_s1",
        "LON2_Aneg_s1",
        "LON3_Aneg_s1",
        "LONK_Apos_v20_s1",
        "LONK_Apos_v30_s1",
        "LONK_Aneg_v30_s1",
        "LON5_Aneg_v50_s1",
    ]
    for name in sessions:
        c, o = load(name, "commands"), load(name, "odom")
        first = float(c[c.acc_pct >= 50].time_s.iloc[0])
        start = first - 1
        if name.startswith("LON5"):
            keep = pd.read_csv(OUT / "raw/20261120_LON5_Aneg_v50_s1/keep_cmd.csv", comment="#")
            start, end = float(keep.wall_s.iloc[0] - 1), float(keep.wall_s.iloc[-1] + 1)
        else:
            durations = 65 if name.startswith("LAT4") else 60 if name.startswith(("LON3", "LONK")) else 32
            end = min(start + durations, float(c.time_s.iloc[-1] - 0.1), float(o.time_s.iloc[-1] - 0.1))
        start = max(start, float(c.time_s.iloc[0]))
        initial = o[(o.time_s >= start - 0.1) & (o.time_s <= start + 0.1)]
        windows[name] = {
            "start_s": start,
            "end_s": end,
            "initial_speed_mps": float(initial.speed_mps.max()),
            "role": "internal_check"
            if name in ["LAT4_L120_s1", "LAT4_R120_s1", "LON2_Aneg_s1", "LONK_Aneg_v30_s1"]
            else "development",
        }
    path = OUT / "windows.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(windows, indent=2) + "\n")
    print(json.dumps(windows, indent=2))


def run(name, steering, drive=None, label=None, original=False):
    project = ROOT / "simulator/variants/field_20261121" if original else PROJECT
    window_file = OUT / "windows_v2.json" if (OUT / "windows_v2.json").exists() else OUT / "windows.json"
    windows = json.loads(window_file.read_text())
    if (OUT / "windows_regression.json").exists():
        windows.update(json.loads((OUT / "windows_regression.json").read_text()))
    window = windows[name]
    start, end = window["start_s"], window["end_s"]
    if window["initial_speed_mps"] > 0.05:
        raise ValueError("Nonstationary initial condition")
    if digest(ROOT / window["command_source"]) != window["command_sha256"]:
        raise ValueError("Frozen command source changed")
    c, f = load(name, "commands"), load(name, "feedback")
    boundary = "observed CAN decoded in bag; original header timestamp"
    command_file = OUT / "decoded" / ("20261120_" + name) / "commands.csv"
    if window["role"] == "previous_development_regression":
        command_file = (
            ROOT / "experiments/evidence/2026-11-20_field_update/decoded" / ("20261120_" + name) / "can_210.csv"
        )
        c = pd.read_csv(command_file)
        boundary = "previous archived original kvaser CAN 0x210; unchanged regression window"
    if name.startswith("LON5"):
        command_file = OUT / "lon5_raw_210.csv"
        c = pd.read_csv(command_file)
        boundary = "original kvaser CAN 0x210 timestamp"
    c = c.sort_values("time_s")
    selected = pd.concat([c[c.time_s <= start].tail(1), c[(c.time_s > start) & (c.time_s <= end)]])
    if not len(selected) or selected.time_s.iloc[0] > start or end - selected.time_s.iloc[-1] > 0.1:
        raise ValueError("Insufficient command coverage")
    if selected.time_s.diff().max() > 0.1:
        raise ValueError("Command gap exceeds 100ms")
    prefix = 3.0
    initial_feedback = f[f.time_s <= start]
    if initial_feedback.empty:
        raise ValueError("Initial steering feedback unavailable at fixed window start")
    initial = float(initial_feedback.handwheel_deg.iloc[-1])
    rows = [[0, 0, 100, float(np.clip(round(initial, 1), -150, 150)), 7]]
    for r in selected.itertuples():
        row = [
            max(0, r.time_s - start) + prefix,
            int(r.acc_pct),
            int(r.brake_pct),
            round(r.handwheel_deg, 1),
            int(r.flags),
        ]
        if len(rows) == 1 or row[1:] != rows[-1][1:]:
            rows.append(row)
    model = json.loads(steering.read_text())
    if "native_project" in model and (ROOT / model["native_project"]).resolve() != project.resolve():
        raise ValueError("Model project differs from the declared experiment project")
    drive = drive or ROOT / model["base_longitudinal_model"]
    d = json.loads(drive.read_text())
    spec = importlib.util.spec_from_file_location("lift_validator", ROOT / "analysis/lift_20261114/replay.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    from model_validation import validate_model
    validate_model(d)
    duration = end - start + prefix
    validate_case(dict(commands=rows, duration_s=duration, lift=False))
    tag = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{name}_{Path(label).stem if label else steering.stem}"
    out = OUT / "native_replays" / tag
    out.mkdir(parents=True, exist_ok=False)
    (out / "runner_source.py").write_bytes(LOADED_SOURCE)
    local = ROOT / "simulator/local/neighbor_steering" / tag
    cfg = dict(
        d,
        model_sha256=digest(drive),
        lift=False,
        commands=rows,
        warmup_s=2,
        duration_s=duration,
        telemetry_path=str(out / "vehicle_telemetry.csv"),
        resolved_path=str(out / "vehicle_resolved.json"),
    )
    config = out / "replay.json"
    config.write_text(json.dumps(cfg, indent=2) + "\n")
    cmd = [
        sys.executable,
        str(ROOT / "analysis/trial03_refinement/launch.py"),
        "--map",
        "TestPad",
        "--offscreen",
        "--port",
        "41669",
        "--output",
        str(local),
        "--steering-model",
        str(steering.resolve()),
        "--replay",
        str(config),
    ]
    result = dict(
        status="FAIL",
        session=name,
        label=label,
        window=window,
        input_boundary=boundary,
        command=cmd,
        steering_model=str(steering),
        steering_sha256=digest(steering),
        drive_model=str(drive),
        drive_sha256=digest(drive),
        binary_sha256=digest(project / "Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so"),
        native_project=str(project),
        dt_s=0.01,
        time_alignment="fixed timestamps; no posthoc shift; no observed-state injection",
        wall_started=time.time(),
    )
    result["input_sha256"] = {
        key: digest(OUT / "decoded" / ("20261120_" + name) / (key + ".csv"))
        for key in ["commands", "feedback", "odom", "state"]
    }
    result["actual_command_source"] = str(command_file)
    result["actual_command_sha256"] = digest(command_file)
    result["map_sha256"] = digest(project / "Content/Maps/TestPad/TestPad.umap")
    result["source_sha256"] = hashlib.sha256(LOADED_SOURCE).hexdigest()
    result["windows_sha256"] = digest(window_file)
    child = None
    print("Replay", out, flush=True)
    try:
        with (out / "console.log").open("w") as log:
            child = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                     env=dict(os.environ, STAGED_AUDIT_ORIGINAL="1" if original else "0"))
            rc = child.wait(timeout=duration * 3 + 120)
        if rc:
            raise RuntimeError("Unreal exit " + str(rc))
        v = pd.read_csv(out / "vehicle_telemetry.csv")
        s = pd.read_csv(local / "steering_telemetry.csv")
        import shutil

        for filename in [
            "steering_telemetry.csv",
            "steering_resolved.json",
            "physics.json",
            "settings.json",
            "steering_live.json",
            "runtime.log",
        ]:
            shutil.copy2(local / filename, out / filename)
        if (
            not np.isfinite(v.to_numpy()).all()
            or np.max(abs(v.dt_s - 0.01)) > 1e-6
            or abs(v.t_s.iloc[-1] - duration) > 0.03
        ):
            raise ValueError("Invalid or incomplete native rollout")
        if v[["fl_air", "fr_air", "rl_air", "rr_air"]].max().max() != 0:
            raise ValueError("Ground contact lost")
        steering_resolved = json.loads((out / "steering_resolved.json").read_text())
        if steering_resolved["model_sha256"] != digest(steering):
            raise ValueError("Steering model hash mismatch")
        if json.loads((out / "vehicle_resolved.json").read_text())["model_sha256"] != digest(drive):
            raise ValueError("Drive model hash mismatch")
        v0 = v.iloc[abs(v.t_s - prefix).argmin()]
        s0 = s.iloc[abs(s.simulation_s - (2 + prefix)).argmin()]
        result["initial_state"] = dict(native_speed_mps=float(v0.speed_mps),
                                       measured_speed_limit_mps=window["initial_speed_mps"],
                                       prepared_handwheel_target_deg=initial,
                                       native_handwheel_deg=float(s0.actual_handwheel_deg))
        if abs(v0.speed_mps) > .05 or abs(s0.actual_handwheel_deg - initial) > .2:
            raise ValueError("Initial preparation mismatch")
        if window.get("stationary") and abs(v.speed_mps).max() > .05:
            raise ValueError("Stationary replay moved")
        o = load(name, "odom")
        o = o[(o.time_s >= start) & (o.time_s <= end)].copy()
        o["relative_s"] = o.time_s - start
        o["native_speed_mps"] = np.interp(o.relative_s, v.t_s - prefix, abs(v.speed_mps))
        o.to_csv(out / "speed_comparison.csv", index=False)
        error = o.native_speed_mps - o.speed_mps
        result["speed"] = {
            "rmse_mps": float(np.sqrt(np.mean(error**2))),
            "observed_peak_mps": float(o.speed_mps.max()),
            "native_peak_mps": float(o.native_speed_mps.max()),
            "observed_final_mps": float(o.speed_mps.iloc[-1]),
            "native_final_mps": float(o.native_speed_mps.iloc[-1]),
        }
        fs = f[(f.time_s >= start) & (f.time_s <= end)]
        pred = np.interp(fs.time_s - start, s.simulation_s - 2 - prefix, s.actual_handwheel_deg)
        result["steering_rmse_deg"] = float(np.sqrt(np.mean((pred - fs.handwheel_deg) ** 2)))
        pd.DataFrame(dict(relative_s=fs.time_s-start, observed_deg=fs.handwheel_deg,
                          native_deg=pred)).to_csv(out / "steering_comparison.csv", index=False)
        if name == "LAT1_s1":
            second = fs.time_s >= 1795153672.44181
            result["steering_cycle2_rmse_deg"] = float(np.sqrt(np.mean((pred[second]-fs.handwheel_deg[second])**2)))
        if "rear_x_m" in v:
            g = load(name, "state")
            g = g[g.time_s.between(start, end)].copy()
            tg = g.time_s.to_numpy() - start
            measured_yaw = np.unwrap(np.arctan2(2 * (g.qw * g.qz + g.qx * g.qy), 1 - 2 * (g.qy**2 + g.qz**2)))
            native_yaw = np.unwrap(-np.deg2rad(v.yaw_ue_deg.to_numpy()))
            yaw0 = float(np.interp(prefix, v.t_s, native_yaw))
            # Initial pose is the sole alignment. Both positions refer to rear axle centers.
            shift = float(measured_yaw[0] - yaw0)
            nx = np.interp(tg, v.t_s - prefix, v.rear_x_m) - np.interp(prefix, v.t_s, v.rear_x_m)
            ny = -np.interp(tg, v.t_s - prefix, v.rear_y_m) + np.interp(prefix, v.t_s, v.rear_y_m)
            px = np.cos(shift) * nx - np.sin(shift) * ny + g.x_m.iloc[0]
            py = np.sin(shift) * nx + np.cos(shift) * ny + g.y_m.iloc[0]
            heading = np.interp(tg, v.t_s - prefix, native_yaw) + shift
            herror = np.arctan2(np.sin(heading - measured_yaw), np.cos(heading - measured_yaw))
            poserror = np.hypot(px - g.x_m, py - g.y_m)
            result["trajectory"] = {
                "endpoint_m": float(poserror.iloc[-1]),
                "heading_endpoint_deg": float(abs(np.degrees(herror[-1]))),
                "position_rmse_m": float(np.sqrt(np.mean(poserror**2))),
                "heading_rmse_deg": float(np.sqrt(np.mean(np.degrees(herror)**2))),
                "basis": "GnssState declared rear axle vs native rear wheel midpoint; initial pose only; captured extrinsics not independently verified",
            }
            pd.DataFrame(
                dict(
                    relative_s=tg,
                    observed_x=g.x_m,
                    observed_y=g.y_m,
                    native_x=px,
                    native_y=py,
                    observed_heading_rad=measured_yaw,
                    native_heading_rad=heading,
                )
            ).to_csv(out / "trajectory_comparison.csv", index=False)
        # Curvature from the native chassis path, fixed central difference in simulation time.
        # Translation/rotation invariant; no measured trajectory is used to align it.
        motion = v[(v.t_s >= prefix + 5) & (abs(v.speed_mps) > 1)].copy()
        if len(motion) > 300:
            stride = 100
            x, y = motion.x_m.to_numpy(), motion.y_m.to_numpy()
            xa, ya = x[stride:-stride] - x[: -2 * stride], y[stride:-stride] - y[: -2 * stride]
            xb, yb = x[2 * stride :] - x[stride:-stride], y[2 * stride :] - y[stride:-stride]
            turn = np.arctan2(xa * yb - ya * xb, xa * xb + ya * yb)
            k = turn / ((np.hypot(xa, ya) + np.hypot(xb, yb)) / 2)
            # UE Y is right; ROS positive left.
            result["native_curvature_median"] = float(-np.median(k))
        result["status"] = "PASS"
    except BaseException as e:
        result["error"] = repr(e)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        result["wall_finished"] = time.time()
        result["owned_process_stopped"] = child is None or child.poll() is not None
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("case")
    p.add_argument("--steering", type=Path, default=ROOT / "models/candidates/steering_field_2026-11-20_v2.json")
    p.add_argument("--drive", type=Path)
    p.add_argument("--label")
    p.add_argument("--original", action="store_true", help="Use preserved pre-audit binary for equivalence check")
    a = p.parse_args()
    if a.case == "prepare":
        prepare_windows()
    else:
        r = run(a.case, a.steering, a.drive, a.label, a.original)
        if r["status"] != "PASS":
            sys.exit(1)
