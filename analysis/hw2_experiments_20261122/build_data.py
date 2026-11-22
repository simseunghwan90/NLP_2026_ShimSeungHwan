"""Assemble all reported cases through the previously audited comparison checks."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/evidence/2026-11-22_hw2_experiments'
OLD=ROOT/'experiments/evidence/2026-11-22_lat3_three_models'
sys.path.insert(0,str(ROOT/'analysis/lat3_three_models_20261122'))
import plot as shared


def main():
    target=OUT/'comparison';target.mkdir(exist_ok=True)
    cases=json.loads((OUT/'design.json').read_text())['comparison_cases']
    windows=json.loads((ROOT/'experiments/evidence/2026-11-22_r5_stages/windows.json').read_text())
    (target/'windows.json').write_text(json.dumps({c:windows[c] for c in cases},indent=2)+'\n')
    for name,path in [('models',OLD/'models'),('decoded',OLD/'decoded')]:
        if not (target/name).exists():(target/name).symlink_to(path,target_is_directory=True)
    links=target/'replay_links';links.mkdir(exist_ok=True)
    for root in [OLD/'native_replays',OUT/'native_replays']:
        for p in root.iterdir():
            if p.is_dir() and not (links/p.name).exists():(links/p.name).symlink_to(p,target_is_directory=True)
    shared.OUT=target;shared.NEW_ROOT=links;shared.CASES=cases
    data,metrics=shared.collect()
    metrics['turn_error']=abs(metrics.signed_turns-metrics.gnss_signed_turns)
    metrics.to_csv(target/'metrics.csv',index=False)
    cat=json.loads((ROOT/'experiments/evidence/2026-11-22_r5_stages/execution_catalog.json').read_text())
    costs={k:cat[k] for k in ['native_attempts','status_counts','native_wall_seconds','physical_tests']}
    costs['scope']='Archived R5-to-R6V2 stage only; process durations summed, not total interaction/inference time.'
    costs['labels_including_controls']=len(cat['counts_by_label'])
    costs['catalog_sha256']=hashlib.sha256((ROOT/'experiments/evidence/2026-11-22_r5_stages/execution_catalog.json').read_bytes()).hexdigest()
    (target/'costs.json').write_text(json.dumps(costs,indent=2)+'\n')
    print(metrics[['case','model','replay_status','speed_rmse_mps','position_rmse_m','endpoint_m','turn_error']].to_string(index=False))
    return data,metrics


if __name__=='__main__':main()
