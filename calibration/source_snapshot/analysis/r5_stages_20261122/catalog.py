"""Capture native attempts, frozen designs and source hashes without modifying evidence."""
import json
import shutil
from collections import Counter
from pathlib import Path
from common import ROOT,OUT,digest


def main():
    runs=[]
    for f in sorted((OUT/'native_replays').glob('*/result.json')):
        r=json.loads(f.read_text())
        runs.append(dict(label=r['label'],session=r['session'],status=r['status'],path=str(f.relative_to(ROOT)),
                         error=r.get('error'),wall_seconds=r['wall_finished']-r['wall_started'],
                         model_sha256=r['steering_sha256'],drive_sha256=r['drive_sha256'],binary_sha256=r['binary_sha256'],
                         command=r['command'],owned_process_stopped=r['owned_process_stopped']))
    designs=[]
    for f in sorted(OUT.glob('*_design.json')):
        r=json.loads(f.read_text())
        if 'label' in r:
            designs.append(dict(label=r['label'],parent=r.get('parent'),stage=r.get('stage'),hypothesis=r.get('hypothesis'),
                                path=str(f.relative_to(ROOT)),native_attempts=sum(x['label']==r['label'] for x in runs)))
    sources={str(f.relative_to(ROOT)):digest(f) for f in sorted((ROOT/'analysis/r5_stages_20261122').glob('*')) if f.is_file()}
    for project in ['r5_stages_20261122','r5_creep_20261122','r5_creep_viscous_20261122']:
        base=ROOT/'simulator/variants'/project
        for rel in ['Plugins/AirSim/Source/Vehicles/Car/PoweredCreep.h','Plugins/AirSim/Source/Vehicles/Car/ResearchReplay.cpp','Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so']:
            f=base/rel
            if f.exists():sources[str(f.relative_to(ROOT))]=digest(f)
    report=dict(runs=runs,designs=designs,counts_by_label=dict(Counter(r['label'] for r in runs)),
                status_counts=dict(Counter(r['status'] for r in runs)),native_attempts=len(runs),
                native_wall_seconds=sum(r['wall_seconds'] for r in runs),physical_tests=0,source_sha256=sources,
                provenance='PROVENANCE.json and trace_manifest.json record configured model/effort plus visible user directions, commentary and tool calls. Exact server build is not independently verified. Native commands and source snapshots are archived separately.',
                limitations='All exposed development data; not a heldout final evaluation. No additional BSW/MPC integration or real vehicle execution in this experiment.')
    for relative, sha in sources.items():
        # Large native binaries stay pinned in their preserved project; copy editable sources.
        if relative.endswith('.so'):
            continue
        destination=OUT/'source_snapshot'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if digest(destination)!=sha:
                raise RuntimeError('Source snapshot already frozen with a different hash: '+relative)
        else:
            shutil.copy2(ROOT/relative,destination)
    (OUT/'execution_catalog.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['native_attempts','status_counts','native_wall_seconds','physical_tests']},indent=2))

if __name__=='__main__':main()
