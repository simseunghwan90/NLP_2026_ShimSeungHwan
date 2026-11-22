"""Assemble an auditable development report from a completed candidate suite."""
import argparse
import json
import pandas as pd
from common import ROOT,OUT,digest
from audit import audit
from candidate import model_path


def number(value, digits=3):
    return '—' if pd.isna(value) else f'{value:.{digits}f}'


def group(name):
    if name.startswith(('LAT1','SELFCHECK')):return '정지 조향'
    if name.startswith('LAT3'):return 'LAT3 직진'
    if name.startswith(('LAT4','LAT5')):return '원선회 8개'
    if name.startswith('LON2'):return 'LON2 2개'
    if name.startswith('LON3'):return 'LON3 반복 제동'
    if name.startswith(('LON5','LONK')):return '고속 4개'
    if name.startswith('LAT6'):return 'LAT6 연속 반복'
    return 'MOVE 6개'


def main(label):
    a=audit(label)
    if a['missing'] or a['evidence_issues'] or a['changed_protected_or_inputs']:
        raise RuntimeError('Complete immutable native evidence is required before the final report')
    (OUT/('audit_'+label+'.json')).write_text(json.dumps(a,indent=2)+'\n')
    d=pd.read_csv(OUT/'metrics.csv');b=d[d.label=='R5'].set_index('session');n=d[d.label==label].set_index('session')
    rows=[]
    flags={r['session']:r['flags'] for r in a['regression_flags']}
    for name,r in n.iterrows():
        old=b.loc[name]
        rows.append(dict(session=name,group=group(name),R5_speed=old.moving_speed_rmse_mps,new_speed=r.moving_speed_rmse_mps,
                         R5_endpoint=old.endpoint_m,new_endpoint=r.endpoint_m,R5_position=old.position_rmse_m,new_position=r.position_rmse_m,
                         R5_turn_error=old.turn_error,new_turn_error=r.turn_error,flags='; '.join(flags.get(name,[]))))
    table=pd.DataFrame(rows);table.to_csv(OUT/('final_comparison_'+label+'.csv'),index=False)
    agg=table.groupby('group',sort=False).agg(count=('session','count'),R5_speed=('R5_speed','mean'),new_speed=('new_speed','mean'),R5_endpoint=('R5_endpoint','mean'),new_endpoint=('new_endpoint','mean'),R5_position=('R5_position','mean'),new_position=('new_position','mean'))
    agg['speed_reduction_pct']=100*(1-agg.new_speed/agg.R5_speed)
    agg.to_csv(OUT/('group_comparison_'+label+'.csv'))
    selection=dict(candidate=label,status='accepted_development_candidate' if a['full_regression_pass'] else 'not_promoted_regression_flags',
                   baseline='R5',default_launcher_changed=False,full_regression_pass=a['full_regression_pass'],
                   steering=a['selected_steering'],drive=a['selected_drive'],steering_sha256=a['selected_steering_sha256'],drive_sha256=a['selected_drive_sha256'],binary_sha256=a['binary_sha256'],
                   baseline_model_retained=True,regression_flags=a['regression_flags'],physical_tests=0,
                   limits='Development candidate; no heldout evaluation, no BSW/MPC runtime integration, no verified physical mass/COM identification.')
    (OUT/'selected_model.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
    lines=['# R5 후속 4~8단계 개발 보정', '',
           f'R5를 출발점으로 단계별 후보를 만들고 최종 검토 후보 **{label}**를 고정된 28개 구간에서 연속 재생했다. ',
           ('고정 회귀 기준을 모두 통과해 후속 개발 후보로 선택한다.' if a['full_regression_pass'] else '고정 회귀 기준을 넘은 항목이 있어 전체 대체 모델로 승격하지 않는다.'),
           '실행 기본값은 변경하지 않는다. 기존 R5·trial03·사용자 GUI·MPC·BSW와 원본 기록을 보존한다. 이 결과는 공개된 개발 자료의 재생 비교이며 미공개 최종 평가가 아니다.', '',
           '## 최종 비교', '',
           '각 행은 해당 묶음의 구간별 지표를 산술 평균한 값이다. 정지 자료를 속도 개선 평균에 섞지 않는다. 속도는 관측 속도 0.1m/s 초과 표본의 RMSE이며 단위는 m/s이다. 종점·위치는 m이다. 묶음 평균으로 개별 실패를 상쇄하지 않는다.', '',
           '| 묶음 | 구간 | 속도 RMSE R5 → 후보 | 종점 R5 → 후보 | 위치 RMSE R5 → 후보 |', '| --- | ---: | ---: | ---: | ---: |']
    for name,r in agg.iterrows():
        lines.append(f'| {name} | {int(r["count"])} | {number(r.R5_speed)} → {number(r.new_speed)} | {r.R5_endpoint:.2f} → {r.new_endpoint:.2f} | {r.R5_position:.2f} → {r.new_position:.2f} |')
    lines += ['', '## 구간별 결과', '', '| 구간 | 속도 RMSE R5 → 후보 | 종점 R5 → 후보 | 누적 회전수 오차 R5 → 후보 | 고정 회귀 기준 |', '| --- | ---: | ---: | ---: | --- |']
    for r in table.itertuples():
        lines.append(f'| {r.session} | {number(r.R5_speed)} → {number(r.new_speed)} | {r.R5_endpoint:.2f} → {r.new_endpoint:.2f} | {r.R5_turn_error:.3f} → {r.new_turn_error:.3f} | {r.flags or "통과"} |')
    lines += ['', '## 모양과 진행량', '',
              '종점 하나로 모델을 고르지 않는다. 경로 모양은 초기 자세만 정렬한 경로의 양방향 최근접 거리와 진행 순서에 따른 위치·방향 차이로 진단한다. 같은 원을 추가로 도는 경우 최근접 거리가 작을 수 있으므로 총 이동거리와 누적 회전수를 반드시 함께 본다. 같은 시각의 위치·속도·종점 오차도 그대로 남긴다. 좌표의 사후 이동·회전·확대나 재생 상태 교정은 하지 않는다.', '',
              '[모양 지표](shape_metrics.csv), [모양 진단 설계](shape_diagnostic_design.json), [속도·경로·회전수 그림](figures/)을 함께 확인한다. GNSS 위치 잡음은 기하학적 경로 길이를 늘릴 수 있어 속도 적분 거리도 따로 제공한다.', '',
              '## 단계별 변경과 기각', '',
              '[단계별 판단](stage_decisions.json)을 따른다. 각 후보의 설계는 실행 전에 고정했다. `S6A`와 `S8A`는 준비 후 대체한 후보이며 실행 결과로 세지 않는다. 중간 불합격 후보를 수리하는 실험도 부모와 함께 보존하되 전체 수락과 구분한다.', '',
              'LAT6 액추에이터 재추정은 첫 블록의 오차를 조금 줄였지만 두 번째 반복과 LAT1을 악화시켜 기각했다. R5의 지연·고유진동수·감쇠·조향 속도 제한을 유지한다. 질량 550kg, COM [0,0,0.35]m, 관성 및 좌우 정적 하중도 유지한다. 이는 상속한 추정값이며 이번에 실측하거나 민감도 실험으로 검증한 값이 아니다. 사용자 진술에 따라 무인·같은 평탄면 조건을 적용하고 시험별 탑승자·경사 보정을 만들지 않았다.', '',
              '## 재현과 검증 경계', '',
              '[실행 명령](../../../analysis/r5_stages_20261122/README.md), [절차·입력·판정](../../../analysis/r5_stages_20261122/WORKFLOW.md), [최종 감사](audit_'+label+'.json), [실행 목록·소스 해시](execution_catalog.json), [모델 선택과 해시](selected_model.json)를 보존한다.', '',
              'Unreal/PhysX TestPad의 별도 offscreen 프로젝트와 포트 41709를 사용한다. 물리 간격은 0.01초이다. 관측 CAN 명령을 고정한 시간축으로 재생하며 반복 사이에 상태를 초기화하지 않는다. 초기 관측 속도는 모두 0.01m/s 미만이며 정지·초기 조향 준비를 검사한다. 최초 자세 이후 실측 상태를 주입하지 않는다. 센서 기준점은 GnssState가 선언한 후륜축과 네이티브 후륜 중점이며 당시 실차 외부 파라미터는 독립 확인하지 못했다.', '',
              '원래 R5 바이너리와 두 선택형 저속 저항 바이너리를 분리한다. 기능을 끈 NP0·NP1 대조에서 보존된 차량·조향 텔레메트리와 정확히 같은 수치를 확인했다. 시작 중복 1회는 프로젝트 잠금이 차단했으며 원래 실행은 정상 완료했다. R6B는 핵심 비교 4개와 정지 대조 2개를 마친 뒤 최종 누적 후보 검증으로 전환하며 자체 배치를 중단했다. 진행 중이던 SELFCHECK_s2는 KeyboardInterrupt를 남기고 소유 프로세스가 정리됐다. 미완료 기록을 완료 결과로 세지 않는다. 실패·중단 시도도 삭제하지 않는다.', '',
              '실차 추가 시험 비용은 0회이다. BSW/MPC의 새 폐루프 주행이나 실차 일치를 검증했다고 주장하지 않는다. 세션 메타데이터의 설정은 `gpt-6-astra`, 추론 노력 `xhigh`이며 서버 빌드나 가중치를 독립 검증한 값은 아니다. 공개 사용자 지시·응답·도구 호출의 보존 범위는 [추적 목록](trace_manifest.json)에 남긴다. 명령 배열·모델·입력 해시·재생기 소스·사람의 지시·실패 기록도 보존한다.']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(selection,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');main(p.parse_args().label)
