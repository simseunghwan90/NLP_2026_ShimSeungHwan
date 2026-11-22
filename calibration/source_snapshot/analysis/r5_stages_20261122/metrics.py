"""Fixed-time phase metrics and unwrapped revolutions, without state resets."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from common import ROOT, OUT, PREVIOUS

def rmse(x):
    x=np.asarray(x,dtype=float)
    return float(np.sqrt(np.mean(x*x))) if len(x) else None

def turns(observed, native):
    a=np.unwrap(np.asarray(observed,dtype=float)); b=np.unwrap(np.asarray(native,dtype=float))
    return (a[-1]-a[0])/(2*np.pi), (b[-1]-b[0])/(2*np.pi)

def summarize(path):
    r=json.loads(path.read_text())
    if r['status']!='PASS':return None,None
    name=r['session']; w=r['window']; folder=path.parent
    if r['label']=='P0':r['label']='R5'
    g=pd.read_csv(OUT/'decoded'/('20261120_'+name)/'state.csv')
    g=g[g.time_s.between(w['start_s'],w['end_s'])].copy().reset_index(drop=True)
    v=pd.read_csv(folder/'vehicle_telemetry.csv')
    q=pd.read_csv(folder/'trajectory_comparison.csv')
    f=pd.read_csv(OUT/'decoded'/('20261120_'+name)/'feedback.csv')
    c=pd.read_csv(r['actual_command_source'])
    t=g.time_s.to_numpy(); simt=v.t_s.to_numpy()-3+w['start_s']
    ix=np.searchsorted(c.time_s,t,side='right')-1
    acc=c.acc_pct.to_numpy()[ix]; brake=c.brake_pct.to_numpy()[ix]
    valid=g.status_valid.to_numpy().astype(bool)&(g.gnss_fix.to_numpy()==4)
    # Fixed observed quality only. Never select by candidate output or residual.
    dt=np.diff(t); bad=np.flatnonzero(dt>.1)
    for i in bad: valid&=~((t>=t[i]-.1)&(t<=t[i+1]+.1))
    nv=np.interp(t,simt,v.speed_mps)
    ov=g.vx_mps.to_numpy(); err=nv-ov
    hd=q.native_heading_rad.to_numpy()-q.observed_heading_rad.to_numpy()
    wrapped=np.degrees(np.arctan2(np.sin(hd),np.cos(hd)))
    pos=np.hypot(q.native_x-q.observed_x,q.native_y-q.observed_y).to_numpy()
    power=(acc>0)&(brake==0); coast=(acc==0)&(brake==0); braking=brake>0
    moving=abs(ov)>.1
    observed_turns,native_turns=turns(q.observed_heading_rad,q.native_heading_rad)
    row=dict(label=r['label'],session=name,folder=str(folder.relative_to(ROOT)),duration_s=w['end_s']-w['start_s'],
        endpoint_m=float(pos[-1]),position_rmse_m=rmse(pos[valid]),heading_rmse_deg=rmse(wrapped[valid]),
        moving_heading_rmse_deg=rmse(wrapped[valid&moving]),heading_endpoint_deg=float(abs(wrapped[-1])),
        observed_turns=observed_turns,native_turns=native_turns,turn_error=abs(native_turns-observed_turns),
        unwrapped_heading_endpoint_deg=abs(native_turns-observed_turns)*360,
        steering_rmse_deg=r['steering_rmse_deg'],valid_count=int(valid.sum()),excluded_observation_count=int((~valid).sum()))
    for label,mask in [('whole',np.ones(len(t),bool)),('moving',moving),('powered',power),('coast',coast),('braking',braking),('stopped',~moving)]:
        m=valid&mask
        row[label+'_speed_rmse_mps']=rmse(err[m]);row[label+'_samples']=int(m.sum())
    h=np.interp(t,f.time_s,f.handwheel_deg)
    stable=valid&(ov>.5)&(t>t[0]+1)&(t<t[-1]-1)&(abs(h-np.interp(t-1,f.time_s,f.handwheel_deg))<1.5)
    # Require every recorded input over the complete central 1s support to be powered.
    badinput=~((c.acc_pct.to_numpy()>0)&(c.brake_pct.to_numpy()==0))
    csum=np.r_[0,np.cumsum(badinput)]
    lo=np.maximum(0,np.searchsorted(c.time_s,t-.5,side='right')-1)
    hi=np.searchsorted(c.time_s,t+.5,side='right')
    stable&=(csum[hi]-csum[lo])==0
    native_yaw=np.unwrap(-np.deg2rad(v.yaw_ue_deg.to_numpy()))
    nr=np.interp(t+.5,simt,native_yaw)-np.interp(t-.5,simt,native_yaw)
    observed_k=np.deg2rad(g.yaw_rate_deg_s.to_numpy())/np.maximum(ov,.01)
    native_k=np.divide(nr,nv,out=np.full(len(t),np.nan),where=nv>.1)
    oa=np.interp(t+.5,t,ov)-np.interp(t-.5,t,ov)
    na=np.interp(t+.5,simt,v.speed_mps)-np.interp(t-.5,simt,v.speed_mps)
    samples=pd.DataFrame(dict(label=r['label'],session=name,time_s=t[stable],relative_s=t[stable]-w['start_s'],
        acc_pct=acc[stable],handwheel_deg=h[stable],observed_v=ov[stable],native_v=nv[stable],
        observed_k=observed_k[stable],native_k=native_k[stable],observed_a=oa[stable],native_a=na[stable]))
    for key in ['observed_v','native_v','observed_k','native_k','observed_a','native_a']:
        row['steady_'+key]=float(samples[key].median()) if len(samples) else None
    row['steady_speed_rmse_mps']=rmse(samples.native_v-samples.observed_v)
    row['steady_curvature_invalid_count']=int(samples.native_k.isna().sum())
    observed_yaw_rate=g.yaw_rate_deg_s.to_numpy()
    native_yaw_rate=np.degrees(nr)
    row['moving_yaw_rate_rmse_deg_s']=rmse((native_yaw_rate-observed_yaw_rate)[valid&moving])
    row['steady_curvature_rmse_per_m']=rmse(samples.native_k-samples.observed_k) if not samples.native_k.isna().any() else None
    pd.DataFrame(dict(relative_s=t-w['start_s'],observed_v=ov,native_v=nv,acc_pct=acc,brake_pct=brake,valid=valid,powered=power,stable=stable,
                       observed_x=q.observed_x,observed_y=q.observed_y,native_x=q.native_x,native_y=q.native_y,
                       observed_heading=q.observed_heading_rad,native_heading=q.native_heading_rad)).to_csv(OUT/'comparisons'/(r['label']+'_'+name+'.csv'),index=False)
    return row,samples

def main():
    (OUT/'comparisons').mkdir(exist_ok=True)
    rows=[];samples=[]
    paths=[p for p in (PREVIOUS/'native_replays').glob('*/result.json') if json.loads(p.read_text()).get('label')=='R5']
    paths += sorted((OUT/'native_replays').glob('*/result.json'))
    for p in paths:
        a,b=summarize(p)
        if a:rows.append(a);samples.append(b)
    df=pd.DataFrame(rows).drop_duplicates(['label','session'],keep='last')
    df.to_csv(OUT/'metrics.csv',index=False)
    pd.concat(samples,ignore_index=True).to_csv(OUT/'steady_samples.csv',index=False)
    print(df[['label','session','moving_speed_rmse_mps','powered_speed_rmse_mps','braking_speed_rmse_mps','endpoint_m','turn_error']].round(4).to_string(index=False))

if __name__=='__main__':main()
