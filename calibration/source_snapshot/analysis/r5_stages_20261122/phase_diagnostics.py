"""Command-anchored stopping and response metrics; never reset native states."""
import argparse
import json
import numpy as np
import pandas as pd
from common import ROOT, OUT


def stop_time(t, speed, start, end):
    # Both traces use the same command edge and sustained 0.5s, 0.1m/s stop rule.
    for i in np.flatnonzero((t>=start)&(t<=end-.5)&(np.abs(speed)<.1)):
        part=(t>=t[i])&(t<=t[i]+.5)
        if np.max(np.abs(speed[part]))<.1:
            return float(t[i]-start)
    return None


def main(label):
    metrics=pd.read_csv(OUT/'metrics.csv');records=[]
    for row in metrics[metrics.label==label].itertuples():
        result=json.loads((ROOT/row.folder/'result.json').read_text());w=result['window']
        commands=pd.read_csv(result['actual_command_source'])
        commands=commands[commands.time_s.between(w['start_s'],w['end_s'])].copy()
        q=pd.read_csv(OUT/'comparisons'/(label+'_'+row.session+'.csv'))
        time=q.relative_s.to_numpy();real=q.observed_v.to_numpy();native=q.native_v.to_numpy()
        changes=commands.brake_pct.ne(commands.brake_pct.shift())
        phases=commands.loc[changes,['time_s','brake_pct']].copy()
        phases['end_s']=phases.time_s.shift(-1).fillna(w['end_s'])
        for phase in phases.itertuples():
            start=phase.time_s-w['start_s'];end=phase.end_s-w['start_s']
            if phase.brake_pct<30 or end-start<.5:continue
            initial=float(np.interp(start,time,real))
            if initial<.3:continue
            mask=(time>=start)&(time<=end)&q.valid.to_numpy()
            fit=(time>=start+.3)&(time<=min(end-.3,start+1.3))&(real>.3)&q.valid.to_numpy()
            obs_acc=(np.interp(time+.2,time,real)-np.interp(time-.2,time,real))/.4
            nat_acc=(np.interp(time+.2,time,native)-np.interp(time-.2,time,native))/.4
            r=dict(label=label,session=row.session,start_s=float(start),end_s=float(end),brake_pct=int(phase.brake_pct),
                   observed_initial_mps=initial,native_initial_mps=float(np.interp(start,time,native)),
                   observed_stop_delay_s=stop_time(time,real,start,end),native_stop_delay_s=stop_time(time,native,start,end),
                   observed_distance_m=float(np.trapz(real[mask],time[mask])),native_distance_m=float(np.trapz(native[mask],time[mask])),
                   speed_rmse_mps=float(np.sqrt(np.mean((real[mask]-native[mask])**2))),
                   fit_samples=int(fit.sum()),observed_acceleration_mps2=float(np.mean(obs_acc[fit])) if fit.any() else None,
                   native_acceleration_mps2=float(np.mean(nat_acc[fit])) if fit.any() else None)
            records.append(r)
    (OUT/('braking_events_'+label+'.json')).write_text(json.dumps(records,indent=2,allow_nan=False)+'\n')
    df=pd.DataFrame(records);df.to_csv(OUT/('braking_events_'+label+'.csv'),index=False)
    print(df.round(4).to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args();main(a.label)
