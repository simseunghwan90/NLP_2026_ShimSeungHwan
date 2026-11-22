"""Keep shape/progression tradeoffs visible in the final development review."""
import json
import pandas as pd
from common import ROOT,OUT,digest
from candidate import model_path


def main():
    label='R6V2'
    audit=json.loads((OUT/('audit_'+label+'.json')).read_text())
    assert audit['complete_native_count']==28 and not audit['missing'] and not audit['evidence_issues'] and not audit['changed_protected_or_inputs']
    m=pd.read_csv(OUT/'metrics.csv').set_index(['label','session'])
    shape=pd.read_csv(OUT/'shape_metrics.csv').set_index(['label','session'])
    brake=json.loads((OUT/'brake_response_R6V2.json').read_text())['summary']
    decisions=json.loads((OUT/'stage_decisions_in_progress.json').read_text())
    decisions['4']['decision']='Keep the bounded85/90/95 pedal correction in R6V2; all final checks use the full fixed windows.'
    decisions['5']['decision']='Keep the S5B brake table; report matched-speed force diagnostic alongside unchanged fixed-time stopping/path metrics.'
    decisions['6']['attempts']+=['R6B','R6V2']
    decisions['6']['decision']='R6B restores100percent pedal to0.33 and shifts the earlier uniform reduction to the high-RPM torque curve. Preserve original torque through1300rpm and reduce above that, reaching the previous gain at4000rpm. R6V2 adds the independently explored low-speed response term. R6B is a six-case control, not a full28-case candidate.'
    decisions['7']['decision']='Reject the actuator refit. Keep R5 actuator dynamics and outer geometry knots. Retain only a10percent center-map gain reduction at the added-40/+5 handwheel knots; report LAT6 full continuous replay and high-speed yaw/heading checks. Do not claim actuator identification improved.'
    decisions['8']['attempts']+=['R6V2']
    decisions['8']['decision']='R6V2 keeps the rising low-speed response term, improving slow MOVE strongly. Preserve the mixed shape/endpoint outcomes in the other MOVE cases. S8CFIT improves one primary path but was not tested as a global model or combined with creep. Constant low-speed resistance candidates stall or escape; do not adopt them. No claim that all MOVE trajectories are calibrated.'
    decisions['body_parameters']=json.loads((OUT/'body_parameters_review.json').read_text())
    decisions['final']=dict(candidate=label,baseline='R5',complete_windows=28,strict_gate_pass=audit['full_regression_pass'],
                            regression_flags=audit['regression_flags'],default_changed=False,
                            interpretation='Reviewed cumulative development candidate, with measured improvements and explicitly unresolved MOVE tradeoffs; not a claim of universal superiority or heldout performance.')
    (OUT/'stage_decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
    slow=m.loc[(label,'MOVE_LAT3_Apos_s2')];base=m.loc[('R5','MOVE_LAT3_Apos_s2')]
    cases=['MOVE_LAT3_Apos_s2','MOVE_LAT2_1_s2','MOVE_LAT2_2_s1','LAT6_L_s1']
    review=[]
    for name in cases:
        a=shape.loc[('R5',name)];b=shape.loc[(label,name)]
        review.append(dict(session=name,R5={k:float(a[k]) for k in ['endpoint_m','nearest_path_rms_m','ordered_progress_position_rmse_m','turn_error','path_length_ratio']},candidate={k:float(b[k]) for k in ['endpoint_m','nearest_path_rms_m','ordered_progress_position_rmse_m','turn_error','path_length_ratio']}))
    result=dict(candidate=label,strict_gate_pass=audit['full_regression_pass'],regression_flags=audit['regression_flags'],
                slow_move_speed_reduction_pct=float(100*(1-slow.moving_speed_rmse_mps/base.moving_speed_rmse_mps)),
                brake_deceleration_rmse=brake,shape_review=review,
                decision='Preserve R6V2 as the cumulative research candidate and R5 as the frozen rollback/reference. Do not silently discard shape gains because of endpoint alone; do not hide unresolved extra loops or claim all fixed gates passed. No GUI/default deployment.',
                limitations=['MOVE_LAT2_2_s1 still has excess speed and extra revolutions.','MOVE_LAT2_1_s2 improves shape but has a farther endpoint.','Low-speed damping is an effective response hypothesis, not independently identified tire or brake physics.','All exposed development data; no heldout final evaluation.'])
    (OUT/'candidate_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    report=OUT/'REPORT.md';body=report.read_text()
    if {r['session'] for r in audit['regression_flags']} == {'MOVE_LAT2_1_s2','MOVE_LAT2_2_s1'}:
        body=body.replace('고정 회귀 기준을 넘은 항목이 있어 전체 대체 모델로 승격하지 않는다.',
                          'R6V2를 모양·진행량·종점의 절충을 기록한 후속 연구 후보로 보존한다. 사전 수치 기준은 26개 구간에서 통과했으며 MOVE 두 구간의 종점 경고가 남는다. 이 경고를 소급해 통과로 바꾸지 않는다.')
    lines=['## 개선과 남은 절충', '',
           f'저속 MOVE_LAT3_Apos_s2의 이동 중 속도 RMSE는 {base.moving_speed_rmse_mps:.3f} → {slow.moving_speed_rmse_mps:.3f}m/s로 {result["slow_move_speed_reduction_pct"]:.1f}% 줄었다. 누적 회전수 오차는 {base.turn_error:.3f} → {slow.turn_error:.3f}바퀴이다. 종점만 보면 작은 차이지만 기존의 불필요한 추가 회전이 크게 줄었다.', '',
           f'LON3의 같은 속도대 감속도 RMSE는 {brake["R5"]["acceleration_rmse_mps2"]:.3f} → {brake[label]["acceleration_rmse_mps2"]:.3f}m/s²이다. 이는 제동 특성 진단이며 전체 시간축의 정지 위치 평가와 구분한다.', '',
           '| 구간 | 종점 R5 → 후보 (m) | 경로 최근접 RMS (m) | 진행 순서 위치 RMSE (m) | 회전수 오차 (바퀴) |',
           '| --- | ---: | ---: | ---: | ---: |']
    for row in review:
        a=row['R5'];b=row['candidate'];lines.append(f'| {row["session"]} | {a["endpoint_m"]:.2f} → {b["endpoint_m"]:.2f} | {a["nearest_path_rms_m"]:.2f} → {b["nearest_path_rms_m"]:.2f} | {a["ordered_progress_position_rmse_m"]:.2f} → {b["ordered_progress_position_rmse_m"]:.2f} | {a["turn_error"]:.3f} → {b["turn_error"]:.3f} |')
    lines += ['', 'MOVE_LAT2_1은 모양·진행 순서·회전수가 개선되지만 종점이 멀어진 절충이다. MOVE_LAT2_2는 여전히 과속과 추가 회전이 크므로 보정 완료로 판단하지 않는다. 원선회와 LAT6의 모양·진행량은 별도 표와 그림으로 확인한다. 고정 회귀 경고는 삭제하거나 통과로 바꾸지 않는다.', '',
              '최종 보존 후보는 R6V2이다. 수치 기준의 전체 통과와 전체 모델의 자동 교체를 주장하지 않는다. [후보 검토](candidate_review.json)에 개선과 한계를 함께 남기고 R5를 비교·복구 기준으로 보존한다.', '',
              '![저속 MOVE의 속도·경로·추가 회전 비교](figures/MOVE_LAT3_Apos_s2.png)', '',
              '![종점과 모양의 절충이 있는 MOVE 비교](figures/MOVE_LAT2_1_s2.png)', '']
    body=body.replace('## 최종 비교','\n'.join(lines)+'\n## 최종 비교',1)
    report.write_text(body)
    selection=json.loads((OUT/'selected_model.json').read_text());selection['review']='candidate_review.json';selection['scope']='Cumulative research candidate; frozen strict gate result and limitations retained. No global default promotion.'
    selection['research_recommendation']='Retain R6V2 for review and further development with the documented shape/endpoint tradeoffs; do not treat the two endpoint flags as proof that every response is worse.'
    (OUT/'selected_model.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
    # Persist exact physical-parameter deltas without changing either frozen model.
    s=json.loads(model_path(label).read_text());d=json.loads((ROOT/s['base_longitudinal_model']).read_text())
    bs=json.loads((ROOT/'models/candidates/steering_trial03_refine_2026-11-21_R5.json').read_text())
    bd=json.loads((ROOT/'models/candidates/drive_trial03_refine_2026-11-21_R5.json').read_text())
    omit={'model_id','provenance','base_longitudinal_model','base_longitudinal_sha256','native_project','native_binary_sha256'}
    changes={kind:{k:dict(R5=old.get(k),candidate=v) for k,v in new.items() if k not in omit and v!=old.get(k)} for kind,old,new in [('steering',bs,s),('drive',bd,d)]}
    (OUT/'final_parameter_changes.json').write_text(json.dumps(changes,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
