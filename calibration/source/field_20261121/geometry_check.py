"""Compare preserved native paths at the same fixed one-second diagnostic samples."""

import json

import numpy as np
import pandas as pd
from intake import OUT


def main():
    samples = pd.read_csv(OUT / "geometry_samples.csv")
    runs = {}
    for path in sorted((OUT / "native_replays").rglob("result.json")):
        result = json.loads(path.read_text())
        if result["status"] == "PASS" and result["label"] in ("previous", "geometry"):
            runs[result["session"], result["label"]] = (path.parent, result)
    records = []
    for name in ("LAT4_L120_s1", "LAT4_R120_s1", "LAT3_Apos_s2"):
        points = samples[samples.session == name]
        # Use identical timestamps for both models; no fitted phase or spatial alignment.
        before = runs[name, "previous"][1]["window"]
        points = points[points.time_s.between(before["start_s"] + 5, before["end_s"] - 1)]
        for label in ("previous", "geometry"):
            folder, result = runs[name, label]
            data = pd.read_csv(folder / "vehicle_telemetry.csv")
            grid = data.t_s.to_numpy() - 3 + result["window"]["start_s"]
            t = points.time_s.to_numpy()
            x = [np.interp(t + delta, grid, data.x_m) for delta in (-0.5, 0, 0.5)]
            y = [np.interp(t + delta, grid, -data.y_m) for delta in (-0.5, 0, 0.5)]
            ax, ay, bx, by = x[1] - x[0], y[1] - y[0], x[2] - x[1], y[2] - y[1]
            length = (np.hypot(ax, ay) + np.hypot(bx, by)) / 2
            if np.any(length < 0.05):
                raise ValueError("Insufficient native displacement for curvature")
            predicted = np.arctan2(ax * by - ay * bx, ax * bx + ay * by) / length
            records.append(
                dict(
                    session=name,
                    label=label,
                    samples=len(points),
                    observed_median_per_m=float(points.curvature.median()),
                    native_median_per_m=float(np.median(predicted)),
                    curvature_rmse_per_m=float(np.sqrt(np.mean((predicted - points.curvature.to_numpy()) ** 2))),
                    basis="native chassis path vs observed rear-axle yaw/vx; geometric development diagnostic",
                )
            )
    pd.DataFrame(records).to_csv(OUT / "native_geometry_check.csv", index=False)
    print(pd.DataFrame(records).to_string(index=False))


if __name__ == "__main__":
    main()
