"""Check native geometry contract independently of Unreal runtime."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_geometry_inverse_and_legacy(tmp_path):
    source = tmp_path / "check.cpp"
    source.write_text(r"""
#include "SteeringGeometry.h"
#include <cassert>
int main() {
    SteeringGeometry g; g.validate(150);
    for (int i=-1500;i<=1500;++i) {
        const double h=i*.1;
        assert(g.tire(h)==h/12.6);
        assert(std::abs(g.handwheel(g.tire(h))-h)<1e-10);
    }
    g.points={{-150,-11},{-75,-5},{-14,0},{75,8},{150,14}};
    g.validate(150);
    assert(g.tire(-14)==0);
    assert(g.tire(-150)==-11 && g.tire(150)==14);
    for (int i=-1500;i<=1500;++i)
        assert(std::abs(g.handwheel(g.tire(i*.1))-i*.1)<1e-10);
    assert(g.tire_limit(150)==14);
    g.points[2].second=-10;
    bool refused=false;
    try { g.validate(150); } catch (const std::runtime_error&) { refused=true; }
    assert(refused);
}
""")
    include = ROOT / "simulator/variants/r5_stages_20261122/Plugins/AirSim/Source/Vehicles/Car"
    subprocess.run(["g++", "-std=c++14", "-I", str(include), str(source), "-o", str(tmp_path / "check")], check=True)
    subprocess.run([str(tmp_path / "check")], check=True)


def test_can_feedback_preserves_offset_and_rejects_bad_geometry(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "geometry_configuration", ROOT / "analysis/neighbor_steering/configuration.py"
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    model = cfg.load_model(ROOT / "models/candidates/steering_field_2026-11-21_v1.json")
    assert cfg.handwheel_from_inner_tire(model, 0) == pytest.approx(-14.130808976342838)
    assert cfg.handwheel_from_inner_tire(model, model["handwheel_to_inner_tire_deg"][0][1]) == -150
    for h, tire in model["handwheel_to_inner_tire_deg"]:
        assert cfg.handwheel_from_inner_tire(model, tire) == pytest.approx(h)
    model["handwheel_to_inner_tire_deg"][2][1] = -15
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(model))
    with pytest.raises(ValueError, match="Nonmonotone"):
        cfg.load_model(path)


@pytest.mark.parametrize("change", [{"brake_map": [[0, 0], [50, 0.8], [100, 0.5]]}, {"rear_coast_damping_nm_s": -1}])
def test_drive_candidate_rejects_invalid_maps_and_resistance(change):
    spec = importlib.util.spec_from_file_location("followup_drive_validator", ROOT / "analysis/lift_20261114/replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = json.loads((ROOT / "models/candidates/drive_field_2026-11-20_v1.json").read_text())
    model.update(change)
    with pytest.raises(ValueError):
        module.validate_model(model)


def test_drive_only_candidate_cannot_silently_select_an_old_native_project():
    args = [
        "--steering-model",
        str(ROOT / "models/candidates/steering_field_2026-11-21_driveonly03.json"),
        "--output",
        str(ROOT / "simulator/local/neighbor_steering/followup_selection_check"),
        "--map",
        "TestPad",
        "--dry-run",
    ]
    old = subprocess.run(
        [sys.executable, str(ROOT / "analysis/neighbor_steering/launch.py"), *args], capture_output=True, text=True
    )
    assert old.returncode != 0
    assert "does not support this drive model" in old.stderr
    supported = subprocess.check_output(
        [sys.executable, str(ROOT / "analysis/field_20261121/launch.py"), *args], text=True
    )
    selection = json.loads(supported)
    assert selection["drive"]["rear_coast_damping_nm_s"] == 0.6
    assert str(ROOT / "simulator/variants/field_20261121/FSOnline.uproject") in selection["command"]
