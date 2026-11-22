"""Run the preserved staged engine in a new evidence directory."""
import argparse
import contextlib
import importlib.util
import json
import sys
from pathlib import Path
from common import ROOT, OUT, digest

sys.path.insert(0, str(ROOT / "analysis/r5_stages_20261122"))
spec = importlib.util.spec_from_file_location("refinement_replay", ROOT / "analysis/r5_stages_20261122/replay.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
engine.OUT = OUT

def main():
    p=argparse.ArgumentParser()
    p.add_argument("label")
    p.add_argument("cases", nargs="+",help="Frozen case names; ALL appends every remaining frozen window")
    p.add_argument("--steering",type=Path,default=ROOT/"models/candidates/steering_r5_stages_2026-11-22_P0.json")
    a=p.parse_args()
    model=json.loads(a.steering.read_text()); drive=ROOT/model["base_longitudinal_model"]
    if digest(drive)!=model["base_longitudinal_sha256"]:
        raise ValueError("Pinned drive changed")
    binary=ROOT/model['native_project']/'Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so'
    if digest(binary)!=model['native_binary_sha256']:raise ValueError('Pinned native binary changed')
    windows=json.loads((OUT/'windows.json').read_text())
    cases=list(dict.fromkeys([n for n in a.cases if n!='ALL']+(list(windows) if 'ALL' in a.cases else [])))
    if not cases or any(n not in windows for n in cases):raise ValueError('Unknown or empty frozen case selection')
    for name in cases:
        preserved=[]
        for f in (OUT/"native_replays").glob("*/result.json"):
            r=json.loads(f.read_text())
            if r["status"]=="PASS" and r["session"]==name and r["label"]==a.label and r["steering_sha256"]==digest(a.steering) and r["drive_sha256"]==digest(drive) and r['binary_sha256']==digest(binary) and r['windows_sha256']==digest(OUT/'windows.json') and r['actual_command_sha256']==digest(r['actual_command_source']):
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
