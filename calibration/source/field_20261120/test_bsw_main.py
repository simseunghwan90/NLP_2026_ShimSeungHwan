"""BSW 버전별 상태 단위와 기록된 정차 중 명령 끊김을 대조한다."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "external/A1-Challenge-2026-bsw-main"
OLD = ROOT / "external/A1-Challenge-2026"


def module(path):
    spec = importlib.util.spec_from_file_location("bsw_comparison", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize("brake_fraction", [0, 0.08, 0.6, 1.0])
def test_feedback_units_keep_identical_can_bytes(brake_fraction):
    old = module(OLD / "src/tools/race_day/a1_proto.py")
    new = module(MAIN / "src/tools/race_day/a1_proto.py")
    pin = json.loads((ROOT / "experiments/bsw_main_source.json").read_text())
    counts = [1, 1, 1, 254, 255, 0]
    previous = old.encode_0x200(-12.3, brake_fraction * 10, *counts)
    current = new.encode_0x200(-12.3, brake_fraction * pin["brake_feedback_full_scale"], *counts)
    assert previous == current
    assert new.decode_0x200(current)["brake_pos_pct"] == round(brake_fraction * 100)
    assert new.decode_0x200(current)["steer_pos_deg"] == pytest.approx(-12.3)


def test_recorded_prestart_gap_recovers_only_with_main():
    for root, stopped in [(OLD, True), (MAIN, False)]:
        m = module(root / "src/bsw/safety/can_guard/state_machine.py")
        state = m.next_state(
            m.State.ACTIVE,
            cmd_age_s=0.050694270999883884,
            holding_duration_s=0.0,
            perception_age_s=0.05074750099993253,
            vehicle_speed_kph=0.0,
        )
        assert state == (m.State.STOPPED if stopped else m.State.HOLDING)
        state = m.next_state(state, 0.005, 0.02, 0.005, vehicle_speed_kph=0.0)
        assert state == (m.State.STOPPED if stopped else m.State.ACTIVE)
        assert m.DEFAULT_WATCHDOG_T_S == 0.05
