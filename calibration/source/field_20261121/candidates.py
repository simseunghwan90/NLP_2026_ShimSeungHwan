"""Create explicitly versioned development candidates without changing defaults."""

import json

import numpy as np
from intake import OUT, ROOT

if __name__ == "__main__":
    d = json.loads((OUT / "geometry_diagnostic.json").read_text())
    rows = {r["session"]: r for r in d["sessions"]}
    anchors = []
    for name in ["LAT4_R150_s2", "LAT4_R75_s1", "LAT4_L75_s1", "LAT4_L150_s1"]:
        r = rows[name]
        angle = np.sign(r["curvature_median"]) * np.degrees(np.arctan(2.36 / (r["radius_abs_m"] - 0.725)))
        anchors.append([r["handwheel_median"], float(angle)])
    # Extrapolate only the <2deg difference between median feedback and fixed CAN limits.
    first = anchors[0][1] + (-150 - anchors[0][0]) * (anchors[1][1] - anchors[0][1]) / (anchors[1][0] - anchors[0][0])
    last = anchors[-1][1] + (150 - anchors[-1][0]) * (anchors[-1][1] - anchors[-2][1]) / (
        anchors[-1][0] - anchors[-2][0]
    )
    points = [[-150, float(first)], anchors[1], [d["offset_deg"], 0], anchors[2], [150, float(last)]]
    model = json.loads((ROOT / "models/candidates/steering_field_2026-11-20_v2.json").read_text())
    model["model_id"] = "STEER-FIELD-20261121-v1"
    model["handwheel_to_inner_tire_deg"] = points
    model["provenance"] = {
        "experiment": "FIELD-CAL-20261121-01",
        "status": "candidate pending native validation",
        "source": "LAT4 L/R150 and L/R75 measured feedback and rear axle yaw/vx; effective geometry",
        "zero": "Joint linear diagnostic on the same four fit sessions; not the field tool offset copied into commands",
        "inherited": "Actuator dynamics, CAN limits, drive model and dimensions retained",
        "report": "experiments/evidence/2026-11-21_field_followup/REPORT.md",
    }
    path = ROOT / "models/candidates/steering_field_2026-11-21_v1.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(model, indent=2) + "\n")
    print(points)
