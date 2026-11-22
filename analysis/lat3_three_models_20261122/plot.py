"""Audited four-trace figures from identical recorded input windows."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/a1_lat3_matplotlib')
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from prepare import CASES, OUT, ROOT, digest, save

FINAL_ROOT = ROOT / 'experiments/evidence/2026-11-22_r5_stages/native_replays'
PREV_ROOT = ROOT / 'experiments/evidence/2026-11-21_staged_calibration/native_replays'
NEW_ROOT = OUT / 'native_replays'
FIG = OUT / 'figures'
COLORS = {'GNSS': '#111111', 'Baseline': '#999999', 'Previous': '#dc7d12', 'R6V2': '#157bb8'}
LABELS = {'GNSS': 'GNSS / INS', 'Baseline': 'Baseline (initial)', 'Previous': 'Previous', 'R6V2': 'R6V2 (final)'}
MODELS = ['Baseline', 'Previous', 'R6V2']


def passing(folder, case, label):
    paths = sorted(folder.glob('*_' + case + '_' + label + '/result.json'))
    paths = [p for p in paths if json.loads(p.read_text())['status'] == 'PASS'
             and json.loads(p.read_text())['session'] == case]
    if paths:
        return paths[-1]
    if label == 'Baseline':
        derived = sorted(folder.glob('*_' + case + '_' + label + '/derived_plot/result.json'))
        for p in reversed(derived):
            r = json.loads(p.read_text())
            if r['session'] == case and r['status'] == 'COMPLETE_WITH_CONTACT_FLAGS' and r['replay_validation_status'] == 'FAIL':
                return p
    return None


def collect():
    windows = json.loads((OUT / 'windows.json').read_text())
    sources, rows, data = {}, [], {}
    original_previous = ROOT / 'models/candidates/steering_field_2026-11-20_v2.json'
    previous_copy = OUT / 'models/Previous.json'
    clean = lambda d: {k: v for k, v in d.items() if k not in ['native_project', 'native_binary_sha256']}
    assert clean(json.loads(original_previous.read_text())) == clean(json.loads(previous_copy.read_text()))
    for case in CASES:
        paths = dict(Baseline=passing(NEW_ROOT, case, 'Baseline'),
                     Previous=passing(NEW_ROOT, case, 'Previous') or passing(PREV_ROOT, case, 'M0'),
                     R6V2=passing(FINAL_ROOT, case, 'R6V2'))
        assert all(paths.values()), (case, paths)
        sources[case], data[case] = {}, {}
        common = None
        reference_t = reference_s = reference_commands = None
        for model, p in paths.items():
            r = json.loads(p.read_text())
            replay = json.loads(p.with_name('replay.json').read_text())
            t = pd.read_csv(p.with_name('trajectory_comparison.csv'))
            s = pd.read_csv(p.with_name('speed_comparison.csv'))
            assert r['window']['start_s'] == windows[case]['start_s']
            assert r['window']['end_s'] == windows[case]['end_s']
            assert r['actual_command_sha256'] == windows[case]['command_sha256']
            assert digest(ROOT / windows[case]['command_source']) == r['actual_command_sha256']
            assert r['dt_s'] == .01 and r['owned_process_stopped']
            if model == 'R6V2':
                assert r['steering_sha256'] == digest(ROOT / 'models/candidates/steering_r5_stages_2026-11-22_R6V2.json')
                assert r['drive_sha256'] == digest(ROOT / 'models/candidates/drive_r5_stages_2026-11-22_R6V2.json')
            elif model == 'Previous':
                assert r['steering_sha256'] in [digest(original_previous), digest(previous_copy)]
                assert r['drive_sha256'] == digest(ROOT / 'models/candidates/drive_field_2026-11-20_v1.json')
            else:
                assert r['steering_sha256'] == digest(OUT / 'models/Baseline.json')
                assert r['drive_sha256'] == digest(ROOT / 'models/candidates/lift_2026-11-14_baseline.json')
                resolved = json.loads(p.with_name('steering_resolved.json').read_text())
                assert resolved['baseline_passthrough'] and resolved['handwheel_to_nominal_tire_ratio'] == 7.5
                assert resolved['legacy_steering_smoothing_rate'] == resolved['original_steering_rise_rate']
            key = dict(inputs=r['input_sha256'], map=r['map_sha256'], dt=r['dt_s'])
            if common is None:
                common = key
                reference_t = t[['relative_s', 'observed_x', 'observed_y', 'observed_heading_rad']].to_numpy()
                reference_s = s[['relative_s', 'speed_mps']].to_numpy()
                reference_commands = replay['commands']
            else:
                assert key == common, (case, model, 'provenance differs')
                np.testing.assert_allclose(reference_t, t[['relative_s', 'observed_x', 'observed_y', 'observed_heading_rad']].to_numpy(), rtol=0, atol=1e-9)
                np.testing.assert_allclose(reference_s, s[['relative_s', 'speed_mps']].to_numpy(), rtol=0, atol=1e-9)
                assert replay['commands'] == reference_commands, (case, model, 'commands differ')
            for channel, h in r['input_sha256'].items():
                assert digest(OUT / 'decoded' / ('20261120_' + case) / (channel + '.csv')) == h
            sources[case][model] = dict(result=str(p.relative_to(ROOT)), result_sha256=digest(p),
                model_sha256=r['steering_sha256'], drive_sha256=r['drive_sha256'], binary_sha256=r['binary_sha256'],
                trajectory_sha256=digest(p.with_name('trajectory_comparison.csv')),
                speed_sha256=digest(p.with_name('speed_comparison.csv')), status=r['status'],
                contact_flags=r.get('contact_flags'))
            distance = lambda x, y: float(np.hypot(np.diff(x), np.diff(y)).sum())
            heading = t.native_heading_rad.to_numpy()
            observed = t.observed_heading_rad.to_numpy()
            rows.append(dict(case=case, model=model, duration_s=windows[case]['duration_s'],
                replay_status=r.get('replay_validation_status',r['status']),
                endpoint_m=r['trajectory']['endpoint_m'], position_rmse_m=r['trajectory']['position_rmse_m'],
                speed_rmse_mps=r['speed']['rmse_mps'], speed_rmse_kph=r['speed']['rmse_mps']*3.6,
                heading_endpoint_deg=r['trajectory']['heading_endpoint_deg'],
                distance_m=distance(t.native_x, t.native_y), gnss_distance_m=distance(t.observed_x,t.observed_y),
                signed_turns=float((heading[-1]-heading[0])/(2*np.pi)),
                gnss_signed_turns=float((observed[-1]-observed[0])/(2*np.pi)),
                absolute_rotation_turns=float(np.abs(np.diff(heading)).sum()/(2*np.pi)),
                gnss_absolute_rotation_turns=float(np.abs(np.diff(observed)).sum()/(2*np.pi))))
            data[case][model] = dict(trajectory=t, speed=s, result=r)
    save(OUT / 'figure_sources.json', sources)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT / 'metrics.csv', index=False)
    return data, metrics


def curves(case_data):
    t = case_data['R6V2']['trajectory']
    x0, y0 = t.observed_x.iloc[0], t.observed_y.iloc[0]
    result = {'GNSS': (t.observed_x.to_numpy()-x0, t.observed_y.to_numpy()-y0)}
    for model in MODELS:
        t = case_data[model]['trajectory']
        result[model] = (t.native_x.to_numpy()-x0, t.native_y.to_numpy()-y0)
    return result


def trajectory(ax, case_data, detail=False):
    c = curves(case_data)
    for model in ['Baseline', 'Previous', 'R6V2', 'GNSS']:
        x, y = c[model]
        ax.plot(x, y, color=COLORS[model], lw=1.9 if model == 'GNSS' else 1.5,
                ls='--' if model == 'Baseline' else '-', alpha=.94)
        ax.plot(x[-1], y[-1], marker='x', ms=7, mew=1.8, color=COLORS[model])
    ax.plot(0, 0, marker='o', ms=5, mfc='white', mec='#111111', zorder=10)
    values = [c[k] for k in (['GNSS', 'Previous', 'R6V2'] if detail else c)]
    xy = np.concatenate([np.column_stack(v) for v in values])
    low, high = xy.min(axis=0), xy.max(axis=0)
    span = max(float(np.max(high-low)), 4)
    center = (low+high)/2
    ax.set_xlim(center[0]-.57*span, center[0]+.57*span)
    ax.set_ylim(center[1]-.57*span, center[1]+.57*span)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlabel('East from start [m]')
    ax.set_ylabel('North from start [m]')
    ax.grid(alpha=.2)
    return ax


def legend(fig, y=.93):
    handles = [Line2D([0],[0], color=COLORS[k], lw=2, ls='--' if k=='Baseline' else '-', label=LABELS[k]) for k in ['GNSS']+MODELS]
    handles += [Line2D([0],[0],color='#111111',marker='o',mfc='white',ls='',label='Start'),
                Line2D([0],[0],color='#111111',marker='x',ls='',label='End')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5,y), ncol=6, frameon=False, fontsize=10)


def export(fig, name):
    fig.savefig(FIG / (name+'.png'), dpi=190, facecolor='white')
    fig.savefig(FIG / (name+'.pdf'), facecolor='white')
    plt.close(fig)


def make_figures(data, metrics):
    FIG.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
                         'axes.spines.top':False,'axes.spines.right':False})
    for cases, title, name in [(CASES[:3], 'LAT3 main tests', 'LAT3_main_trajectories'),
                               (CASES[3:], 'MOVE records associated with LAT3', 'LAT3_MOVE_trajectories')]:
        fig, axes = plt.subplots(2, len(cases), figsize=(5.0*len(cases),10), squeeze=False)
        fig.suptitle(title, fontsize=17, y=.982)
        legend(fig, .955)
        for col, case in enumerate(cases):
            duration = data[case]['R6V2']['result']['window']['duration_s']
            trajectory(axes[0,col], data[case])
            note = ' [contact flags]*' if data[case]['Baseline']['result'].get('contact_flags') else ''
            axes[0,col].set_title(f'{case}  |  {duration:.2f} s\nFull extent, all models'+note, pad=9)
            trajectory(axes[1,col], data[case], detail=True)
            axes[1,col].set_title('Detail of GNSS / Previous / R6V2 area\nBaseline outside this area is clipped', pad=9)
        footer='Identical recorded CAN inputs and time windows; initial pose alignment only.\nCircle = start; cross = end. No subsequent trajectory fitting. Development data.'
        if any(data[c]['Baseline']['result'].get('contact_flags') for c in cases):
            footer+='\n*Baseline: intermittent wheel-contact flags; full failed rollout shown. Contact validation remains FAIL.'
        fig.text(.5,.018,footer,ha='center',fontsize=9,color='#444444')
        fig.subplots_adjust(top=.86,bottom=.10,hspace=.36,wspace=.30)
        export(fig,name)
    for case in CASES:
        fig, ax = plt.subplots(2,2,figsize=(12,10))
        fig.suptitle(case,fontsize=17,y=.98)
        legend(fig,.95)
        trajectory(ax[0,0],data[case]);ax[0,0].set_title('Trajectory: full extent')
        trajectory(ax[0,1],data[case],detail=True);ax[0,1].set_title('Trajectory: detail (Baseline may be clipped)')
        for model in ['GNSS']+MODELS:
            d=data[case]['R6V2' if model=='GNSS' else model]
            s,t=d['speed'],d['trajectory']
            vel=s.speed_mps if model=='GNSS' else s.native_speed_mps
            heading=t.observed_heading_rad if model=='GNSS' else t.native_heading_rad
            style=dict(color=COLORS[model],lw=1.6,ls='--' if model=='Baseline' else '-')
            ax[1,0].plot(s.relative_s,vel*3.6,**style)
            ax[1,1].plot(t.relative_s,(heading-heading.iloc[0])/(2*np.pi),**style)
        for a in ax[1]:a.set_xlabel('Time from window start [s]');a.grid(alpha=.2)
        ax[1,0].set_title('Speed');ax[1,0].set_ylabel('Speed [km/h]')
        ax[1,1].set_title('Accumulated heading (unwrapped)');ax[1,1].set_ylabel('Signed turns [revolutions]')
        footer='Same input and start pose; no posthoc fitting. Signed turns preserve direction and extra rotations.\nGNSS / INS declared rear axle vs simulated rear wheel midpoint; extrinsics not independently verified.'
        if data[case]['Baseline']['result'].get('contact_flags'):
            footer+='\nBaseline: intermittent wheel-contact flags; full failed rollout shown. Contact validation remains FAIL.'
        fig.text(.5,.018,footer,ha='center',fontsize=9,color='#444444')
        fig.subplots_adjust(top=.86,bottom=.10,hspace=.35,wspace=.30)
        export(fig,case+'_detail')


def report(metrics):
    lines=['# LAT3 본시험 및 MOVE의 세 모델 비교', '',
           'GNSS/INS는 검정, 최초 Baseline은 회색 점선, Previous는 주황, 최종 연구 모델 R6V2는 파랑으로 표시한다.',
           '본시험 3개와 별도로 기록된 MOVE 2개를 비교한다. Baseline은 11월 10일 보존 차량 에셋·기본 물리값을 사용하고, 동일 입력 재생·계측 어댑터만 추가한 실행이다. 역사적 바이너리 자체의 실행은 아니다. 공통 TestPad 맵은 과거 비교에 사용한 맵이며 최초 맵과 해시가 다르다.',
           '위쪽은 전체 범위, 아래쪽은 GNSS·Previous·R6V2 영역 확대이다. 확대 그림에서 범위를 벗어나는 Baseline은 잘린다. 개별 상세 그림에는 속도와 누적 회전량을 포함한다.', '',
           '두 MOVE의 Baseline은 전체 시간 재생을 완료했으나 일부 바퀴의 접촉 플래그 검사에서 실패한다. 실패 원본을 보존하고 완전한 궤적을 별도 추출해 표시한다. 해당 결과를 통과나 후보 수락으로 바꾸지 않는다.', '',
           '| 구간 | 모델 | 재생 검사 | 길이 [s] | 종점 오차 [m] | 위치 RMSE [m] | 속도 RMSE [km/h] | 누적 회전 [회] | GNSS 누적 회전 [회] |',
           '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in metrics.itertuples():
        lines.append(f'| {r.case} | {r.model} | {r.replay_status} | {r.duration_s:.2f} | {r.endpoint_m:.2f} | {r.position_rmse_m:.2f} | {r.speed_rmse_kph:.2f} | {r.signed_turns:.3f} | {r.gnss_signed_turns:.3f} |')
    lines += ['', '동일 CAN 입력·시각·구간·지도·초기 준비 조건을 확인한다. 시간 간격은 0.01초이며 시작 자세만 한 번 정렬한다. 이후 실측값을 주입하거나 궤적을 사후 정렬하지 않는다. 누적 회전은 방향 부호를 유지한 heading 변화량이며 절대 회전 총량과 구분한다.',
              'GNSS 기준점은 기록 스키마의 후륜축 선언을 사용하며 센서 외부변환을 독립 실측한 것은 아니다. 원자료에 기록된 상태 공백은 windows.json에 보존한다. 이 자료는 기존 개발 데이터이며 독립 평가 자료가 아니다.',
              '출처·모델·입력 해시는 figure_sources.json, baseline_audit.json과 각 replay result.json에 기록한다. 원본 모델·기존 결과는 변경하지 않는다.', '',
              '재생 실행: 저장소에서 `.venv/bin/python analysis/lat3_three_models_20261122/run.py --model Baseline --case LAT3_Apos_s1`을 실행한다. 별도 offscreen 프로젝트와 RPC 41923을 사용하며 기존 프로젝트를 종료하지 않는다.',
              '그림 재생성: 저장소에서 `.venv/bin/python analysis/lat3_three_models_20261122/plot.py`를 실행한다.', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    data, metrics = collect()
    make_figures(data, metrics)
    report(metrics)
    print(metrics[['case','model','endpoint_m','speed_rmse_kph','signed_turns']].to_string(index=False))
    print(FIG)
