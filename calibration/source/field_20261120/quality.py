"""Audit GNSS status and frame consistency separately from fitting."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rosbag2_py
from intake import EVIDENCE, digest
from rclpy.serialization import deserialize_message

from miru_msgs.msg import GnssState


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--message-definition", type=Path, required=True)
    args = p.parse_args()
    expected = "75c330b5e36e816411715c0313b0c0c93e69cd3ce3f23dd8f9daaeaaf1840e13"
    if digest(args.message_definition) != expected:
        raise ValueError("GnssState schema differs from captured commit")
    out = EVIDENCE / "gnss_quality"
    out.mkdir(exist_ok=False)
    report = dict(message_definition_sha256=expected, sessions={})
    for name in ["MOVE_LAT2_1_s2", "LAT3_Apos_s1", "MOVE_LAT2_2_s1", "MOVE_LAT3_Apos_s2"]:
        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(args.raw_root / ("20261120_" + name) / "bag"), storage_id="mcap"),
            rosbag2_py.ConverterOptions("", ""),
        )
        reader.set_filter(rosbag2_py.StorageFilter(topics=["/sensor/gnss/state"]))
        rows = []
        while reader.has_next():
            _, data, received = reader.read_next()
            m = deserialize_message(data, GnssState)
            rows.append(
                [
                    m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                    received * 1e-9,
                    m.vx_mps,
                    m.vy_mps,
                    m.ax_mps2,
                    m.yaw_rate_deg_s,
                    m.gnss_fix,
                    m.ins_alignment,
                    m.accel_valid,
                    m.status_valid,
                    m.heading_rms_deg,
                    m.velocity_uncertainty_valid,
                    m.raw_velocity_variance_m2ps2,
                ]
            )
        f = pd.DataFrame(
            rows,
            columns=[
                "time_s",
                "received_s",
                "vx_mps",
                "vy_mps",
                "ax_mps2",
                "yaw_rate_deg_s",
                "gnss_fix",
                "ins_alignment",
                "accel_valid",
                "status_valid",
                "heading_rms_deg",
                "velocity_uncertainty_valid",
                "raw_velocity_variance_m2ps2",
            ],
        )
        c = pd.read_csv(EVIDENCE / "decoded" / ("20261120_" + name) / "can_210.csv")
        active = c[c.acc_pct > 0].time_s.iloc[0]
        start = max(c.time_s.iloc[0], active - 1)
        f = f[(f.time_s >= start) & (f.time_s <= start + (20 if name == "LAT3_Apos_s1" else 22))]
        f.to_csv(out / (name + ".csv"), index=False)
        report["sessions"][name] = dict(
            n=len(f),
            gnss_fix_counts=f.gnss_fix.value_counts().to_dict(),
            ins_alignment_counts=f.ins_alignment.value_counts().to_dict(),
            status_valid_fraction=float(f.status_valid.mean()),
            velocity_uncertainty_valid_fraction=float(f.velocity_uncertainty_valid.mean()),
            max_speed_sigma_mps=float(np.sqrt(f.raw_velocity_variance_m2ps2.max())),
            max_heading_rms_deg=float(f.heading_rms_deg.max()),
            receipt_minus_header_median_s=float((f.received_s - f.time_s).median()),
        )
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
