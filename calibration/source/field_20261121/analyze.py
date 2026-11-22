"""Audit captured input boundaries and diagnose steering geometry before fitting native candidates."""

import json

import numpy as np
import pandas as pd
from intake import OUT, ROOT
from scipy.optimize import least_squares


def load(name, channel):
    return pd.read_csv(OUT / "decoded" / ("20261120_" + name) / (channel + ".csv"))


def clean_schema(text):
    return [s for line in text.split("===")[0].splitlines() if (s := line.split("#", 1)[0].strip())]


def audit():
    result = {"schema": {}, "sessions": {}}
    for folder in sorted((OUT / "decoded").iterdir()):
        if not (folder / "snapshots.json").exists():
            continue
        schema = json.loads((folder / "schemas.json").read_text())
        for key in ["ActuatorCommand", "ActuatorStatus", "WheelStatus", "GnssState"]:
            recorded = clean_schema(schema["miru_msgs/msg/" + key]["definition"])
            local = clean_schema((ROOT / "ros_ws/install_bsw_main/share/miru_msgs/msg" / (key + ".msg")).read_text())
            if recorded != local:
                raise ValueError("Schema mismatch " + str(folder) + key)
        result["schema"][folder.name] = "captured fields match installed definitions"
        if not (folder / "commands.csv").exists():
            result["sessions"][folder.name] = {"command_n": 0, "excluded": "no recorded actuator command"}
            continue
        c = pd.read_csv(folder / "commands.csv")
        o = pd.read_csv(folder / "odom.csv")
        g = pd.read_csv(folder / "state.csv")
        active = c[c.acc_pct >= 50]
        result["sessions"][folder.name] = {
            "command_n": len(c),
            "command_duplicate_stamps": int(c.time_s.duplicated().sum()),
            "command_backward": int((c.time_s.diff() < 0).sum()),
            "command_max_gap_s": float(c.time_s.diff().max()),
            "peak_gnss_kph": float(o.speed_mps.max() * 3.6),
            "rtk_fraction": float((g.gnss_fix == 4).mean()),
            "status_valid_fraction": float(g.status_valid.mean()),
            "powered_start": float(active.time_s.min()),
            "powered_end": float(active.time_s.max()),
        }
    (OUT / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def can_check():
    import importlib.util

    spec = importlib.util.spec_from_file_location("prior_intake", ROOT / "analysis/field_20261120/intake.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = module.decode_can(OUT / "raw/20261120_LON5_Aneg_v50_s1/kvaser_ch0.log")
    report = {}
    for key, channel, fields in [
        (0x210, "commands", ["handwheel_deg", "acc_pct", "brake_pct", "flags"]),
        (0x200, "feedback", ["handwheel_deg"]),
        (0x201, "wheels", ["left_kph", "right_kph", "left_rpm", "right_rpm"]),
    ]:
        b = load("LON5_Aneg_v50_s1", channel).sort_values("time_s")
        a = raw[key].sort_values("time_s").rename(columns={"time_s": "can_s"})
        joined = pd.merge_asof(
            b, a, left_on="time_s", right_on="can_s", direction="nearest", tolerance=0.003, suffixes=("_bag", "_can")
        )
        matched = joined[joined.can_s.notna()]
        equal = np.ones(len(matched), dtype=bool)
        for field in fields:
            equal &= abs(matched[field + "_bag"] - matched[field + "_can"]).to_numpy() < 0.0001
        report[channel] = {
            "bag_n": len(b),
            "raw_n": len(a),
            "nearest_within_3ms": len(matched),
            "equal_payload_fraction": float(equal.mean()),
            "equal_payload_time_difference_median_s": float((matched.time_s - matched.can_s)[equal].median()),
            "max_time_difference_s": float(abs(matched.time_s - matched.can_s).max()),
            "max_field_errors": {k: float(abs(matched[k + "_bag"] - matched[k + "_can"]).max()) for k in fields},
        }
        raw[key].to_csv(OUT / (f"lon5_raw_{key:03x}.csv"), index=False, float_format="%.9f")
    (OUT / "can_bag_comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def geometry():
    names = [
        "LAT3_Apos_s1",
        "LAT3_Apos_s2",
        "LAT3_Aneg_s1",
        "LON1_Apos_v8_s1",
        "LAT4_L150_s1",
        "LAT4_R150_s2",
        "LAT4_L120_s1",
        "LAT4_R120_s1",
        "LAT4_L75_s1",
        "LAT4_R75_s1",
        "LAT5_L_s1",
        "LAT5_L_s2",
        "LAT6_L_s1",
    ]
    stats, samples = [], []
    for name in names:
        f, g = load(name, "feedback"), load(name, "state")
        h = np.interp(g.time_s, f.time_s, f.handwheel_deg)
        # Geometric diagnosis uses measured yaw/vx at declared rear axle base_link.
        # This is not rollout state correction or an independent evaluation.
        rate = pd.Series(h).diff(100).abs().fillna(100).to_numpy()
        mask = (g.vx_mps > 1) & (g.gnss_fix == 4) & g.status_valid & (rate < 1.5)
        mask &= (g.time_s >= f.time_s.iloc[0]) & (g.time_s <= f.time_s.iloc[-1])
        k = np.deg2rad(g.yaw_rate_deg_s) / g.vx_mps.clip(lower=0.1)
        points = pd.DataFrame(
            {"session": name, "time_s": g.time_s[mask], "handwheel_deg": h[mask], "curvature": k[mask]}
        )
        # Fixed one-second averages reduce measurement noise without moving time.
        points["bin"] = np.floor(points.time_s - points.time_s.min()).astype(int)
        counts = points.groupby("bin").size()
        points = points.groupby("bin").agg(
            {"session": "first", "time_s": "mean", "handwheel_deg": "mean", "curvature": "mean"}
        )
        points = points.loc[counts >= 50].reset_index(drop=True)
        samples.append(points)
        stats.append(
            {
                "session": name,
                "n_seconds": len(points),
                "handwheel_median": float(points.handwheel_deg.median()),
                "curvature_median": float(points.curvature.median()),
                "radius_abs_m": float(abs(1 / points.curvature.median())),
            }
        )
    pts = pd.concat(samples, ignore_index=True)
    fit_names = ["LAT4_L150_s1", "LAT4_R150_s2", "LAT4_L75_s1", "LAT4_R75_s1"]
    fit = pts[pts.session.isin(fit_names)]

    # Fixed inherited simulator wheelbase/track. Fit effective geometry only.
    def predict(h, offset, ratio):
        angle = np.deg2rad((h - offset) / ratio)
        return np.tan(angle) / (2.36 + 0.725 * np.abs(np.tan(angle)))

    opt = least_squares(
        lambda p: predict(fit.handwheel_deg.to_numpy(), *p) - fit.curvature.to_numpy(),
        [-14.8, 12.6],
        bounds=([-25, 7], [5, 18]),
        loss="soft_l1",
        f_scale=0.003,
    )
    for row in stats:
        s = pts[pts.session == row["session"]]
        row["role"] = "fit" if row["session"] in fit_names else "internal_check"
        for label, p in [("previous", [0, 12.6]), ("candidate", opt.x)]:
            row[label + "_curvature_rmse"] = float(np.sqrt(np.mean((predict(s.handwheel_deg, *p) - s.curvature) ** 2)))
    result = {
        "offset_deg": float(opt.x[0]),
        "ratio": float(opt.x[1]),
        "wheelbase_m": 2.36,
        "track_m": 1.45,
        "scope": "effective low-speed geometry; fixed inherited dimensions; not identified tire mechanics",
        "sessions": stats,
    }
    pts.to_csv(OUT / "geometry_samples.csv", index=False)
    (OUT / "geometry_diagnostic.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    audit()
    print(json.dumps(can_check(), indent=2))
    print(json.dumps(geometry(), indent=2))
