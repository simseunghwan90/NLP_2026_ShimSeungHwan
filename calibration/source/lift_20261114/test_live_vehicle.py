"""Live launch selection and CAN boundary regressions; no Unreal/CAN writes."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulator/scripts"))
sys.path.insert(0, str(ROOT / "ros_ws/src/simulator_bridge"))
from research_vehicle import live_config  # noqa: E402

from simulator_bridge.algorithm.vehicle import Command, Response  # noqa: E402

MODEL = ROOT / "models/candidates/lift_2026-11-14_v7.json"


class LiveVehicleTest(unittest.TestCase):
    def test_live_config_contains_no_replay_or_lift(self):
        config = live_config(MODEL, ROOT / "simulator/local/test")
        self.assertFalse(config["lift"])
        self.assertNotIn("commands", config)
        self.assertEqual(config["pedal_map"], json.loads(MODEL.read_text())["pedal_map"])
        self.assertEqual(len(config["model_sha256"]), 64)

    def test_can_fraction_and_emergency_brake_are_preserved(self):
        response = Response(0.0, 0.0, 7.5, 20.0)
        response.push(1.0, Command(steer_deg=75, brake_pct=20, acc_pct=60, steer_auto=1, brake_auto=1, acc_auto=1))
        controls = response.step(1.0, 0.02)
        self.assertEqual(controls["throttle"], 0.6)
        self.assertEqual(controls["brake"], 0.2)
        self.assertEqual(controls["steering"], -0.5)
        stopped = response.step(2.0, 0.02, stale=True)
        self.assertEqual(stopped["throttle"], 0.0)
        self.assertEqual(stopped["brake"], 1.0)

    def test_duplicate_bridge_pedal_correction_is_rejected(self):
        spec = importlib.util.spec_from_file_location("live_prepare", ROOT / "scripts/prepare.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "results") as tmp:
            response = Path(tmp) / "response.json"
            response.write_text(json.dumps({"additional_delay_s": 0, "additional_tau_s": 0, "drive_pedal_map": {}}))
            with patch.dict(
                os.environ,
                RESEARCH_RESULT_DIR=tmp,
                RESEARCH_VEHICLE_MODEL=str(MODEL),
                RESEARCH_RESPONSE_FILE=str(response),
            ):
                with self.assertRaisesRegex(ValueError, "double mapping"), contextlib.redirect_stdout(io.StringIO()):
                    module.prepare("YonginSLAMFrame", "vcan79", 41615)

    def test_dry_run_selects_live_and_default_stays_default(self):
        command = [sys.executable, str(ROOT / "simulator/scripts/launch.py"), "--dry-run"]
        original = json.loads(subprocess.check_output(command, text=True))
        self.assertIsNone(original["vehicle_model"])
        live = json.loads(subprocess.check_output(command + ["--vehicle-model", str(MODEL)], text=True))
        self.assertEqual(len([s for s in live["command"] if s.startswith("-ResearchVehicle=")]), 1)
        self.assertFalse(any(s.startswith("-ResearchReplay=") for s in live["command"]))


if __name__ == "__main__":
    unittest.main()
