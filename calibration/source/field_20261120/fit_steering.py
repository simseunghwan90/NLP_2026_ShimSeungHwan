"""Fit effective steering dynamics to the first stationary LAT1 cycle only."""

import argparse
import ctypes
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from intake import EVIDENCE, ROOT, digest
from scipy.optimize import differential_evolution

OLD = ROOT / "models/candidates/steering_neighbor_2026-11-17_v1.json"
NEW = ROOT / "models/candidates/steering_field_2026-11-20_v1.json"
START = 1795153617.753108
SPLIT = 1795153672.44181
END = 1795153725.113237
HEADER = ROOT / "simulator/variants/neighbor_steering/Plugins/AirSim/Source/Vehicles/Car/SteeringDynamics.h"


def build_kernel(output):
    library = output / "steering_kernel.so"
    command = [
        "g++",
        "-std=c++14",
        "-O3",
        "-shared",
        "-fPIC",
        "-I",
        str(HEADER.parent),
        str(Path(__file__).with_name("steering_kernel.cpp")),
        "-o",
        str(library),
    ]
    subprocess.run(command, check=True, capture_output=True)
    native = ctypes.CDLL(str(library)).rollout
    array = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags="C_CONTIGUOUS")
    native.argtypes = [
        array,
        ctypes.c_int,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        array,
    ]
    native.restype = None
    return native, command


def transitions(commands):
    changes = commands.time_s.to_numpy()[np.r_[False, np.diff(commands.handwheel_deg) != 0]]
    if not len(changes):
        return changes
    return changes[np.r_[True, np.diff(changes) > 0.1]]


def load_case(name, start, end, dt=0.01):
    folder = EVIDENCE / "decoded" / ("20261120_" + name)
    commands = pd.read_csv(folder / "can_210.csv")
    feedback = pd.read_csv(folder / "can_200.csv")
    observed = feedback[(feedback.time_s >= start) & (feedback.time_s <= end)].copy()
    grid = np.arange(0, end - start + dt, dt)
    indices = np.searchsorted(commands.time_s.to_numpy() - start, grid, side="right") - 1
    if indices.min() < 0 or not len(observed):
        raise ValueError("Missing initial command/feedback")
    u = np.ascontiguousarray(commands.handwheel_deg.to_numpy()[indices])
    initial = float(feedback[feedback.time_s <= start].iloc[-1].handwheel_deg)
    obs_t = observed.time_s.to_numpy() - start
    mask = np.zeros(len(observed), dtype=bool)
    for t in transitions(commands) - start:
        mask |= (obs_t >= t) & (obs_t < t + 1)
    return dict(
        grid=grid,
        u=u,
        initial=initial,
        obs_t=obs_t,
        y=observed.handwheel_deg.to_numpy(),
        transient=mask,
        dt=dt,
        start=start,
    )


def predict(native, case, params):
    out = np.empty(len(case["u"]), dtype=np.float64)
    native(case["u"], len(out), case["dt"], case["initial"], *params, out)
    return np.interp(case["obs_t"], case["grid"], out)


