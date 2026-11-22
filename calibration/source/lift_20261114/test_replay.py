"""Guard units, time direction and physical parameter validity before native runs."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

import numpy as np

from replay import DBC, EVIDENCE, ROOT, read_can, validate_case, validate_model


class ReplayTests(unittest.TestCase):
    def test_fixed_wire_examples(self):
        text = "(1.0) vcan0 210#ECFF08003C060000\n(1.1) vcan0 201#C8214D1593920000\n(1.2) vcan0 200#0000080006000000\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "can.log"
            p.write_text(text)
            bus = read_can(p)
        np.testing.assert_allclose(bus[0x210][0], [1, 60, 8, -2, 6])
        np.testing.assert_allclose(bus[0x201][0], [1.1, 2345, 1234, 78.9, 45.6])
        self.assertEqual(bus[0x200][0, 1], 8)  # New DBC: 8%, not 0.8%.

    def test_definition_is_signal_specific(self):
        dbc = DBC.read_bytes().decode("cp949")
        definitions = {}
        ident = None
        for line in dbc.splitlines():
            if m := re.match(r"BO_ (\d+) ", line):
                ident = int(m[1])
            if m := re.match(r"\s*SG_ (\w+) : (\d+)\|(\d+)@1([+-]) \(([^,]+),([^)]*)\)", line):
                definitions[ident, m[1]] = (int(m[2]), int(m[3]), m[4], float(m[5]), float(m[6]))
        expected = {
            (528, "steer_command"): (0, 16, "-", .1, 0),
            (528, "break_command"): (16, 16, "+", 1, 0),
            (528, "acc_command"): (32, 8, "+", 1, 0),
            (513, "left_rpm"): (36, 12, "+", 1, 0),
            (513, "right_rpm"): (12, 12, "+", 1, 0),
            (512, "break_postion"): (16, 16, "-", 1, 0),
        }
        for key, value in expected.items():
            self.assertEqual(definitions[key], value)

    def test_nonmonotone_log_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "can.log"
            p.write_text("(2) vcan0 210#0000000000060000\n(1) vcan0 210#0000000000060000\n")
            with self.assertRaisesRegex(ValueError, "Nonmonotonic"):
                read_can(p)

    def test_all_prepared_inputs_and_models(self):
        for path in (EVIDENCE / "inputs").glob("*.json"):
            if path.name != "manifest.json":
                validate_case(json.loads(path.read_text()))
        for path in (ROOT / "models/candidates").glob("lift_*.json"):
            validate_model(json.loads(path.read_text()))

    def test_invalid_physics_rejected(self):
        cases = [{"motor_moi_kg_m2": 0}, {"motor_max_rpm": 0},
                 {"rear_residual_torque_nm": float("nan")}, {"torque_curve": [1, 2]},
                 {"pedal_map": [[0, 0], [80, .7], [100, .6]]},
                 {"pedal_map": [[0, 0], [100, 1.1]]}, {"unknown": 3},
                 {"low_speed_substeps": 0}, {"low_speed_substeps": 1.5}]
        for model in cases:
            with self.subTest(model=model), self.assertRaises(ValueError):
                validate_model(model)

    def test_invalid_input_units_and_time_rejected(self):
        base = {"lift": True, "duration_s": 3, "commands": [[0, 0, 0, 0, 6], [1, 60, 0, 0, 6]]}
        for col, value in [(0, -1), (0, 4), (1, 101), (2, -1), (3, 151), (4, 6.2)]:
            c = copy.deepcopy(base)
            c["commands"][1][col] = value
            with self.subTest(col=col, value=value), self.assertRaises(ValueError):
                validate_case(c)


if __name__ == "__main__":
    unittest.main()
