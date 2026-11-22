"""Run the existing MPC/BSW session with an explicitly pinned research candidate."""

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--steering", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    sys.path.insert(0, str(ROOT / "analysis/mpc_field"))
    spec = importlib.util.spec_from_file_location("followup_mpc_session", ROOT / "analysis/mpc_field/session.py")
    session = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session)
    from configuration import load_model, project_for_model

    model = load_model(args.steering)
    if "native_project" not in model or "native_binary_sha256" not in model:
        raise ValueError("Probe requires explicit native project and binary hash")
    session.MODEL = args.steering.resolve()
    session.PROJECT = project_for_model(model)
    session.SOCKET = ROOT / "results/field_20261121_mpc_probe.sock"
    sys.argv = [sys.argv[0], *remaining]
    session.main()


if __name__ == "__main__":
    main()
