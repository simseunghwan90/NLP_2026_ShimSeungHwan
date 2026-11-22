"""Decode recorded CAN and standard ROS odometry; never opens a CAN socket."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "experiments/evidence/2026-11-20_field_update"
ARCHIVE_SHA = "67097a4372d54a49dfe0a630b33aee74ac2b296a7deac5f5827c73806a07db33"
LINE = re.compile(r"\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]+)")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def decode_can(path):
    rows = {0x210: [], 0x200: [], 0x201: []}
    for line in Path(path).read_text().splitlines():
        match = LINE.fullmatch(line.strip())
        if not match:
            continue
        stamp, can_id, payload = match.groups()
        can_id = int(can_id, 16)
        if can_id not in rows:
            continue
        b = bytes.fromhex(payload)
        if len(b) != 8:
            raise ValueError("Unexpected CAN payload size")
        t = float(stamp)
        if rows[can_id] and t <= rows[can_id][-1][0]:
            raise ValueError("CAN timestamps not strictly increasing")
        if can_id == 0x210:
            row = [
                t,
                int.from_bytes(b[:2], "little", signed=True) / 10,
                int.from_bytes(b[2:4], "little"),
                b[4],
                b[5] & 7,
            ]
        elif can_id == 0x200:
            row = [
                t,
                int.from_bytes(b[:2], "little", signed=True) / 10,
                int.from_bytes(b[2:4], "little", signed=True),
                b[4] & 7,
            ]
        else:
            right, left = int.from_bytes(b[:3], "little"), int.from_bytes(b[3:6], "little")
            row = [t, (right & 4095) / 10, right >> 12, (left & 4095) / 10, left >> 12]
        rows[can_id].append(row)
    columns = {
        0x210: ["time_s", "handwheel_deg", "brake_pct", "acc_pct", "flags"],
        0x200: ["time_s", "handwheel_deg", "brake_position_pct", "flags"],
        0x201: ["time_s", "right_kph", "right_rpm", "left_kph", "left_rpm"],
    }
    return {key: pd.DataFrame(value, columns=columns[key]) for key, value in rows.items()}


def decode_odom(bag):
    import rosbag2_py
    from nav_msgs.msg import Odometry
    from rclpy.serialization import deserialize_message

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/sensor/gnss/raw/odom"]))
    rows, frames = [], set()
    while reader.has_next():
        _, data, received_ns = reader.read_next()
        m = deserialize_message(data, Odometry)
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        v, p = m.twist.twist.linear, m.pose.pose.position
        frames.add((m.header.frame_id, m.child_frame_id))
        rows.append([t, received_ns * 1e-9, v.x, v.y, v.z, np.hypot(v.x, v.y), p.x, p.y, p.z])
    f = pd.DataFrame(
        rows, columns=["time_s", "received_s", "vx_mps", "vy_mps", "vz_mps", "speed_mps", "x_m", "y_m", "z_m"]
    )
    if len(f) < 2 or (np.diff(f.time_s) <= 0).any() or not np.isfinite(f.to_numpy()).all():
        raise ValueError("Invalid odometry data")
    return f, sorted(frames)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, default=ROOT / "upload_20261120_1543.tar.gz")
    p.add_argument("--raw-root", type=Path, required=True, help="Previously safely extracted archive")
    p.add_argument("--output", type=Path, default=EVIDENCE / "decoded")
    a = p.parse_args()
    if digest(a.archive) != ARCHIVE_SHA:
        raise ValueError("Wrong source archive")
    a.output.mkdir(parents=True, exist_ok=False)
    # Verify every extracted file against the original archive before using it.
    source_hashes = {}
    with tarfile.open(a.archive, "r:gz") as tar:
        for member in tar:
            target = (a.raw_root / member.name).resolve()
            if not target.is_relative_to(a.raw_root.resolve()) or member.issym() or member.islnk():
                raise ValueError("Unsafe archive path")
            if member.isfile():
                h = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                if digest(target) != h:
                    raise ValueError("Extracted data differs: " + member.name)
                source_hashes[member.name] = h
    manifest = dict(archive_sha256=ARCHIVE_SHA, source_hashes=source_hashes, sessions={})
    for session in sorted(a.raw_root.glob("20261120_*")):
        if not (session / "kvaser_ch0.log").exists():
            manifest["sessions"][session.name] = {"recorded": False}
            continue
        output = a.output / session.name
        output.mkdir()
        can = decode_can(session / "kvaser_ch0.log")
        odom, frames = decode_odom(session / "bag")
        for key, f in can.items():
            f.to_csv(output / f"can_{key:03x}.csv", index=False, float_format="%.9f")
        odom.to_csv(output / "odom.csv", index=False, float_format="%.9f")
        manifest["sessions"][session.name] = dict(
            recorded=True,
            can_counts={f"{k:03x}": len(v) for k, v in can.items()},
            odom_count=len(odom),
            frames=frames,
            max_gnss_speed_mps=float(odom.speed_mps.max()),
            commands_auto_flags=sorted(map(int, can[0x210]["flags"].unique())),
            can_clock="original python-can message.timestamp; not mirror receive time",
            odom_clock="raw Odometry header stamp; synchronization uncertainty uncorrected",
        )
    (a.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["sessions"], indent=2))


if __name__ == "__main__":
    main()
