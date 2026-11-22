"""Summarize recorded Unreal outputs; never tunes or changes time alignment."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from replay import EVIDENCE, ROOT

CANDIDATE = "v7"
BASELINE = "baseline60"


def crossing(t, y, threshold=10):
    idx = np.flatnonzero(y >= threshold)
    return float(t[idx[0]]) if len(idx) else None


def lift_metrics():
    rows = []
    for p in sorted((EVIDENCE / "runs").glob("*/result.json")):
        r = json.loads(p.read_text())
        if r["status"] != "PASS" or "mean_rpm_rmse" not in r:
            continue
        cfg = json.loads((p.parent / "replay.json").read_text())
        real = pd.read_csv(cfg["real_csv"])
        sim = pd.read_csv(p.parent / "telemetry.csv")
        t = real.t_s.to_numpy()
        y = (real.left_rpm + real.right_rpm).to_numpy() / 2
        sy = np.interp(t, sim.t_s, (sim.rl_rpm + sim.rr_rpm) / 2)
        cmd = np.array(cfg["commands"])
        row = dict(run=p.parent.name, case=r["case"], rmse=r["mean_rpm_rmse"], mae=r["mean_rpm_mae"],
                   real_t10=crossing(t, y), sim_t10=crossing(sim.t_s.to_numpy(), (sim.rl_rpm + sim.rr_rpm).to_numpy()/2))
        off_idx = np.flatnonzero((cmd[:-1, 1] > 0) & (cmd[1:, 1] == 0))
        on_idx = np.flatnonzero(cmd[:, 1] > 0)
        if "STEP" in r["case"] and len(on_idx):
            on = cmd[on_idx[0], 0]
            off = cmd[off_idx[0]+1, 0] if len(off_idx) else t[-1]
            for phase, mask in [("power", (t>on+1)&(t<off-.5)), ("coast", (t>off+.5)&(y>20))]:
                if sum(mask) > 10:
                    row[f"real_{phase}_slope_rpm_s"] = float(np.polyfit(t[mask], y[mask], 1)[0])
                    row[f"sim_{phase}_slope_rpm_s"] = float(np.polyfit(t[mask], sy[mask], 1)[0])
            if len(off_idx):
                for label, z in [("real", y), ("sim", sy)]:
                    stops = np.flatnonzero((t>off)&(z<10))
                    row[f"{label}_coast_to_10rpm_s"] = float(t[stops[0]]-off) if len(stops) else None
        rows.append(row)
    pd.DataFrame(rows).to_csv(EVIDENCE / "lift_metrics.csv", index=False)
    panels = [("step_r2", "LIFT-STEP-COAST_run9_r2", "60% fit"),
              ("step_r4", "LIFT-STEP-COAST_run9_r4", "70% fit"),
              ("step_r3", "LIFT-STEP-COAST_run9_r3", "65% development check"),
              ("step_r1", "LIFT-STEP-COAST_run9_r1", "55% development check"),
              ("ramp_r1", "LIFT-DZ-RAMP_run8_r1", "Ramp 1 development check"),
              ("hold", "LIFT-HOLD30_run12", "Hold development check")]
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    for ax, (suffix, case, title) in zip(axes.flat, panels):
        real = pd.read_csv(EVIDENCE / "inputs" / (case + ".csv"))
        ax.plot(real.t_s, (real.left_rpm + real.right_rpm)/2, color="black", lw=1.3, label="Real CAN (mean rear)")
        for model, color, label in [(BASELINE, "#9a9a9a", "Initial physics"), (CANDIDATE, "#087e8b", "Candidate " + CANDIDATE)]:
            name = model+"_"+suffix
            if name == "baseline_step_r2":
                name = "baseline_awake_60"
            p = EVIDENCE / "runs" / name / "telemetry.csv"
            if p.exists():
                f = pd.read_csv(p)
                ax.plot(f.t_s, (f.rl_rpm+f.rr_rpm)/2, color=color, lw=1.3, label=label)
        ax.set(title=title, xlabel="Time from fixed CAN boundary [s]", ylabel="Mean rear wheel [RPM]")
        ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Unreal physics replay vs real lift data — no time shift or measured-state injection")
    for ext in ["png", "pdf"]:
        fig.savefig(EVIDENCE / f"lift_comparison.{ext}", dpi=160)
    plt.close(fig)
    return rows


def ground_metrics():
    curves = {}
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    road = np.load(ROOT / "experiments/evidence/2026-11-10_drive/longitudinal_fit_data.npz")
    roadfit = json.loads((ROOT / "experiments/evidence/2026-11-10_drive/drive_candidate_fit.json").read_text())
    for model, color in [(BASELINE, "#888888"), (CANDIDATE, "#087e8b"), ("v3", "#cc7722")]:
        samples = []
        for pct in range(75, 101, 5):
            p = EVIDENCE / "runs" / f"{model}_ground_{pct}"
            if not (p / "result.json").exists():
                continue
            result = json.loads((p / "result.json").read_text())
            if result["status"] != "PASS":
                continue
            velocities, accelerations = [], []
            for run_dir in [p] + sorted(p.parent.glob(p.name + "_rolling*")):
                if not (run_dir / "result.json").exists():
                    continue
                check = json.loads((run_dir / "result.json").read_text())
                if check["status"] != "PASS" or max(check["contact_air_fraction"].values()) > .01:
                    continue
                f = pd.read_csv(run_dir / "telemetry.csv")
                cfg = json.loads((run_dir / "replay.json").read_text())
                acc = savgol_filter(f.speed_mps, 51, 3, deriv=1, delta=.01)
                mask = (f.t_s > cfg.get("measure_start_s", 1.2)) & (f.t_s < f.t_s.max()-.3) & (f.speed_mps > 1) & (f.speed_mps < 5.8) & (f.acc_pct == pct)
                velocities.extend(f.speed_mps.to_numpy()[mask])
                accelerations.extend(acc[mask])
            if not velocities:
                continue
            v, a = np.asarray(velocities), np.asarray(accelerations)
            order = np.argsort(v)
            curves[model, pct] = (v[order], a[order])
            near = abs(v-3).argmin()
            samples.append([pct, a[near]])
        if samples:
            samples = np.array(samples)
            ax.plot(samples[:, 0], samples[:, 1], "o-", color=color, label=model+" simulated (nearest 3 m/s)")
    xp = np.arange(75, 101, 5)
    pars = roadfit["parameters"]
    ax.plot(xp, pars[0]*(xp-75)/25+pars[1]-pars[2]*3, "ks--", label="Real bsw3 fitted target at 3 m/s")
    ax.set(xlabel="CAN accelerator [%]", ylabel="Flat / grade-adjusted acceleration [m/s²]", title="Development ground response diagnostic (not trajectory evaluation)")
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    for ext in ["png", "pdf"]:
        fig.savefig(EVIDENCE / f"ground_comparison.{ext}", dpi=160)
    plt.close(fig)

    def interpolate(model, u, speed):
        low = max(75, min(100, 5*np.floor(u/5)))
        high = min(100, low+5)
        values = []
        for pct in [low, high]:
            if (model, pct) not in curves:
                return np.nan
            v, a = curves[model, pct]
            if speed < v.min() or speed > v.max():
                return np.nan
            values.append(np.interp(speed, v, a))
        return values[0] if low == high else np.interp(u, [low, high], values)

    metrics = {}
    for name in road.files:
        data = road[name]
        preds = {m: np.array([interpolate(m, x[1], x[2]) for x in data]) for m in [BASELINE, CANDIDATE]}
        common = np.isfinite(preds[BASELINE]) & np.isfinite(preds[CANDIDATE])
        metrics[name] = {"total_samples": len(data), "common_supported_samples": int(sum(common)),
                         "outside_common_support": int(sum(~common)),
                         "mean_abs_error_mps2": {m: float(np.mean(abs(y[common]-data[common, -1]))) if common.any() else None for m, y in preds.items()}}
    (EVIDENCE / "ground_metrics.json").write_text(json.dumps(metrics, indent=2)+"\n")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default=CANDIDATE)
    parser.add_argument("--baseline", default=BASELINE)
    args = parser.parse_args()
    CANDIDATE, BASELINE = args.candidate, args.baseline
    rows = lift_metrics()
    print(pd.DataFrame(rows)[["run", "rmse", "mae"]].to_string(index=False))
    if (EVIDENCE / "runs" / (CANDIDATE+"_ground_100/result.json")).exists():
        print(json.dumps(ground_metrics(), indent=2))
