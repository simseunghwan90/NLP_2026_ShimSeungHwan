"""Initialize versioned PhysX candidates from development data, not final evaluation."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/evidence/2026-11-14_lift_calibration"
MODELS = ROOT / "models/candidates"


def initialize():
    targets = [OUT / "surrogate_fit.json"] + [MODELS / f"lift_2026-11-14_{v}.json" for v in ("v1", "v2")]
    if any(p.exists() for p in targets):
        raise FileExistsError("Preserved initialization exists; use new versioned output paths for a new experiment")
    datasets = []
    for rep in (2, 4):
        p = OUT / f"inputs/LIFT-STEP-COAST_run9_r{rep}"
        c = json.loads(p.with_suffix(".json").read_text())
        f = pd.read_csv(p.with_suffix(".csv"))
        datasets.append((c, f.t_s.to_numpy(), (f.left_rpm + f.right_rpm).to_numpy() / 2))

    def predict(parameters, config, t):
        drive = parameters[0] if config["commands"][1][1] == 60 else parameters[1]
        coast, drop = parameters[2:]
        start, off = config["commands"][1][0], config["commands"][-1][0]
        duration = np.maximum(0, np.minimum(t, off) - start)
        y = (drive - coast) / (drive * drop) * (-np.expm1(-drive * drop * duration))
        return np.maximum(0, y - coast * np.maximum(0, t - off))

    fit = least_squares(lambda p: np.concatenate([predict(p, c, t) - y for c, t, y in datasets]),
                        [240, 380, 143, .00025], bounds=([100, 200, 50, 1e-8], [500, 700, 250, .001]))
    a60, a70, coast, drop = fit.x
    report = {"method": "Affine wheel-RPM surrogate, initialization only; no time shift or output state injection",
              "parameters": dict(zip(["drive_rpm_s_60", "drive_rpm_s_70", "coast_rpm_s", "torque_curve_drop_per_wheel_rpm"], fit.x)),
              "fit_cases": [d[0]["case"] for d in datasets],
              "surrogate_rmse": {c["case"]: float(np.sqrt(np.mean((predict(fit.x,c,t)-y)**2))) for c,t,y in datasets}}
    (OUT / "surrogate_fit.json").write_text(json.dumps(report, indent=2) + "\n")
    ratio, wheel_moi, peak, radius = 9.23, .36551249, 57, .285
    road = json.loads((ROOT / "experiments/evidence/2026-11-10_drive/drive_candidate_fit.json").read_text())
    for label, motor_moi in (("v1", .1), ("v2", .005)):
        inertia = 2 * wheel_moi + motor_moi * ratio**2
        scale = inertia * np.pi / 30 / (peak * ratio)
        per_pct = (a70 - a60) / 10
        intercept = 60 - a60 / per_pct
        pedal_map = [[0, 0], [float(intercept), 0], [60, a60 * scale], [70, a70 * scale]]
        drag = coast * inertia * np.pi / 30 / 2
        if label == "v1":
            pedal_map.append([100, min(1.0, (a70 + 30 * per_pct) * scale)])
        else:
            # Non-unique joint candidate. Keep body mass/wheel inertia/peak torque
            # at initial assumed values; choose a smaller effective motor inertia
            # compatible with a monotone low-input and road-input pedal map.
            mass_eff = 550 + (2 * .34031251 + 2 * wheel_moi + motor_moi * ratio**2) / radius**2
            v = 3
            for pct, acc in zip(road["candidate"]["can_pct"][1:], road["candidate"]["target_effective_accel_mps2"][1:]):
                wheel_rpm = v / radius * 30 / np.pi
                torque = mass_eff * acc * radius + 2 * drag + 2 * .25 * v / .275
                throttle = torque / (peak * ratio * (1 - drop * wheel_rpm))
                pedal_map.append([pct, max(pedal_map[-1][1], throttle)])
        model = {"model_id": f"LIFT-CAL-20261114-{label}",
                 "provenance": "Development candidate. Torque/inertia scale is not uniquely identified. v1 retains initial motor inertia; v2 uses an assumed effective inertia to test joint consistency with prior road fit. Not measured rotor inertia or identified regenerative braking.",
                 "motor_moi_kg_m2": motor_moi, "rear_damping_nm_s": 0,
                 "rear_residual_torque_nm": float(drag), "motor_max_rpm": 10000,
                 "torque_curve": [[0,peak],[7500,float(peak*(1-drop*7500/ratio))],[10000,float(peak*(1-drop*10000/ratio))]],
                 "pedal_map": [[float(x),float(y)] for x,y in pedal_map]}
        (MODELS / f"lift_2026-11-14_{label}.json").write_text(json.dumps(model, indent=2) + "\n")
        print(label, "motor_moi", motor_moi, "rear_drag_each_Nm", drag, "map", pedal_map)


if __name__ == "__main__":
    initialize()
