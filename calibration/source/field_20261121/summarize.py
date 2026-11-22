"""Summarize every preserved native attempt and plot fixed-time development comparisons."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from intake import OUT

COLORS = {
    "previous": "#4C78A8",
    "geometry": "#F58518",
    "trial01": "#54A24B",
    "trial02": "#B279A2",
    "trial03": "#E45756",
    "driveonly03": "#79706E",
}


def ordered(frame):
    return frame.assign(order=frame.label.map({name: i for i, name in enumerate(COLORS)})).sort_values("order")


def label(value):
    for name in ["trial01", "trial02", "trial03"]:
        if name in str(value):
            return name
    return "previous" if str(value).startswith("previous") else value


def main():
    records = []
    for path in sorted((OUT / "native_replays").rglob("result.json")):
        d = json.loads(path.read_text())
        row = {
            "session": d["session"],
            "label": label(d["label"]),
            "status": d["status"],
            "path": str(path.parent),
            "wall_started": d["wall_started"],
            "binary_sha256": d["binary_sha256"],
            "error": d.get("error", ""),
        }
        row.update(d.get("speed", {}))
        row.update(d.get("trajectory", {}))
        row["steering_rmse_deg"] = d.get("steering_rmse_deg", float("nan"))
        row["native_curvature_median"] = d.get("native_curvature_median", float("nan"))
        records.append(row)
    all_runs = pd.DataFrame(records).sort_values("wall_started")
    all_runs.to_csv(OUT / "all_native_runs.csv", index=False)
    latest = all_runs[all_runs.status == "PASS"].drop_duplicates(["session", "label"], keep="last")
    latest.to_csv(OUT / "comparison.csv", index=False)
    charts = ["LON5_Aneg_v50_s1", "LON2_Aneg_s1", "MOVE_LAT2_1_s2", "MOVE_LAT2_2_s1"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, case in zip(axes.flat, charts):
        rows = ordered(latest[latest.session == case])
        if rows.empty:
            continue
        observed = False
        for r in rows.itertuples():
            df = pd.read_csv(Path(r.path) / "speed_comparison.csv")
            if not observed:
                ax.plot(df.relative_s, df.speed_mps * 3.6, "k", lw=2, label="Measured GNSS")
                observed = True
            ax.plot(df.relative_s, df.native_speed_mps * 3.6, label=r.label, color=COLORS.get(r.label), alpha=0.85)
        ax.set(title=case, xlabel="Time from fixed start (s)", ylabel="Speed (km/h)")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("Development replay: identical recorded input, no time shift or state correction")
    fig.tight_layout()
    fig.savefig(OUT / "speed_comparison.png", dpi=170)
    plt.close(fig)
    case = "LON5_Aneg_v50_s1"
    fig, ax = plt.subplots(figsize=(8, 8))
    observed = False
    for r in ordered(latest[latest.session == case]).itertuples():
        p = Path(r.path) / "trajectory_comparison.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        x0, y0 = df.observed_x.iloc[0], df.observed_y.iloc[0]
        if not observed:
            ax.plot(df.observed_x - x0, df.observed_y - y0, "k", lw=2, label="Measured rear axle")
            observed = True
        ax.plot(df.native_x - x0, df.native_y - y0, label=r.label, color=COLORS.get(r.label))
    ax.set(
        xlabel="ENU x relative to initial position (m)",
        ylabel="ENU y relative to initial position (m)",
        title="LON5 development trajectory: initial pose alignment only",
    )
    ax.axis("equal")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "trajectory_comparison.png", dpi=170)
    print(
        latest[
            [c for c in ["session", "label", "rmse_mps", "endpoint_m", "heading_endpoint_deg"] if c in latest]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
