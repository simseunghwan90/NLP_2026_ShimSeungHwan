from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"experiments/evidence/2026-11-22_r5_stages"
PREVIOUS=ROOT/"experiments/evidence/2026-11-21_trial03_refinement"
PROJECT=ROOT/"simulator/variants/r5_stages_20261122"
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open("x") as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write("\n")
