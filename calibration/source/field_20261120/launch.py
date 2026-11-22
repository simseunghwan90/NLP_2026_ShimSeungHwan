"""Launch the separately copied field candidate; leave the user's project alone."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "simulator/variants/field_20261120"
MODEL = ROOT / "models/candidates/steering_field_2026-11-20_v2.json"


def main():
    if not (PROJECT / "FSOnline.uproject").is_file():
        raise RuntimeError("Field project missing; follow analysis/field_20261120/README.md")
    # Reuse the tested launcher, validators and native configuration boundary.
    source = ROOT / "analysis/neighbor_steering"
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location("field_unreal_launch", source / "launch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PROJECT = PROJECT
    module.MODEL = MODEL
    module.main()


if __name__ == "__main__":
    main()
