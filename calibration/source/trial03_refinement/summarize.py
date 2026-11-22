"""Export per-window and per-family evidence; require complete final coverage."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from setup import ROOT, OUT, digest
from assess import compare

def main():
    p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args()
    windows=json.loads((OUT/'windows.json').read_text())
    metrics=pd.read_csv(OUT/'metrics.csv').set_index(['label','session'])
    expected=set(windows);found=set(metrics.loc[a.label].index)
    if found!=expected:raise ValueError('Incomplete final coverage: '+str(sorted(expected-found)))
    rows=[];equivalence={}
    for name,w in windows.items():
        base=metrics.loc[('T0',name)];new=metrics.loc[(a.label,name)]
        family='stationary' if w.get('stationary') else 'circle' if name.startswith(('LAT4','LAT5')) else 'move' if name.startswith('MOVE') else 'straight'
        row=dict(session=name,family=family,duration_s=new.duration_s)
        for key in ['moving_speed_rmse_mps','powered_speed_rmse_mps','coast_speed_rmse_mps','braking_speed_rmse_mps','position_rmse_m','endpoint_m','turn_error','observed_turns','native_turns','heading_endpoint_deg','moving_heading_rmse_deg','steering_rmse_deg','valid_count','excluded_observation_count']:
            row['trial03_'+key]=base[key];row[a.label+'_'+key]=new[key]
            if ('M0',name) in metrics.index:row['M0_'+key]=metrics.loc[('M0',name)][key]
        rows.append(row)
        if family in ['straight','stationary']:
            report={}
            for file in ['vehicle_telemetry.csv','steering_telemetry.csv']:
                x=pd.read_csv(ROOT/base.folder/file);y=pd.read_csv(ROOT/new.folder/file);cols=sorted(set(x)&set(y))
                report[file]=dict(rows=len(x),columns=len(cols),same_shape=x[cols].shape==y[cols].shape,
                    max_abs_difference=float(np.max(np.abs(x[cols].to_numpy()-y[cols].to_numpy()))) if x[cols].shape==y[cols].shape else None)
                if file=='steering_telemetry.csv':
                    # R5 intentionally changes tire-angle geometry; audit actuator dynamics separately.
                    dynamics=['simulation_s','dt_s','can_target_handwheel_deg','model_handwheel_deg','model_rate_deg_s']
                    report[file]['actuator_dynamics_columns']=dynamics
                    report[file]['actuator_dynamics_max_abs_difference']=float(np.max(np.abs(x[dynamics].to_numpy()-y[dynamics].to_numpy()))) if x[dynamics].shape==y[dynamics].shape else None
                    report[file]['actual_handwheel_max_abs_difference_deg']=float(np.max(np.abs(x.actual_handwheel_deg-y.actual_handwheel_deg))) if len(x)==len(y) else None
            report['family']=family
            equivalence[name]=report
    df=pd.DataFrame(rows);df.to_csv(OUT/('final_comparison_'+a.label+'.csv'),index=False)
    groups={}
    for family in ['circle','straight','move']:
        q=df[df.family==family];g={'cases':len(q)}
        for key in ['moving_speed_rmse_mps','position_rmse_m','endpoint_m','turn_error']:
            before=float(q['trial03_'+key].mean());after=float(q[a.label+'_'+key].mean())
            g[key]=dict(before=before,after=after,reduction_pct=(1-after/before)*100 if before else None)
        groups[family]=g
    assessment=compare(a.label)
    (OUT/('summary_'+a.label+'.json')).write_text(json.dumps(dict(label=a.label,groups=groups,flagged_cases=[r for r in assessment if r['flags']],all_circle_turn_targets_met=bool(df[df.family=='circle'][a.label+'_turn_error'].le(.1).all())),indent=2)+'\n')
    (OUT/('straight_stationary_equivalence_'+a.label+'.json')).write_text(json.dumps(equivalence,indent=2)+'\n')
    print(json.dumps(groups,indent=2));print('Flagged:',[(r['session'],r['flags']) for r in assessment if r['flags']])

if __name__=='__main__':main()
