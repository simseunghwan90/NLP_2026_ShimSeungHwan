"""Read-only archive ingestion and ROS decoding for FIELD-CAL-20261121-01."""

import hashlib
import json
import shutil
import struct
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/evidence/2026-11-21_field_followup"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def schemas(path):
    """Read MCAP summary schema records without loading compressed messages."""
    result = {}
    with path.open("rb") as f:
        f.seek(-37, 2)
        footer = f.read(29)
        if footer[0] != 2:
            raise ValueError("Missing MCAP footer")
        start = struct.unpack_from("<Q", footer, 9)[0]
        if not start:
            raise ValueError("Missing MCAP summary")
        f.seek(start)
        while True:
            head = f.read(9)
            op, size = struct.unpack("<BQ", head)
            data = f.read(size)
            if op == 2:
                break
            if op != 3:
                continue
            pos = 2
            fields = []
            for _ in range(3):
                length = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                fields.append(data[pos : pos + length].decode())
                pos += length
            result[fields[0]] = {"encoding": fields[1], "definition": fields[2]}
    return result


def extract():
    raw = OUT / "raw"
    raw.mkdir(exist_ok=False)
    old = json.loads((ROOT / "experiments/evidence/2026-11-20_field_update/decoded/manifest.json").read_text())
    old_hashes = set(old["source_hashes"].values())
    report = {"archives": {}, "files": {}, "duplicate_members": []}
    for name in ["bsw_test_bags_20261120.zip", "20261120_LON5_Aneg_v50_s1.zip"]:
        archive = ROOT / "data" / name
        report["archives"][name] = {"sha256": digest(archive), "size": archive.stat().st_size}
        with ZipFile(archive) as z:
            for item in z.infolist():
                if item.is_dir():
                    continue
                p = raw / item.filename
                if not p.resolve().is_relative_to(raw.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Unsafe zip member")
                p.parent.mkdir(parents=True, exist_ok=True)
                if p.exists():
                    with z.open(item) as f:
                        h = hashlib.sha256(f.read()).hexdigest()
                    if h != digest(p):
                        raise ValueError("Conflicting duplicate " + item.filename)
                    report["duplicate_members"].append(item.filename)
                    continue
                with z.open(item) as src, p.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
                h = digest(p)
                report["files"][item.filename] = {
                    "sha256": h,
                    "bytes": p.stat().st_size,
                    "identical_previous": h in old_hashes,
                }
    (OUT / "intake_manifest.json").write_text(json.dumps(report, indent=2) + "\n")


def stamp(m):
    return m.header.stamp.sec + m.header.stamp.nanosec * 1e-9


def decode():
    import rosbag2_py
    from nav_msgs.msg import Odometry
    from rclpy.serialization import deserialize_message
    from std_msgs.msg import String

    from miru_msgs.msg import ActuatorCommand, ActuatorStatus, GnssState, WheelStatus

    types = {
        "/vehicle/actuator_command": ActuatorCommand,
        "/vehicle/actuator_status": ActuatorStatus,
        "/vehicle/wheel_status": WheelStatus,
        "/sensor/gnss/state": GnssState,
        "/sensor/gnss/raw/odom": Odometry,
        "/bsw/params_snapshot": String,
    }
    summary = {}
    for session in sorted((OUT / "raw").iterdir()):
        target = OUT / "decoded" / session.name
        target.mkdir(parents=True, exist_ok=False)
        schema = schemas(session / "bag/bag_0.mcap")
        (target / "schemas.json").write_text(json.dumps(schema, indent=2) + "\n")
        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(session / "bag"), storage_id="mcap"), rosbag2_py.ConverterOptions("", "")
        )
        reader.set_filter(rosbag2_py.StorageFilter(topics=list(types)))
        rows = {k: [] for k in ["commands", "feedback", "wheels", "state", "odom"]}
        snapshots, frames = [], set()
        while reader.has_next():
            topic, payload, ns = reader.read_next()
            m = deserialize_message(payload, types[topic])
            if topic == "/bsw/params_snapshot":
                snapshots.append({"received_s": ns * 1e-9, "text": m.data})
                continue
            base = {"time_s": stamp(m), "received_s": ns * 1e-9}
            frames.add((topic, m.header.frame_id))
            if topic == "/vehicle/actuator_command":
                rows["commands"].append(
                    dict(
                        base,
                        handwheel_deg=m.steer_cmd_deg,
                        acc_pct=m.acc_cmd_pct,
                        brake_pct=m.brake_cmd_pct,
                        flags=int(m.steer_auto) + 2 * int(m.brake_auto) + 4 * int(m.acc_auto),
                    )
                )
            elif topic == "/vehicle/actuator_status":
                rows["feedback"].append(
                    dict(
                        base,
                        handwheel_deg=m.steer_position_deg,
                        brake_position_ros=m.brake_position,
                        flags=int(m.steer_auto) + 2 * int(m.brake_auto) + 4 * int(m.acc_auto),
                    )
                )
            elif topic == "/vehicle/wheel_status":
                rows["wheels"].append(
                    dict(
                        base,
                        left_kph=m.left_speed_kph,
                        right_kph=m.right_speed_kph,
                        left_rpm=m.left_rpm,
                        right_rpm=m.right_rpm,
                    )
                )
            elif topic == "/sensor/gnss/state":
                row = dict(base)
                for k in [
                    "x_m",
                    "y_m",
                    "z_m",
                    "qx",
                    "qy",
                    "qz",
                    "qw",
                    "vx_mps",
                    "vy_mps",
                    "vz_mps",
                    "yaw_rate_deg_s",
                    "ax_mps2",
                    "ay_mps2",
                    "az_mps2",
                    "gnss_fix",
                    "ins_alignment",
                    "status_valid",
                    "accel_valid",
                    "heading_rms_deg",
                    "raw_velocity_variance_m2ps2",
                ]:
                    row[k] = getattr(m, k)
                rows["state"].append(row)
            else:
                v, p, q = m.twist.twist.linear, m.pose.pose.position, m.pose.pose.orientation
                rows["odom"].append(
                    dict(
                        base,
                        x_m=p.x,
                        y_m=p.y,
                        z_m=p.z,
                        qx=q.x,
                        qy=q.y,
                        qz=q.z,
                        qw=q.w,
                        vx_mps=v.x,
                        vy_mps=v.y,
                        vz_mps=v.z,
                        speed_mps=float(np.hypot(v.x, v.y)),
                    )
                )
        item = {"frames": sorted(frames), "channels": {}}
        for key, data in rows.items():
            df = pd.DataFrame(data)
            if df.empty:
                item["channels"][key] = {"n": 0}
                continue
            df.to_csv(target / (key + ".csv"), index=False, float_format="%.9f")
            dt = np.diff(df.time_s)
            item["channels"][key] = {
                "n": len(df),
                "start_s": float(df.time_s.iloc[0]),
                "end_s": float(df.time_s.iloc[-1]),
                "nonincreasing": int(np.sum(dt <= 0)),
                "max_gap_s": float(dt.max()),
                "receipt_header_median_s": float((df.received_s - df.time_s).median()),
            }
        odom, state = pd.DataFrame(rows["odom"]), pd.DataFrame(rows["state"])
        item["max_speed_kph"] = float(odom.speed_mps.max() * 3.6) if not odom.empty else None
        item["fix_counts"] = state.gnss_fix.value_counts().to_dict() if not state.empty else {}
        (target / "snapshots.json").write_text(json.dumps(snapshots, indent=2) + "\n")
        summary[session.name] = item
        print(session.name, "peak_kph", round(item["max_speed_kph"] or 0, 2), flush=True)
    (OUT / "bag_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    extract()
    decode()
