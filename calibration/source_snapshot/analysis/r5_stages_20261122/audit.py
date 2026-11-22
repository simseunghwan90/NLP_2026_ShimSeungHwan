"""Audit coverage, immutable inputs and native evidence before model selection."""
import argparse
import json
from collections import Counter
import pandas as pd
from common import ROOT,OUT,PREVIOUS,PROJECT,digest
from candidate import model_path
from assess import compare

def audit(label):
    manifest=json.loads((OUT/'baseline_manifest.json').read_text());windows=json.loads((OUT/'windows.json').read_text())
    changed=[]
    for category in ['protected_sha256','input_sha256']:
        for name,sha in manifest[category].items():
            if digest(ROOT/name)!=sha:changed.append(dict(category=category,path=name))
    for key,path in [('window_sha256',OUT/'windows.json'),('previous_selection_sha256',PREVIOUS/'selected_model.json')]:
        if digest(path)!=manifest[key]:changed.append(dict(category=key,path=str(path.relative_to(ROOT))))
    model=model_path(label);steering=json.loads(model.read_text());drive=ROOT/steering['base_longitudinal_model']
    assert digest(drive)==steering['base_longitudinal_sha256']
    binary=ROOT/steering['native_project']/'Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so'
    assert digest(binary)==steering['native_binary_sha256']
    rows=[];selected=[];issues=[]
    for path in sorted((OUT/'native_replays').glob('*/result.json')):
        r=json.loads(path.read_text());rows.append(r)
        if r['label']!=label or r['status']!='PASS':continue
        selected.append(r['session'])
        for key,expected in [('status','PASS'),('steering_sha256',digest(model)),('drive_sha256',digest(drive)),('binary_sha256',digest(binary)),('windows_sha256',digest(OUT/'windows.json')),('owned_process_stopped',True)]:
            if r.get(key)!=expected:issues.append(dict(session=r['session'],field=key,actual=r.get(key),expected=expected))
        if r['window']!=windows[r['session']]:issues.append(dict(session=r['session'],field='window'))
        if digest(r['actual_command_source'])!=r['actual_command_sha256']:issues.append(dict(session=r['session'],field='actual_command_sha256'))
        for channel,sha in r['input_sha256'].items():
            path=OUT/'decoded'/('20261120_'+r['session'])/(channel+'.csv')
            if digest(path)!=sha:issues.append(dict(session=r['session'],field='decoded_'+channel))
        map_path=ROOT/r['native_project']/'Content/Maps/TestPad/TestPad.umap'
        if digest(map_path)!=r['map_sha256']:issues.append(dict(session=r['session'],field='map_sha256'))
    assessments=compare(label)
    flags=[dict(session=r['session'],flags=r['references']['R5']['flags']) for r in assessments if r['references']['R5']['flags']]
    missing=sorted(set(windows)-set(selected));duplicates={k:v for k,v in Counter(selected).items() if v>1}
    data=pd.read_csv(OUT/'metrics.csv');coverage=set(data[data.label==label].session)
    if coverage!=set(selected):issues.append(dict(field='metrics_coverage',missing=sorted(set(selected)-coverage),extra=sorted(coverage-set(selected))))
    return dict(label=label,complete_native_count=len(selected),expected_count=len(windows),missing=missing,duplicate_results=duplicates,
                changed_protected_or_inputs=changed,evidence_issues=issues,regression_flags=flags,
                full_regression_pass=not(missing or duplicates or changed or issues or flags),
                selected_steering=str(model.relative_to(ROOT)),selected_steering_sha256=digest(model),
                selected_drive=str(drive.relative_to(ROOT)),selected_drive_sha256=digest(drive),binary_sha256=digest(binary),
                all_native_runs=len(rows),run_counts_by_label=dict(Counter(r['label'] for r in rows)),
                failed_native_runs=[dict(label=r['label'],session=r['session'],error=r.get('error'),wall_started=r['wall_started']) for r in rows if r['status']!='PASS'],
                total_native_wall_seconds=sum(r['wall_finished']-r['wall_started'] for r in rows),
                physical_tests=0,note='Coverage counts completed PASS replays only. Failed attempts remain explicitly listed and cannot satisfy coverage. Regression pass is necessary; stage-specific primary improvements and limitations are reported separately. No heldout final-evaluation claim.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args();report=audit(a.label)
    (OUT/('audit_'+a.label+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
