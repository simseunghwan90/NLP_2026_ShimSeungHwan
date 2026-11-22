"""Fit only the effective pedal-off damping after the high-pedal ablation."""
import argparse
import json
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from common import ROOT,OUT,save
from candidate import make,model_path
from metrics import summarize

def main(parent,label):
    paths=[]
    for path in (OUT/'native_replays').glob('*/result.json'):
        r=json.loads(path.read_text())
        if r['status']=='PASS' and r['label']==parent and r['session']=='LON5_Aneg_v50_s1':paths.append(path)
    assert len(paths)==1, 'Require one completed parent LON5 replay'
    path=paths[0];summarize(path)
    v=pd.read_csv(path.parent/'vehicle_telemetry.csv');q=pd.read_csv(OUT/'comparisons'/(parent+'_LON5_Aneg_v50_s1.csv'))
    resolved=json.loads((path.parent/'vehicle_resolved.json').read_text())
    mass=resolved['mass_kg'];radius=resolved['wheels'][2]['radius_m']
    t=v.t_s.to_numpy()-3
    sensitivity=cumulative_trapezoid(-2*v.speed_mps.to_numpy()/(mass*radius**2)*(v.acc_pct.to_numpy()==0),t,initial=0)
    x=np.interp(q.relative_s,t,sensitivity);e=(q.native_v-q.observed_v).to_numpy()
    mask=q.valid&(q.acc_pct==0)&(q.brake_pct==0)&(q.observed_v>.1)
    assert mask.sum()>100
    delta=float(np.clip(-np.dot(x[mask],e[mask])/np.dot(x[mask],x[mask]),0,.6))
    steering=json.loads(model_path(parent).read_text());drive=json.loads((ROOT/steering['base_longitudinal_model']).read_text())
    report=dict(parent=parent,fit='LON5 pedal-off no-brake moving samples, original full rollout',bounds_delta_nm_s=[0,.6],delta_nm_s=delta,
                reference_rmse=float(np.sqrt(np.mean(e[mask]**2))),surrogate_rmse=float(np.sqrt(np.mean((e[mask]+delta*x[mask])**2))),
                sample_count=int(mask.sum()),mass_kg=mass,radius_m=radius,
                limitation='Integrated force sensitivity proposal; native validation required. Existing damping also applies during service braking when pedal is zero; check brake phases explicitly.')
    save(OUT/(label+'_proposal.json'),report)
    make(label,parent,'6b','Pedal-off deceleration remains weak after drive correction. Change only rear coast damping; retain fixed initial conditions and test low-speed coasts and stopping.',
         drive_patch={'rear_coast_damping_nm_s':drive['rear_coast_damping_nm_s']+delta},extra=report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent');p.add_argument('label');a=p.parse_args();main(a.parent,a.label)
