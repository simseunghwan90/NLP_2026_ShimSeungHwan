"""Offline CAN intake and owned Unreal plant replay; never opens a CAN device."""

import argparse
import fcntl
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "experiments/evidence/2026-11-14_lift_calibration"
SOURCE = ROOT / "data/2026-11-14_lift/20261114"
DBC = ROOT / "data/specifications/can/2026-11-14_final/A1_dbc_2.bin"


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_can(path):
    """Required Intel signals, checked against the user-supplied definition."""
    definitions = DBC.read_bytes().decode("cp949")
    assert 'SG_ right_rpm : 12|12@1+ (1,0)' in definitions
    assert 'SG_ left_rpm : 36|12@1+ (1,0)' in definitions
    assert 'SG_ break_postion : 16|16@1- (1,0)' in definitions
    rows = {0x210: [], 0x201: [], 0x200: []}
    with path.open() as source:
        for line in source:
            p = line.split()
            if len(p) < 3 or "#" not in p[2]:
                continue
            ident, payload = p[2].split("#", 1)
            ident = int(ident, 16)
            if ident not in rows:
                continue
            b = bytes.fromhex(payload)
            if len(b) != 8:
                raise ValueError("Unexpected DLC")
            t = float(p[0].strip("()"))
            if ident == 0x210:
                row = [t, b[4], int.from_bytes(b[2:4], "little"), int.from_bytes(b[:2], "little", signed=True) / 10, b[5] & 7]
            elif ident == 0x201:
                r, l = int.from_bytes(b[:3], "little"), int.from_bytes(b[3:6], "little")
                row = [t, l >> 12, r >> 12, (l & 4095) / 10, (r & 4095) / 10]
            else:
                row = [t, int.from_bytes(b[2:4], "little", signed=True)]
            rows[ident].append(row)
    arrays = {k: np.asarray(v) for k, v in rows.items()}
    for a in arrays.values():
        if len(a) and np.any(np.diff(a[:, 0]) < 0):
            raise ValueError("Nonmonotonic original CAN timestamps")
    return arrays


