"""Secondary force-law diagnostic at matched speed; rollout metrics remain fixed-time."""
import argparse
import json
import numpy as np
import pandas as pd
from common import OUT

def values(q,start,end,lo,hi,key):
    t=q.relative_s.to_numpy();v=q[key].to_numpy()
    a=(np.interp(t+.15,t,v)-np.interp(t-.15,t,v))/.3
    mask=(t>start+.3)&(t<end-.2)&(v>lo)&(v<hi)&q.valid.to_numpy()
    return float(np.median(a[mask])) if mask.sum()>10 else None

def main(labels):
    events=pd.read_csv(OUT/'braking_events_R5.csv')
    events=events[events.session=='LON3_Aneg_s1']
    base=pd.read_csv(OUT/'comparisons/R5_LON3_Aneg_s1.csv')
    records=[]
    # Fix support using R5 and observations only. Missing candidate support is reported, not dropped.
    for ev in events.itertuples():
        for lo in [.3,.8,1.3,1.8,2.3,2.8]:
            obs=values(base,ev.start_s,ev.end_s,lo,lo+.5,'observed_v')
            old=values(base,ev.start_s,ev.end_s,lo,lo+.5,'native_v')
            if obs is None or old is None:continue
            row=dict(brake_pct=int(ev.brake_pct),speed_lo_mps=lo,speed_hi_mps=lo+.5,observed_a=obs,R5_a=old)
            for label in labels:
                q=pd.read_csv(OUT/'comparisons'/(label+'_LON3_Aneg_s1.csv'))
                row[label+'_a']=values(q,ev.start_s,ev.end_s,lo,lo+.5,'native_v')
            records.append(row)
    df=pd.DataFrame(records);summary={}
    for label in ['R5']+labels:
        diff=df[label+'_a']-df.observed_a
        summary[label]=dict(missing_bins=int(diff.isna().sum()),acceleration_rmse_mps2=float(np.sqrt(np.mean(diff**2))) if not diff.isna().any() else None)
    report=dict(method='Median deceleration in identical speed bins fixed by R5 support; excludes first0.3s after each command edge. Parameter diagnostic only; no temporal alignment or state resets in native replay.',summary=summary,bins=records)
    (OUT/('brake_response_'+'_'.join(labels)+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('labels',nargs='+');main(p.parse_args().labels)
