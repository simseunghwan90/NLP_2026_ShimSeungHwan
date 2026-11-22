"""Read-only retrospective audit. Never imports or executes vehicle tools.

Run with the temporary environment recorded in the review README.
Bus timestamps are receive timestamps; no alignment or latency correction is fitted.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/a1-lift-matplotlib")
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mcap.reader import make_reader
from rosbags.typesys import Stores, get_types_from_msg, get_typestore

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/2026-11-14_lift/20261114"
OUT = ROOT / "experiments/evidence/2026-11-14_lift_review"
OUT.mkdir(exist_ok=True, parents=True)


def local(t):
    return datetime.fromtimestamp(t, ZoneInfo("Asia/Seoul")).isoformat()


def read_can(path):
    rows = {i: [] for i in (0x200, 0x201, 0x202, 0x203, 0x210)}
    counts = Counter()
    for line in path.open():
        p = line.split()
        if len(p) < 3 or "#" not in p[2]:
            continue
        cid, payload = p[2].split("#", 1)
        cid = int(cid, 16)
        counts[f"0x{cid:x}"] += 1
        if cid not in rows:
            continue
        d = bytes.fromhex(payload)
        t = float(p[0].strip("()"))
        if cid == 0x201:
            r, l = int.from_bytes(d[:3], "little"), int.from_bytes(d[3:6], "little")
            value = [t, (r & 4095) / 10, r >> 12, (l & 4095) / 10, l >> 12]
        elif cid == 0x200:
            value = [t, int.from_bytes(d[2:4], "little", signed=True)]
        elif cid == 0x210:
            value = [t, d[4], int.from_bytes(d[2:4], "little"), d[5] & 7]
        else:
            value = [t, (int.from_bytes(d[:2], "little") & 1023) / 10]
        rows[cid].append(value)
    return {k: np.asarray(v, dtype=float) for k, v in rows.items()}, counts


def previous(a, times, column):
    if not len(a):
        return np.full(len(times), np.nan)
    assert np.all(np.diff(a[:, 0]) >= 0)
    idx = np.searchsorted(a[:, 0], times, side="right") - 1
    return np.where(idx >= 0, a[np.maximum(idx, 0), column], np.nan)


def slope(frame, col):
    return float(np.polyfit(frame.wall_s - frame.wall_s.iloc[0], frame[col], 1)[0])


def main():
    evidence = {"sessions": [], "ramps": [], "steps": [], "brake_plateaus": [], "bags": []}
    plotted = {}
    for session in sorted(BASE.glob("lift_acc_deadzone_*")):
        if not (session / "candump_kv0.log").exists():
            evidence["sessions"].append({"session": session.name, "status": "no candump_kv0.log"})
            continue
        bus, counts = read_can(session / "candump_kv0.log")
        reversals = {f"0x{k:x}": int(np.sum(np.diff(v[:, 0]) < 0)) for k,v in bus.items() if len(v)}
        bus = {k: v[np.argsort(v[:, 0], kind="stable")] if len(v) else v for k,v in bus.items()}
        w, c = bus[0x201], bus[0x210]
        info = {"session": session.name, "counts": dict(counts),
                "timestamp_reversals_in_file": reversals,
                "wheel_interval_median_s": float(np.median(np.diff(w[:, 0]))),
                "wheel_interval_max_s": float(np.max(np.diff(w[:, 0]))),
                "wheel_start_kst": local(w[0, 0]), "wheel_end_kst": local(w[-1, 0]),
                "speed_limit_values": sorted(set(bus[0x202][:, 1])),
                "limit_write": bus[0x203].tolist()}
        if len(bus[0x203]):
            t = bus[0x203][0, 0]
            changed = bus[0x202][(bus[0x202][:, 0] >= t) & (bus[0x202][:, 1] == 100)]
            info["limit_feedback_receive_delta_s"] = float(changed[0, 0] - t) if len(changed) else None
        evidence["sessions"].append(info)
        for cmdpath in sorted(session.glob("*_cmd.csv")):
            cmd = pd.read_csv(cmdpath, low_memory=False)
            run = cmd[cmd.phase == "run"]
            if run.empty:
                continue
            start, end = float(run.wall_s.iloc[0]), float(run.wall_s.iloc[-1])
            subset = w[(w[:, 0] >= start) & (w[:, 0] <= end)]
            df = pd.DataFrame(subset, columns=["wall_s", "right_kph", "right_rpm", "left_kph", "left_rpm"])
            df["t_s"] = df.wall_s - start
            df["mean_kph"] = (df.right_kph + df.left_kph) / 2
            df["mean_rpm"] = (df.right_rpm + df.left_rpm) / 2
            df["bus_acc_pct"] = previous(c, df.wall_s, 1)
            df["bus_brake_pct"] = previous(c, df.wall_s, 2)
            df["bus_command_age_s"] = df.wall_s - previous(c, df.wall_s, 0)
            df["brake_position_pct"] = previous(bus[0x200], df.wall_s, 1)
            ca = cmd[["wall_s", "acc_cmd_pct", "tx210_acc_pct"]].to_numpy(float)
            df["requested_acc_pct"] = previous(ca, df.wall_s, 1)
            name = cmdpath.stem.replace("20261114_", "").replace("_cmd", "")
            (OUT / "bus_aligned").mkdir(exist_ok=True)
            df.to_csv(OUT / "bus_aligned" / (name + ".csv"), index=False)
            plotted[name] = df
            if "run8" in name:
                record = {"run": name}
                for threshold in (0.0, 1.0):
                    # >0 and >=1 match explicitly different onset definitions.
                    moving = df[(df.mean_kph > threshold if threshold == 0 else df.mean_kph >= threshold)
                                & (df.bus_acc_pct >= 50) & (df.bus_brake_pct == 0)]
                    first = moving.iloc[0]
                    record[str(threshold)] = {k: float(first[k]) for k in ["t_s", "mean_kph", "requested_acc_pct", "bus_acc_pct", "bus_command_age_s"]}
                evidence["ramps"].append(record)
            if "run9" in name:
                acc = float(run.acc_cmd_pct.max())
                active = df[(df.bus_acc_pct == acc) & (df.bus_brake_pct == 0)]
                fit = active[(active.mean_kph >= 15) & (active.mean_kph <= 75)]
                # This is a descriptive slope over a stated speed interval, not a torque model.
                record = {"run": name, "acc_pct": acc,
                          "one_wheel_zero_other_above_10kph_samples": int(((active.right_kph.eq(0) & active.left_kph.gt(10)) | (active.left_kph.eq(0) & active.right_kph.gt(10))).sum()),
                          "ols_15_75_kph_per_s": slope(fit, "mean_kph"),
                          "ols_15_75_rpm_per_s": slope(fit, "mean_rpm"),
                          "active_duration_s": float(active.wall_s.iloc[-1] - active.wall_s.iloc[0])}
                co = df[(df.wall_s > active.wall_s.iloc[-1]) & (df.bus_acc_pct == 0)
                        & (df.bus_brake_pct == 0) & (df.mean_kph >= 8) & (df.mean_kph <= 75)]
                if len(co) > 10:
                    record.update(coast_ols_rpm_per_s=slope(co, "mean_rpm"),
                                  coast_ols_mps2_equivalent=slope(co, "mean_kph") / 3.6,
                                  coast_brake_positions=sorted(set(co.brake_position_pct)))
                evidence["steps"].append(record)
            if "run10" in name:
                # Drop first 1 s of each plateau, including the first plateau in the run.
                group = df.bus_brake_pct.ne(df.bus_brake_pct.shift()).cumsum()
                for _, seg in df.groupby(group):
                    stable = seg[seg.wall_s >= seg.wall_s.iloc[0] + 1.0]
                    if stable.empty:
                        continue
                    evidence["brake_plateaus"].append({"command_pct": float(stable.bus_brake_pct.iloc[0]),
                        "feedback_min": float(stable.brake_position_pct.min()),
                        "feedback_median": float(stable.brake_position_pct.median()),
                        "feedback_max": float(stable.brake_position_pct.max()), "n": len(stable)})

    for bag in sorted(BASE.rglob("*.mcap")):
        counts = Counter(); ranges = {}; schemas = {}
        store = get_typestore(Stores.ROS2_HUMBLE)
        decoded = {}; can_ids = Counter()
        with bag.open("rb") as f:
            reader = make_reader(f, validate_crcs=True)
            for schema, channel, msg in reader.iter_messages(log_time_order=False):
                counts[channel.topic] += 1
                r = ranges.setdefault(channel.topic, [msg.log_time, msg.log_time])
                r[0], r[1] = min(r[0], msg.log_time), max(r[1], msg.log_time)
                if schema:
                    schemas[schema.name] = schema.data.decode(errors="replace")
                if channel.topic in ("/vehicle/wheel_status", "/vehicle/actuator_status", "/vehicle/can/rx"):
                    if schema.name not in store.types:
                        store.register(get_types_from_msg(schema.data.decode(), schema.name))
                    obj = store.deserialize_cdr(msg.data, schema.name)
                    hdr = obj.header.stamp.sec * 10**9 + obj.header.stamp.nanosec
                    row = [hdr, (msg.log_time - hdr) / 1e6]
                    if channel.topic == "/vehicle/wheel_status":
                        row += [obj.right_rpm, obj.left_rpm]
                    elif channel.topic == "/vehicle/actuator_status":
                        row += [obj.brake_position]  # Embedded schema: CAN percent divided by 10.
                    else:
                        can_ids[f"0x{obj.id:x}"] += 1
                    decoded.setdefault(channel.topic, []).append(row)
        meta = yaml.safe_load((bag.parent / "metadata.yaml").read_text())["rosbag2_bagfile_information"]
        expected = {x["topic_metadata"]["name"]: x["message_count"] for x in meta["topics_with_message_count"]}
        info = {"path": str(bag.relative_to(BASE)), "message_counts": dict(counts),
                "metadata_counts_match": all(counts[k] == v for k, v in expected.items()) and sum(counts.values()) == meta["message_count"],
                "range_kst": {k: [local(x/1e9) for x in v] for k,v in ranges.items()},
                "crc_read_completed": True}
        info["raw_can_ids"] = dict(can_ids)
        info["decoded"] = {}
        for topic, rows in decoded.items():
            a = np.asarray(rows, dtype=float)
            info["decoded"][topic] = {"header_reversals": int(np.sum(np.diff(a[:,0]) < 0)),
                "receipt_minus_header_ms_min_median_max": np.quantile(a[:,1], [0,.5,1]).tolist(),
                "payload_min": a[:,2:].min(axis=0).tolist(), "payload_max": a[:,2:].max(axis=0).tolist()}
        evidence["bags"].append(info)
        schemaout = OUT / "bag_schemas" / bag.parent.parent.name
        schemaout.mkdir(parents=True, exist_ok=True)
        for name, definition in schemas.items():
            (schemaout / (name.replace("/", "_") + ".msg")).write_text(definition)

    original = OUT / "imported_report/data"
    reproduced = OUT / "reproduced_report/data"
    evidence["provided_csv_reproduction"] = {p.name: pd.read_csv(p).equals(pd.read_csv(reproduced/p.name)) for p in original.glob("*.csv")}
    (OUT / "audit.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for name, df in plotted.items():
        if "run8" in name:
            part = df[(df.bus_acc_pct >= 50) & (df.bus_brake_pct == 0) & (df.requested_acc_pct >= 50)]
            axes[0, 0].plot(part.requested_acc_pct, part.mean_rpm, label=name[-2:])
        if "run9" in name:
            axes[0, 1].plot(df.t_s, df.mean_rpm, label=f"{int(df.bus_acc_pct.max())}%")
            if name[-1] != "1":
                co = df[(df.bus_acc_pct == 0) & (df.bus_brake_pct == 0) & (df.mean_kph > 8)
                        & (df.t_s > df.loc[df.bus_acc_pct > 0, 't_s'].max())]
                axes[1, 0].plot(co.t_s - co.t_s.iloc[0], co.mean_rpm, label=name[-2:])
        if "run10" in name:
            axes[1, 1].step(df.t_s, df.bus_brake_pct, where="post", label="CAN command")
            axes[1, 1].plot(df.t_s, df.brake_position_pct, label="CAN position")
    for ax, title, xlabel, ylabel in zip(axes.flat,
            ["Ramp: requested input vs wheel response", "Step trials: lifted wheels", "Coast: D, zero accelerator/brake command", "Stationary brake staircase"],
            ["Requested accelerator [%]", "Run time [s]", "Time from selected coast segment [s]", "Run time [s]"],
            ["Mean wheel RPM", "Mean wheel RPM", "Mean wheel RPM", "Command / reported position [%]"]):
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel); ax.grid(alpha=.25); ax.legend()
    fig.suptitle("2026-11-14 Stage I pilot — received CAN observations; no simulator comparison")
    fig.tight_layout()
    fig.savefig(OUT / "stage1_observations.png", dpi=180)
    fig.savefig(OUT / "stage1_observations.pdf")
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['sessions','bags']}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