def prepare():
    out = EVIDENCE / "inputs"
    out.mkdir(exist_ok=False)
    manifest = {"dbc_sha256": hash_file(DBC), "partition": "development only", "cases": {}}
    for cmdpath in sorted(SOURCE.glob("lift_acc_deadzone_*/*_cmd.csv")):
        if not any(s in cmdpath.name for s in ("run8_", "run9_", "run12_")):
            continue
        profile = pd.read_csv(cmdpath, low_memory=False)
        active = profile[profile.phase == "run"]
        begin, end = active.wall_s.iloc[0], active.wall_s.iloc[-1]
        canpath = cmdpath.parent / "candump_kv0.log"
        bus = read_can(canpath)
        c, w = bus[0x210], bus[0x201]
        powered = c[(c[:, 0] >= begin) & (c[:, 0] <= end) & (c[:, 1] > 0) & (c[:, 2] == 0)]
        start = max(begin, powered[0, 0] - 0.5)
        first = max(0, np.searchsorted(c[:, 0], start, side="right") - 1)
        selected = c[first:np.searchsorted(c[:, 0], end, side="right")].copy()
        max_gap = float(np.diff(selected[:, 0]).max())
        if max_gap > 0.15:
            raise ValueError(f"Command gap {max_gap}: {cmdpath}")
        selected[:, 0] -= start
        selected[0, 0] = 0
        changes = np.r_[True, np.any(np.diff(selected[:, 1:], axis=0) != 0, axis=1)]
        commands = selected[changes].tolist()
        real = w[(w[:, 0] >= start) & (w[:, 0] <= end)].copy()
        real[:, 0] -= start
        case = re.sub(r"^20261114_|_cmd$", "", cmdpath.stem)
        pd.DataFrame(real, columns=["t_s", "left_rpm", "right_rpm", "left_kph", "right_kph"]).to_csv(out / f"{case}.csv", index=False)
        config = {"case": case, "lift": True, "duration_s": float(end - start), "commands": commands,
                  "source_command_boundary": "CAN receive 0x210, not internal accepted torque",
                  "start_wall_s": float(start), "real_csv": str(out / f"{case}.csv")}
        (out / f"{case}.json").write_text(json.dumps(config, indent=2) + "\n")
        manifest[case] = {"can_sha256": hash_file(canpath), "request_csv_sha256": hash_file(cmdpath),
                          "max_command_gap_s": max_gap, "start_wall_s": float(start), "duration_s": float(end-start),
                          "observations": len(real), "command_changes": len(commands)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared", len(manifest) - 3, "cases")


def validate_model(model):
    allowed = {"pedal_map", "brake_map", "rear_coast_damping_nm_s", "rear_residual_torque_nm", "torque_scale", "torque_curve", "motor_max_rpm",
               "motor_moi_kg_m2", "rear_wheel_moi_kg_m2", "rear_damping_nm_s", "low_speed_substeps", "model_id", "provenance"}
    if set(model) - allowed:
        raise ValueError(f"Unknown model keys: {set(model)-allowed}")
    for map_key in ("pedal_map", "brake_map"):
        if map_key not in model:
            continue
        p = np.asarray(model[map_key], dtype=float)
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 2 or not np.isfinite(p).all():
            raise ValueError("Invalid pedal map")
        if p[0, 0] != 0 or p[-1, 0] != 100 or p[0, 1] != 0 or np.any(np.diff(p[:, 0]) <= 0) or np.any(np.diff(p[:, 1]) < 0) or np.any((p[:, 1] < 0) | (p[:, 1] > 1)):
            raise ValueError("Pedal map bounds/order")
    for key in allowed - {"pedal_map", "brake_map", "torque_curve", "model_id", "provenance"}:
        if key in model and (not np.isfinite(model[key]) or model[key] < 0):
            raise ValueError(f"Invalid {key}")
    for key in ("motor_moi_kg_m2", "rear_wheel_moi_kg_m2", "motor_max_rpm"):
        if key in model and model[key] <= 0:
            raise ValueError(f"Nonpositive {key}")
    if "low_speed_substeps" in model and (not 1 <= model["low_speed_substeps"] <= 60 or model["low_speed_substeps"] != int(model["low_speed_substeps"])):
        raise ValueError("Substep count must be an integer from 1 to 60")
    if "torque_curve" in model:
        p = np.asarray(model["torque_curve"])
        maxrpm = model.get("motor_max_rpm", 10000)
        if p.ndim != 2 or len(p) < 2 or len(p) > 8 or p.shape[1] != 2 or not np.isfinite(p).all() or np.any(np.diff(p[:, 0]) <= 0) or p[0, 0] != 0 or p[-1, 0] > maxrpm or np.any(p[:, 1] < 0) or p[:, 1].max() <= 0:
            raise ValueError("Invalid torque curve")


def validate_case(config):
    c = np.asarray(config["commands"], dtype=float)
    duration = config["duration_s"]
    if not isinstance(config["lift"], bool) or not np.isfinite(duration) or not 0 < duration <= 180:
        raise ValueError("Invalid fixture/duration")
    if c.ndim != 2 or c.shape[1] != 5 or len(c) < 1 or not np.isfinite(c).all():
        raise ValueError("Invalid command rows")
    if c[0, 0] != 0 or c[-1, 0] > duration or np.any(np.diff(c[:, 0]) <= 0):
        raise ValueError("Invalid command time")
    if np.any((c[:, 1:3] < 0) | (c[:, 1:3] > 100)) or np.any(abs(c[:, 3]) > 150):
        raise ValueError("Command outside DBC units/range")
    if np.any((c[:, 4] < 0) | (c[:, 4] > 7) | (c[:, 4] != np.floor(c[:, 4]))):
        raise ValueError("Invalid automatic mode bits")


def run(case_path, model_path, name, lift=None, fast=False):
    config = json.loads(case_path.read_text())
    model = json.loads(model_path.read_text())
    validate_model(model)
    config.update(model)
    if lift is not None:
        config["lift"] = lift
    validate_case(config)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("Run name must be a single safe path component")
    out = EVIDENCE / "runs" / name
    out.mkdir(parents=True, exist_ok=False)
    local = ROOT / "simulator/local/lift_calibration" / name
    local.mkdir(parents=True, exist_ok=False)
    config.update(telemetry_path=str(out / "telemetry.csv"), resolved_path=str(out / "resolved.json"))
    runtime = out / "replay.json"
    runtime.write_text(json.dumps(config, indent=2) + "\n")
    port = 41614
    selection = json.loads(subprocess.check_output(["bash", "simulator/run.sh", "--map", "TestPad", "--vehicle", "A1", "--mode", "vehicle", "--port", str(port), "--offscreen", "--output", str(local), "--dry-run"], cwd=ROOT))
    (local / "settings.json").write_text(json.dumps(selection["settings"], indent=2))
    command = [s for s in selection["command"] if not s.startswith(("-ExecCmds=", "-UserDir="))]
    command += [f"-ResearchReplay={runtime}", "-UseFixedTimeStep", "-FPS=100", "-ExecCmds=t.MaxFPS 100", f"-UserDir={local / 'user'}"]
    if fast:
        # Fixed simulation dt remains 10 ms; only remove wall-clock pacing.
        command = [s for s in command if not s.startswith(("-ExecCmds=", "-ResX=", "-ResY="))]
        command += ["-ExecCmds=t.MaxFPS 0", "-ResX=640", "-ResY=360"]
    env = dict(os.environ, **{"UE-LocalDataCachePath": str(ROOT / "simulator/local/ddc")})
    result = {"status": "FAIL", "case": config["case"], "model": model, "command": command,
              "status_meaning": "fixture, finite rollout and timing checks; not model acceptance",
              "source_case_sha256": hash_file(case_path), "model_sha256": hash_file(model_path), "physical_dt_requested_s": 0.01,
              "started_wall_s": time.time(), "wall_clock_pacing": not fast, "environment": {"platform": platform.platform(), "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}}
    tracked = [Path(__file__).resolve(), ROOT / "simulator/Plugins/AirSim/Source/Vehicles/Car/ResearchReplay.cpp",
               ROOT / "simulator/Plugins/AirSim/Source/Vehicles/Car/ResearchReplay.h",
               ROOT / "simulator/Plugins/AirSim/Source/Vehicles/Car/CarPawnSimApi.cpp",
               ROOT / "simulator/Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so", DBC]
    result["artifact_sha256"] = {str(p.relative_to(ROOT)): hash_file(p) for p in tracked}
    (out / "settings.json").write_text(json.dumps(selection["settings"], indent=2) + "\n")
    child = None
    try:
        with (ROOT / "simulator/local/simulator.lock").open("a") as lock, (out / "unreal.log").open("w") as log:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with socket.socket() as sock:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError("Research RPC port occupied")
            child = subprocess.Popen(command, cwd=local, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            result["owned_pid"] = child.pid
            child.wait(timeout=max(120, config["duration_s"] * 4 + 60))
            result["exit_code"] = child.returncode
            if child.returncode != 0:
                raise RuntimeError(f"Unreal exit {child.returncode}")
        frame = pd.read_csv(out / "telemetry.csv")
        if not np.isfinite(frame.to_numpy()).all() or frame.t_s.iloc[-1] < config["duration_s"] - 0.02:
            raise RuntimeError("Incomplete/nonfinite rollout")
        result["dt_min_max"] = [float(frame.dt_s.min()), float(frame.dt_s.max())]
        result["contact_air_fraction"] = frame[[f"{w}_air" for w in ("fl", "fr", "rl", "rr")]].mean().to_dict()
        result["chassis_span_m"] = (frame[["x_m", "y_m", "z_m"]].max() - frame[["x_m", "y_m", "z_m"]].min()).to_dict()
        if config["lift"]:
            if frame.rl_air.mean() < 0.999 or frame.rr_air.mean() < 0.999 or frame.fl_air.mean() > 0.01 or frame.fr_air.mean() > 0.01:
                raise RuntimeError("Lift contact condition failed")
            if max(result["chassis_span_m"].values()) > 0.001:
                raise RuntimeError("Lift chassis moved")
        elif frame.z_m.max() - frame.z_m.min() > 0.5:
            raise RuntimeError("Ground rollout left pad")
        if max(abs(frame.dt_s - 0.01)) > 1e-5:
            raise RuntimeError("Unexpected physics frame timestep")
        result["status"] = "PASS"
        if config.get("real_csv") and config["lift"]:
            real = pd.read_csv(config["real_csv"])
            errors = []
            for side, wheel in (("left", "rl"), ("right", "rr")):
                e = np.interp(real.t_s, frame.t_s, frame[f"{wheel}_rpm"]) - real[f"{side}_rpm"]
                errors.append(e)
                result[f"{side}_rpm_rmse"] = float(np.sqrt(np.mean(e**2)))
            e = (errors[0] + errors[1]) / 2
            result["mean_rpm_rmse"] = float(np.sqrt(np.mean(e**2)))
            result["mean_rpm_mae"] = float(np.mean(abs(e)))
    except Exception as exc:
        result["error"] = repr(exc)
        raise
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        result["finished_wall_s"] = time.time()
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: result[k] for k in ("status", "case", "mean_rpm_rmse", "error") if k in result}), flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    r = sub.add_parser("run")
    r.add_argument("case", type=Path)
    r.add_argument("model", type=Path)
    r.add_argument("name")
    r.add_argument("--fast", action="store_true", help="Remove wall-clock pacing while retaining fixed 10 ms simulation time")
    args = p.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        run(args.case.resolve(), args.model.resolve(), args.name, fast=args.fast)
