"""Run inside an isolated UE editor commandlet, never an existing GUI."""

import json
from pathlib import Path

import unreal

project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project.name == "field_20261121"
root = project.parents[2]
report = root / "experiments/evidence/2026-11-21_field_followup/pad_expansion.json"
assert not report.exists()
assert unreal.EditorLevelLibrary.load_level("/Game/Maps/TestPad/TestPad")
matches = [
    a for a in unreal.EditorLevelLibrary.get_all_level_actors() if a.get_actor_label() == "MIRU_FlatTestPad_200m"
]
assert len(matches) == 1
actor = matches[0]
s = actor.get_actor_scale3d()
assert abs(s.x - 200) < 0.001 and abs(s.y - 200) < 0.001 and abs(s.z - 1) < 0.001
p = actor.get_actor_location()
actor.set_actor_scale3d(unreal.Vector(2000, 2000, s.z))
assert unreal.EditorLevelLibrary.save_current_level()
report.write_text(
    json.dumps(
        {
            "before_scale": [s.x, s.y, s.z],
            "after_scale": [2000, 2000, s.z],
            "location_unchanged_cm": [p.x, p.y, p.z],
            "scope": "copied flat pad only; same material and height",
        },
        indent=2,
    )
    + "\n"
)
