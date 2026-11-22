"""Identify actuator response using the exact native kernel; no vehicle-state fit."""
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from common import ROOT, OUT, PROJECT, save, digest

sys.path.insert(0,str(ROOT/'analysis/field_20261120'))
import fit_steering as fit


def load_case(name):
    w=json.loads((OUT/'windows.json').read_text())[name]
    c=pd.read_csv(ROOT/w['command_source'])
    raw=ROOT/'experiments/evidence/2026-11-20_field_update/decoded'/('20261120_'+name)/'can_200.csv'
    f=pd.read_csv(raw if raw.exists() else OUT/'decoded'/('20261120_'+name)/'feedback.csv')
    start,end=w['start_s'],w['end_s'];o=f[f.time_s.between(start,end)]
    grid=np.arange(0,end-start+.01,.01)
    ix=np.searchsorted(c.time_s.to_numpy()-start,grid,side='right')-1
    assert ix.min()>=0
    ot=o.time_s.to_numpy()-start
    transient=np.zeros(len(o),dtype=bool)
    for t in fit.transitions(c)-start:transient|=(ot>=t)&(ot<t+1)
    return dict(grid=grid,u=np.ascontiguousarray(c.handwheel_deg.to_numpy()[ix]),
                initial=float(f[f.time_s<=start].handwheel_deg.iloc[-1]),obs_t=ot,
                y=o.handwheel_deg.to_numpy(),transient=transient,dt=.01,start=start)


def main():
    output=OUT/'stage7_actuator_fit';output.mkdir(exist_ok=False)
    bounds=[(0,.2),(4,25),(.1,2)]
    save(output/'design.json',dict(hypothesis='LAT6 sinusoidal tracking may need different effective actuator dynamics; distinguish from vehicle yaw response.',
         fit='LAT6 first block relative0..198s',check='LAT6 second block continuous state, plus LAT1/SELFCHECK1/2',
         bounds=bounds,seed=20261122,acceptance='10% second-block improvement, stationary added RMSE <=max(10%,0.2deg); native vehicle validation required',
         no_time_alignment=True,rate_limit_deg_s=140))
    fit.HEADER=PROJECT/'Plugins/AirSim/Source/Vehicles/Car/SteeringDynamics.h'
    native,command=fit.build_kernel(output)
    model=json.loads((ROOT/'models/candidates/steering_r5_stages_2026-11-22_P0.json').read_text())
    keys=['effective_delay_s','natural_frequency_rad_s','damping_ratio'];base=[model[k] for k in keys]
    case=load_case('LAT6_L_s1');mask=case['obs_t']<198
    # Run the entire continuous input in every prediction; select only the declared fit block for cost.
    opt=differential_evolution(lambda p:float(np.mean((fit.predict(native,case,p)[mask]-case['y'][mask])**2)),
         bounds,seed=20261122,maxiter=100,popsize=10,tol=1e-7,polish=False)
    params=[float(x) for x in opt.x]
    report=dict(kernel_sha256=digest(fit.HEADER),build_command=command,baseline=dict(zip(keys,base)),candidate=dict(zip(keys,params)),
                nfev=int(opt.nfev),optimizer_success=bool(opt.success),conditions={})
    for tag,m in [('LAT6_fit',mask),('LAT6_check',~mask)]:
        report['conditions'][tag]={l:fit.metrics(case,fit.predict(native,case,p),m) for l,p in [('R5',base),('proposal',params)]}
    for name in ['LAT1_s1','SELFCHECK_s1','SELFCHECK_s2']:
        c=load_case(name)
        report['conditions'][name]={l:fit.metrics(c,fit.predict(native,c,p)) for l,p in [('R5',base),('proposal',params)]}
    checks=report['conditions'];report['primary_pass']=checks['LAT6_check']['proposal']['rmse_deg']<=.9*checks['LAT6_check']['R5']['rmse_deg']
    report['stationary_pass']=all(v['proposal']['rmse_deg']-v['R5']['rmse_deg']<=max(.2,.1*v['R5']['rmse_deg']) for k,v in checks.items() if not k.startswith('LAT6'))
    save(output/'result.json',report)
    pd.DataFrame(dict(relative_s=case['obs_t'],observed=case['y'],R5=fit.predict(native,case,base),proposal=fit.predict(native,case,params),fit=mask)).to_csv(output/'comparison.csv',index=False)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