def metrics(case, predicted, mask=None):
    mask = np.ones(len(predicted), dtype=bool) if mask is None else mask
    error = predicted - case["y"]
    transient = mask & case["transient"]
    return dict(
        n=int(mask.sum()),
        rmse_deg=float(np.mean(error[mask] ** 2) ** 0.5),
        transient_rmse_deg=float(np.mean(error[transient] ** 2) ** 0.5) if transient.any() else None,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE / "steering_fit")
    parser.add_argument("--model-output", type=Path, default=NEW)
    args = parser.parse_args()
    output = args.output
    if args.model_output.exists():
        raise FileExistsError("Choose a new model output; preserve previous candidates")
    output.mkdir(exist_ok=False)
    native, build_command = build_kernel(output)
    old = json.loads(OLD.read_text())
    keys = ["effective_delay_s", "natural_frequency_rad_s", "damping_ratio"]
    previous = [old[k] for k in keys]
    fit = load_case("LAT1_s1", START, SPLIT)

    def objective(params):
        error = predict(native, fit, params) - fit["y"]
        # Whole first-cycle MSE; transient metric is a separate acceptance check.
        return float(np.mean(error**2))

    result = differential_evolution(
        objective,
        [(0, 0.4), (2, 40), (0.2, 2)],
        seed=20261120,
        maxiter=100,
        popsize=12,
        tol=1e-8,
        polish=False,
        workers=1,
    )
    params = [float(round(v, 6)) for v in result.x]
    all_lat = load_case("LAT1_s1", START, END)
    baseline, candidate = predict(native, all_lat, previous), predict(native, all_lat, params)
    check = all_lat["obs_t"] >= SPLIT - START
    report = dict(
        experiment="FIELD-CAL-20261120-01",
        native_header_sha256=digest(HEADER),
        build_command=build_command,
        fit_start=START,
        split=SPLIT,
        end=END,
        dt_s=0.01,
        fit_cost="first-cycle whole trajectory MSE",
        params=dict(zip(keys, params)),
        optimizer=dict(success=bool(result.success), message=str(result.message), nfev=result.nfev, fun=result.fun),
        cycle1=dict(old=metrics(all_lat, baseline, ~check), new=metrics(all_lat, candidate, ~check)),
        cycle2=dict(old=metrics(all_lat, baseline, check), new=metrics(all_lat, candidate, check)),
    )
    pd.DataFrame(
        dict(
            time_s=all_lat["obs_t"],
            observed_deg=all_lat["y"],
            old_deg=baseline,
            candidate_deg=candidate,
            transient=all_lat["transient"],
            internal_check=check,
        )
    ).to_csv(output / "lat1_comparison.csv", index=False)
    self_commands = pd.read_csv(EVIDENCE / "decoded/20261120_SELFCHECK_s1/can_210.csv")
    moves = transitions(self_commands)
    self_case = load_case("SELFCHECK_s1", float(moves[0] - 1), float(moves[-1] + 2))
    self_old, self_new = predict(native, self_case, previous), predict(native, self_case, params)
    report["selfcheck"] = dict(
        old=metrics(self_case, self_old),
        new=metrics(self_case, self_new),
        start=self_case["start"],
        end=float(self_case["start"] + self_case["grid"][-1]),
    )
    pd.DataFrame(
        dict(time_s=self_case["obs_t"], observed_deg=self_case["y"], old_deg=self_old, candidate_deg=self_new)
    ).to_csv(output / "selfcheck_comparison.csv", index=False)
    c2 = report["cycle2"]
    report["acceptance_numerical"] = bool(
        c2["new"]["transient_rmse_deg"] <= 0.9 * c2["old"]["transient_rmse_deg"]
        and c2["new"]["rmse_deg"] <= 1.05 * c2["old"]["rmse_deg"]
    )
    model = dict(old, model_id="STEER-FIELD-20261120-v1", **dict(zip(keys, params)))
    model["provenance"] = dict(
        source_archive_sha256="67097a4372d54a49dfe0a630b33aee74ac2b296a7deac5f5827c73806a07db33",
        experiment="FIELD-CAL-20261120-01",
        dynamics="Fit LAT1 cycle1 final CAN 0x210 to 0x200, original timestamps",
        delay="Effective CAN-to-feedback delay, not pure actuator hardware latency; replaces previous 0.088s",
        geometry="Inherited neighbor ratio/inner tire convention; not identified by this stationary capture",
        rate_limit="Inherited assumption 140 deg/s; not identified by +/-20deg stationary ramps",
        limits="Low amplitude stationary development fit; no high-speed, road geometry or final evaluation claim",
        validation_status="Numerical candidate; see experiment report for native acceptance",
        previous_model=str(OLD.relative_to(ROOT)),
        previous_model_sha256=digest(OLD),
    )
    args.model_output.write_text(json.dumps(model, indent=2) + "\n")
    report["model_sha256"] = digest(args.model_output)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
