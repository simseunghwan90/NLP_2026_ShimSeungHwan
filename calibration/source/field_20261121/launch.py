"""Launch only the isolated follow-up project; reuse the established launcher."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "simulator/variants/field_20261121"

if __name__ == "__main__":
    source = ROOT / "analysis/neighbor_steering"
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location("followup_launcher", source / "launch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PROJECT = PROJECT
    module.main()
