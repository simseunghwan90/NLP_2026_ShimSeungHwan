"""Owned offscreen Unreal replay of recorded CAN, without transmitting CAN."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fit_steering import END, NEW, OLD, SPLIT, START, load_case, metrics
from intake import EVIDENCE, ROOT, digest

PROJECT = ROOT / "simulator/variants/field_20261120"
CASES = {
    "lat1": "LAT1_s1",
    "selfcheck": "SELFCHECK_s1",
    "move": "MOVE_LAT2_1_s2",
    "lat3": "LAT3_Apos_s1",
    "m8": "MOVE_LAT3_Apos_s2",
    "move_check": "MOVE_LAT2_2_s1",
}


def case_data(case):
    folder = EVIDENCE / "decoded" / ("20261120_" + CASES[case])
    commands = pd.read_csv(folder / "can_210.csv")
    feedback = pd.read_csv(folder / "can_200.csv")
    odom = pd.read_csv(folder / "odom.csv")
    if case == "lat1":
        start, end = START, END
    elif case == "selfcheck":
        from fit_steering import transitions

        changes = transitions(commands)
        start, end = float(changes[0] - 1), float(changes[-1] + 2)
    else:
        active = commands[commands.acc_pct > 0]
        start = max(float(commands.time_s.iloc[0]), float(active.time_s.iloc[0] - 1))
        end = start + (20 if case == "lat3" else 22)
    if end > min(commands.time_s.iloc[-1], odom.time_s.iloc[-1], feedback.time_s.iloc[-1]):
        raise ValueError("Insufficient source coverage")
    initial_speed = odom[(odom.time_s >= start) & (odom.time_s < start + 0.1)].speed_mps.max()
    if not np.isfinite(initial_speed) or initial_speed > 0.05:
        raise ValueError("Replay needs an initially stationary recording")
    initial = float(feedback[feedback.time_s <= start].iloc[-1].handwheel_deg)
    prefix = 2.0
    rows = [[0, 0, 100, round(initial, 1), 7]]
    selected = pd.concat(
        [commands[commands.time_s <= start].tail(1), commands[(commands.time_s > start) & (commands.time_s <= end)]]
    )
    for r in selected.itertuples(index=False, name=None):
        t, steer, brake, acc, flags = r
        row = [max(0, t - start) + prefix, acc, brake, steer, int(flags)]
        if len(rows) == 1 or row[1:] != rows[-1][1:]:
            rows.append(row)
    return start, end, prefix, rows, folder


def run(case, model_path, drive_path=None, label=None):
    tag = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{os.getpid()}_{case}_{label or model_path.stem}"
    out = EVIDENCE / "native_replays" / tag
    local = ROOT / "simulator/local/neighbor_steering" / tag
    out.mkdir(parents=True, exist_ok=False)
    start, end, prefix, commands, folder = case_data(case)
    model = json.loads(model_path.read_text())
    drive_path = drive_path or ROOT / model["base_longitudinal_model"]
    drive = json.loads(drive_path.read_text())
    # Use the established validator before passing any candidate to native code.
    sys.path.insert(0, str(ROOT / "analysis/lift_20261114"))
    from replay import validate_case, validate_model

    validate_model(drive)
    duration = prefix + end - start
    validate_case(dict(commands=commands, duration_s=duration, lift=False))
    cfg = dict(
        drive,
        model_sha256=digest(drive_path),
        lift=False,
        commands=commands,
        warmup_s=2,
        duration_s=duration,
        telemetry_path=str(out / "vehicle_telemetry.csv"),
        resolved_path=str(out / "vehicle_resolved.json"),
    )
    config = out / "replay.json"
    config.write_text(json.dumps(cfg, indent=2) + "\n")
    command = [
        sys.executable,
        str(ROOT / "analysis/field_20261120/launch.py"),
        "--map",
        "TestPad",
        "--offscreen",
        "--port",
        "41647",
        "--output",
        str(local),
        "--steering-model",
        str(model_path.resolve()),
        "--replay",
        str(config),
    ]
    result = dict(
        status="FAIL",
        case=case,
        command=command,
        can_start_s=start,
        can_end_s=end,
        prefix_s=prefix,
        warmup_s=2,
        duration_s=duration,
        dt_s=0.01,
        steering_model=str(model_path),
        steering_sha256=digest(model_path),
        drive_model=str(drive_path),
        drive_sha256=digest(drive_path),
        binary_sha256=digest(PROJECT / "Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so"),
        initial_condition="stationary; 2s initial feedback angle hold; then uninterrupted recorded commands",
        alignment="fixed source timestamps, no posthoc shift or observed state correction",
        wall_started=time.time(),
    )
    child = None
    print("Replay:", out, flush=True)
    try:
        with (out / "console.log").open("w") as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            code = child.wait(timeout=duration * 2 + 90)
        if code:
            raise RuntimeError(f"Unreal exit {code}")
        for name in [
            "steering_telemetry.csv",
            "steering_resolved.json",
            "steering_live.json",
            "physics.json",
            "settings.json",
            "runtime.log",
        ]:
            shutil.copy2(local / name, out / name)
        steer = pd.read_csv(out / "steering_telemetry.csv")
        v = pd.read_csv(out / "vehicle_telemetry.csv")
        for frame in [steer, v]:
            if not np.isfinite(frame.to_numpy()).all() or np.max(abs(frame.dt_s - 0.01)) > 1e-6:
                raise ValueError("Invalid native telemetry or timestep")
        if abs(v.t_s.iloc[-1] - duration) > 0.02:
            raise ValueError("Incomplete native rollout")
        if v[["fl_air", "fr_air", "rl_air", "rr_air"]].max().max() != 0:
            raise ValueError("Lost ground contact")
        resolved = json.loads((out / "steering_resolved.json").read_text())
        if resolved["model_sha256"] != digest(model_path):
            raise ValueError("Native model hash mismatch")
        reference = load_case(CASES[case], start, end)
        predicted = np.interp(reference["obs_t"], steer.simulation_s - 2 - prefix, steer.actual_handwheel_deg)
        result["steering"] = metrics(reference, predicted)
        if case == "lat1":
            result["steering_cycle2"] = metrics(reference, predicted, reference["obs_t"] >= SPLIT - start)
        pd.DataFrame(
            dict(
                time_s=reference["obs_t"],
                observed_deg=reference["y"],
                native_deg=predicted,
                transient=reference["transient"],
            )
        ).to_csv(out / "steering_comparison.csv", index=False)
        odom = pd.read_csv(folder / "odom.csv")
        odom = odom[(odom.time_s >= start) & (odom.time_s <= end)].copy()
        odom["relative_s"] = odom.time_s - start
        odom["native_speed_mps"] = np.interp(odom.relative_s, v.t_s - prefix, abs(v.speed_mps))
        wheel = pd.read_csv(folder / "can_201.csv")
        odom["can_wheel_speed_mps"] = np.interp(odom.time_s, wheel.time_s, (wheel.left_kph + wheel.right_kph) / 7.2)
        odom.to_csv(out / "speed_comparison.csv", index=False)
        result["speed"] = dict(
            rmse_mps=float(np.mean((odom.native_speed_mps - odom.speed_mps) ** 2) ** 0.5),
            observed_peak_mps=float(odom.speed_mps.max()),
            native_peak_mps=float(odom.native_speed_mps.max()),
            can_vs_gnss_rmse_mps=float(np.mean((odom.can_wheel_speed_mps - odom.speed_mps) ** 2) ** 0.5),
            native_final_mps=float(odom.native_speed_mps.iloc[-1]),
            observed_final_mps=float(odom.speed_mps.iloc[-1]),
        )
        if case in {"lat1", "selfcheck"} and abs(v.speed_mps).max() > 0.05:
            raise ValueError("Stationary replay moved")
        result["status"] = "PASS"
    except BaseException as exc:
        result["error"] = repr(exc)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        result["owned_process_stopped"] = child is None or child.poll() is not None
        result["wall_finished"] = time.time()
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    if result["status"] != "PASS":
        raise RuntimeError("Native replay failed: " + str(out))
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", choices=CASES)
    p.add_argument("--model", type=Path, default=NEW)
    p.add_argument("--previous", action="store_true")
    p.add_argument("--drive-model", type=Path)
    p.add_argument("--label")
    a = p.parse_args()
    run(a.case, OLD if a.previous else a.model, a.drive_model, a.label)
