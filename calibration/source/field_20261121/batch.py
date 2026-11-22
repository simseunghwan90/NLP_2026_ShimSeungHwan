"""Sequential, owned offscreen comparison; never opens CAN or ROS publishers."""

import argparse

from intake import ROOT
from replay import run

p = argparse.ArgumentParser()
p.add_argument("--cases", nargs="+", required=True)
p.add_argument("--models", nargs="+", default=["previous", "geometry"])
a = p.parse_args()
models = {
    "previous": ROOT / "models/candidates/steering_field_2026-11-20_v2.json",
    "geometry": ROOT / "models/candidates/steering_field_2026-11-21_v1.json",
    "trial01": ROOT / "models/candidates/steering_field_2026-11-21_trial01.json",
    "trial02": ROOT / "models/candidates/steering_field_2026-11-21_trial02.json",
    "trial03": ROOT / "models/candidates/steering_field_2026-11-21_trial03.json",
    "driveonly03": ROOT / "models/candidates/steering_field_2026-11-21_driveonly03.json",
}
results = []
for case in a.cases:
    for name in a.models:
        model = models.get(name, ROOT / name)
        result = run(case, model, label=name)
        results.append(result)
        if result["status"] != "PASS":
            raise RuntimeError("Failed replay; inspect preserved result before proceeding")
