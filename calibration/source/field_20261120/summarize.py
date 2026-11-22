"""Summarize completed native replays without changing inputs or time alignment."""

import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/a1_field_matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from intake import EVIDENCE


def main():
    runs = []
    for p in sorted((EVIDENCE / "native_replays").glob("*/result.json")):
        r = json.loads(p.read_text())
        runs.append((p.parent, r))

    def select(case, ending):
        return next(
            (p, r) for p, r in reversed(runs) if r["status"] == "PASS" and r["case"] == case and p.name.endswith(ending)
        )

    report = dict(
        native_pass_count=sum(r["status"] == "PASS" for _, r in runs),
        native_failures=[
            dict(path=str(p.relative_to(EVIDENCE)), error=r["error"]) for p, r in runs if r["status"] != "PASS"
        ],
        owned_processes_stopped=all(r["owned_process_stopped"] for _, r in runs),
        steering={},
        drive={},
    )
    old_p, old_r = select("lat1", "steering_neighbor_2026-11-17_v1")
    new_p, new_r = select("lat1", "steering_field_2026-11-20_v1")
    report["steering"] = dict(
        old=old_r["steering_cycle2"],
        new=new_r["steering_cycle2"],
        runs=[str(p.relative_to(EVIDENCE)) for p in [old_p, new_p]],
    )
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), layout="constrained")
    old_f, new_f = pd.read_csv(old_p / "steering_comparison.csv"), pd.read_csv(new_p / "steering_comparison.csv")
    for ax, (lo, hi) in zip(axes, [(54, 107.36), (65, 70)]):
        ax.plot(new_f.time_s, new_f.observed_deg, label="Recorded CAN feedback", lw=1)
        ax.plot(old_f.time_s, old_f.native_deg, label="Previous native model", lw=1)
        ax.plot(new_f.time_s, new_f.native_deg, label="Field native model", lw=1)
        ax.set(xlim=(lo, hi), xlabel="Time from fixed CAN origin (s)", ylabel="Handwheel (deg)")
        ax.grid(alpha=0.25)
    axes[0].legend(ncol=3)
    fig.savefig(EVIDENCE / "steering_native.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    for ax, case in zip(axes.flat, ["move", "lat3", "move_check", "m8"]):
        bp, br = select(case, "v7_field_steer")
        cp, cr = select(case, "drive_trial02" if case in {"move", "lat3"} else "final")
        b, c = pd.read_csv(bp / "speed_comparison.csv"), pd.read_csv(cp / "speed_comparison.csv")
        ax.plot(c.relative_s, c.speed_mps, label="Recorded GNSS")
        ax.plot(c.relative_s, c.can_wheel_speed_mps, label="Recorded wheel CAN", alpha=0.6)
        ax.plot(b.relative_s, b.native_speed_mps, label="Previous v7")
        ax.plot(c.relative_s, c.native_speed_mps, label="Field ground model")
        ax.set(
            title=case + (" (selection)" if case in {"move", "lat3"} else " (internal check)"),
            xlabel="Time from fixed CAN origin (s)",
            ylabel="Speed (m/s)",
        )
        ax.grid(alpha=0.25)
        report["drive"][case] = dict(
            old=br["speed"], new=cr["speed"], runs=[str(p.relative_to(EVIDENCE)) for p in [bp, cp]]
        )
    axes[0, 0].legend(fontsize=8)
    fig.savefig(EVIDENCE / "drive_native.png", dpi=150)
    plt.close(fig)
    (EVIDENCE / "summary.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
