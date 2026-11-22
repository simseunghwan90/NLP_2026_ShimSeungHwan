"""Separate R4 drive correction after the R3 geometry-only measurement."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from setup import ROOT, OUT, digest

def main():
    path=OUT/'small_angle_loss_design.json'
    if path.exists():raise FileExistsError(path)
    d=pd.read_csv(OUT/'metrics.csv').set_index(['label','session'])
    drive=json.loads((ROOT/'models/candidates/drive_trial03_refine_2026-11-21_R2.json').read_text())
    base=drive['rear_residual_torque_nm'];rows=[]
    for name in ['LAT5_L_s1','LAT5_L_s2']:
        values={}
        for label in ['T0','R1','R3']:
            row=d.loc[(label,name)];v=pd.read_csv(ROOT/row.folder/'vehicle_telemetry.csv')
            q=pd.read_csv(OUT/'comparisons'/(label+'_'+name+'.csv'))
            mask=(v.t_s>20)&(v.acc_pct>0)&(v.brake_pct==0)
            values[label]=dict(native_distance_m=float(np.trapz(np.maximum(q.native_v,0),q.relative_s)),
                observed_distance_m=float(np.trapz(np.maximum(q.observed_v,0),q.relative_s)),
                residual_nm=float(v[mask].effective_rear_residual_nm.median()) if label!='T0' else base,
                curvature_per_m=float(v[mask].loss_curvature_per_m.median()) if label!='T0' else None)
        slope=(values['R1']['native_distance_m']-values['T0']['native_distance_m'])/(values['R1']['residual_nm']-base)
        delta=values['R3']['observed_distance_m']-values['R3']['native_distance_m']
        target=values['R3']['residual_nm']+delta/slope
        if not 0<=target<=20:raise ValueError('Unbounded proposal')
        drive['powered_loss_map'].append([values['R3']['curvature_per_m'],target])
        rows.append(dict(session=name,evidence=values,distance_sensitivity_m_per_nm=slope,proposed_residual_nm=target))
    design=dict(experiment='TRIAL03-REFINE-R4',parent='R3',hypothesis='R3 makes small-angle curvature close to measured, but its R2 loss curve reduces speed. Correct only the two small-curvature loss knots using speed-integral sensitivity; steering stays R3.',
        method='T0-to-R1 native distance sensitivity estimates the R3 torque correction. Distance is integral of nonnegative recorded/native longitudinal speed over the original complete window; no trajectory or time alignment. Native verification is required.',
        fit=rows,scope='Two per-rear-wheel loss knots added between .03 and .0412/m. Original map elsewhere, straight guard, high-pedal fade, braking and coast retained. No mass/COM changes.',
        validation='Both full LAT5 replays first, then all final-regression windows and stationary checks; compare trial03 and previous M0. All data remain development.',acceptance='Original design.json unchanged; native PASS is not model adoption.')
    path.write_text(json.dumps(design,indent=2)+'\n')
    drive['powered_loss_map'].sort();drive['model_id']='DRIVE-TRIAL03-REFINE-20261121-R4'
    drive['provenance']=dict(parent='DRIVE-TRIAL03-REFINE-20261121-R2',status='experimental',design=str(path.relative_to(ROOT)),change='Two small-curvature powered loss knots; speed-integral fit after R3 geometry')
    target=ROOT/'models/candidates/drive_trial03_refine_2026-11-21_R4.json';target.write_text(json.dumps(drive,indent=2)+'\n')
    steering=json.loads((ROOT/'models/candidates/steering_trial03_refine_2026-11-21_R3.json').read_text())
    steering['model_id']='STEER-TRIAL03-REFINE-20261121-R4';steering['base_longitudinal_model']=str(target.relative_to(ROOT));steering['base_longitudinal_sha256']=digest(target)
    steering['provenance']=dict(parent='STEER-TRIAL03-REFINE-20261121-R3',status='experimental',change='R3 steering unchanged; R4 small-curvature loss')
    (ROOT/'models/candidates/steering_trial03_refine_2026-11-21_R4.json').write_text(json.dumps(steering,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
