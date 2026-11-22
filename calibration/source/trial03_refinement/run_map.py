"""Run the preserved staged engine in a new evidence directory."""
import argparse
import contextlib
import importlib.util
import json
import sys
from pathlib import Path
from setup import ROOT, OUT, digest

sys.path.insert(0, str(ROOT / "analysis/staged_20261121"))
spec = importlib.util.spec_from_file_location("refinement_replay", ROOT / "analysis/trial03_refinement/replay_map.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
engine.OUT = OUT

def main():
    p=argparse.ArgumentParser()
    p.add_argument("label")
    p.add_argument("cases", nargs="+")
    p.add_argument("--steering",type=Path,default=ROOT/"models/candidates/steering_field_2026-11-21_trial03.json")
    a=p.parse_args()
    model=json.loads(a.steering.read_text()); drive=ROOT/model["base_longitudinal_model"]
    if digest(drive)!=model["base_longitudinal_sha256"]:
        raise ValueError("Pinned drive changed")
    for name in a.cases:
        preserved=[]
        for f in (OUT/"native_replays").glob("*/result.json"):
            r=json.loads(f.read_text())
            if r["status"]=="PASS" and r["session"]==name and r["label"]==a.label and r["steering_sha256"]==digest(a.steering) and r["drive_sha256"]==digest(drive):
                preserved.append(f)
        if preserved:
            print("PRESERVED",name,preserved[-1],flush=True);continue
        with (OUT/("batch_"+a.label+"_"+name+".log")).open("a") as log, contextlib.redirect_stdout(log):
            result=engine.run(name,a.steering,drive,a.label)
        folder=Path(result["command"][result["command"].index("--replay")+1]).parent
        (folder/"adapter_source.py").write_bytes(Path(__file__).read_bytes())
        print(result["status"],name,result.get("speed"),result.get("trajectory"),result.get("error",""),flush=True)
        if result["status"]!="PASS":raise RuntimeError("Stopped after native failure: "+name)

if __name__=="__main__":main()
