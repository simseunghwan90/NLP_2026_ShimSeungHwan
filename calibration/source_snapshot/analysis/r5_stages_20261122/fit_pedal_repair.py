"""Repair the conflicting 85/90/95% range using four controlled LON windows."""
import json
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.optimize import minimize
from common import ROOT,OUT,save
from candidate import make
from metrics import summarize

def main():
    names=['LON2_Aneg_s1','LONK_Aneg_v30_s1','LONK_Apos_v20_s1','LONK_Apos_v30_s1']
    sets={};drive=json.loads((ROOT/'models/candidates/drive_r5_stages_2026-11-22_S6DRIVE.json').read_text())
    curve=np.array(drive['torque_curve']);knots=np.array([83,85,90,95,100])
    save(OUT/'pedal_repair_fit_design.json',dict(reason='S6DRIVE retains a LONK30 Aneg speed regression; smaller90% correction and a later95% correction may retain LON2 benefit without overspeed.',
        cases=names,fit_groups='Controlled LON only; no circles/MOVE in objective',bounds_delta=[[-.005,.005],[-.015,0],[0,.018]],
        primary='Retain >=10% LON2 powered improvement; constrain LONK30Aneg and20 powered errors using R5 reference',
        method='Local native force sensitivity; candidate still requires complete native replay',fixed='<=83%,100%,torque,braking,coast,steering,body'))
    for name in names:
        paths=[p for p in (OUT/'native_replays').glob('*/result.json') if (lambda r:r['status']=='PASS' and r['label']=='S6DRIVE' and r['session']==name)(json.loads(p.read_text()))]
        assert len(paths)==1;summarize(paths[0]);v=pd.read_csv(paths[0].parent/'vehicle_telemetry.csv');q=pd.read_csv(OUT/'comparisons'/('S6DRIVE_'+name+'.csv'))
        t=v.t_s.to_numpy()-3;gain=np.interp(v.engine_rpm,curve[:,0],curve[:,1])*9.23/(550*.285)
        kernels=[]
        for i in [1,2,3]:
            values=np.zeros(5);values[i]=1
            weight=np.interp(v.acc_pct,knots,values,left=0,right=0)*(v.brake_pct.to_numpy()==0)
            k=cumulative_trapezoid(weight*gain,t,initial=0);kernels.append(np.interp(q.relative_s,t,k))
        mask=q.valid&q.powered&(q.observed_v>.1);X=np.array(kernels).T[mask];e=(q.native_v-q.observed_v).to_numpy()[mask]
        b=pd.read_csv(OUT/'comparisons'/('R5_'+name+'.csv'));bm=b.valid&b.powered&(b.observed_v>.1)
        sets[name]=(X,e,float(np.sqrt(np.mean((b.native_v[bm]-b.observed_v[bm])**2))))
    def error(name,x):
        X,e,base=sets[name];return float(np.sqrt(np.mean((e+X@x)**2)))
    limits={names[0]:.9*sets[names[0]][2],names[1]:1.00*sets[names[1]][2],names[2]:1.05*sets[names[2]][2],names[3]:1.05*sets[names[3]][2]}
    constraints=[dict(type='ineq',fun=lambda x,n=n,limit=limit:limit-error(n,x)) for n,limit in limits.items()]
    opt=minimize(lambda x:error(names[0],x)**2+.3*error(names[2],x)**2+.01*np.sum((x/.01)**2),
        [.003,-.007,.007],bounds=[(-.005,.005),(-.015,0),(0,.018)],constraints=constraints,method='SLSQP',options={'maxiter':200,'ftol':1e-12})
    delta=[float(x) for x in opt.x];table=drive['pedal_map']
    for k,change in zip([85,90,95],delta):
        for point in table:
            if point[0]==k:point[1]+=change
    assert all(table[i][1]<=table[i+1][1] for i in range(len(table)-1))
    report=dict(success=bool(opt.success),message=str(opt.message),delta=delta,limits=limits,
                predictions={n:dict(reference_R5=s[2],parent=error(n,np.zeros(3)),proposal=error(n,opt.x)) for n,s in sets.items()},pedal_map=table)
    save(OUT/'pedal_repair_proposal.json',report)
    if not opt.success:raise RuntimeError('Optimizer did not certify convergence; proposal preserved without native execution')
    make('S6REPAIR','S6COAST','6a_revisit','Redistribute the small85/90/95% pedal correction to preserve low-speed acceleration and remove the LONK30 overspeed regression.',drive_patch={'pedal_map':table},extra=report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
