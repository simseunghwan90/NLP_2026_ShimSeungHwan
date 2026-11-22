"""Regression checks for recorded-command boundaries and the native fitting plant."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fit_steering import NEW, build_kernel, predict, transitions
from intake import EVIDENCE, ROOT, decode_can, digest


def test_final_dbc_signed_angle_and_packed_wheels(tmp_path):
    # Asymmetric, nonzero high bits catch swapped wheel fields and signedness.
    right = (1234 << 12) | 123
    left = (2345 << 12) | 234
    payload = right.to_bytes(3, "little") + left.to_bytes(3, "little") + b"\x00\x00"
    log = tmp_path / "can.log"
    log.write_text(
        "(1.000000) kv0 210#85ff1e0050070000\n"
        "(1.001000) kv0 200#85ff080007000000\n"
        f"(1.002000) kv0 201#{payload.hex()}\n"
    )
    frames = decode_can(log)
    assert frames[0x210].iloc[0].tolist() == [1, -12.3, 30, 80, 7]
    assert frames[0x200].iloc[0].tolist() == [1.001, -12.3, 8, 7]
    assert frames[0x201].iloc[0].tolist() == [1.002, 12.3, 1234, 23.4, 2345]
    assert (
        digest(EVIDENCE / "preflight/A1_dbc_2_fixed.dbc")
        == "21a047607060ddf34be596767067ec04277857e6c1dbc0dc075fac4620a3fcaf"
    )


def test_time_reversal_rejected(tmp_path):
    log = tmp_path / "can.log"
    log.write_text("(2.000000) kv0 210#0000000000070000\n(1.000000) kv0 210#0000000000070000\n")
    with pytest.raises(ValueError, match="timestamps"):
        decode_can(log)


def test_constant_steering_has_no_transient():
    commands = pd.DataFrame(dict(time_s=[0, 0.02, 0.04], handwheel_deg=[-14.5] * 3))
    assert transitions(commands).size == 0


def test_native_prediction_is_causal_and_does_not_use_observed_state(tmp_path):
    native, _ = build_kernel(tmp_path)
    t = np.arange(0, 2, 0.01)
    u = np.where(t < 1, 0.0, 20.0)
    case = dict(u=u, dt=0.01, initial=0.0, grid=t, obs_t=t, y=np.zeros(len(t)))
    first = predict(native, case, [0.1, 8, 0.6])
    case["y"][:] = 1000
    second = predict(native, case, [0.1, 8, 0.6])
    np.testing.assert_array_equal(first, second)
    assert np.max(abs(first[t <= 1.1])) < 1e-8
    assert first[-1] > 15


def test_new_candidate_retains_physical_limits_and_separate_delay(tmp_path):
    native, _ = build_kernel(tmp_path)
    m = json.loads(NEW.read_text())
    t = np.arange(0, 12, 0.01)
    u = np.where(t < 1, 0.0, np.where(t < 5, 150.0, -150.0))
    case = dict(u=u, dt=0.01, initial=0.0, grid=t, obs_t=t)
    y = predict(native, case, [m[k] for k in ["effective_delay_s", "natural_frequency_rad_s", "damping_ratio"]])
    assert np.max(abs(y)) <= 150
    assert np.max(abs(np.diff(y))) <= 140 * 0.01 + 1e-8
    assert abs(y[-1] + 150) < 0.1
    response = json.loads((ROOT / "models/response.json").read_text())
    assert all(v == 0 for k, v in response.items() if "delay" in k or "tau" in k)


def test_current_and_previous_launch_select_complete_matching_models():
    base = [
        sys.executable,
        str(ROOT / "analysis/neighbor_steering/launch.py"),
        "--map",
        "TestPad",
        "--output",
        str(ROOT / "simulator/local/neighbor_steering/selection_unit_check"),
        "--dry-run",
    ]
    for extra, steering_id, drive_id in [
        ([], "STEER-FIELD-20261120-v2", "DRIVE-FIELD-20261120-v1"),
        (
            ["--steering-model", str(ROOT / "models/candidates/steering_neighbor_2026-11-17_v1.json")],
            "STEER-NEIGHBOR-20261117-v1",
            "LIFT-CAL-20261114-v7",
        ),
    ]:
        config = json.loads(subprocess.check_output(base + extra, text=True))
        assert config["steering"]["model_id"] == steering_id
        assert config["drive"]["model_id"] == drive_id
        for kind in ["steering", "drive"]:
            assert digest(config[kind]["model_source"]) == config[kind]["model_sha256"]
