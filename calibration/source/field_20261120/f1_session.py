"""기존 격리 F1/BSW 세션에 실측 기반 차량 파라미터만 선택한다."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models/candidates/steering_field_2026-11-20_v2.json"


def configured_session():
    folder = ROOT / "analysis/neighbor_steering"
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("field_f1_session", folder / "session.py")
    session = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session)
    steering = session.load_model(MODEL)
    session.STEERING_MODEL = MODEL
    session.MODEL = ROOT / steering["base_longitudinal_model"]
    return session


if __name__ == "__main__":
    session = configured_session()
    print("차량: STEER-FIELD-20261120-v2 + DRIVE-FIELD-20261120-v1", flush=True)
    print("준비 완료 뒤 다른 터미널: bash scripts/f1_field.sh drive", flush=True)
    raise SystemExit(session.main())
