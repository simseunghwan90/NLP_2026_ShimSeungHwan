"""Render manuscript figures and tables from frozen comparison CSVs."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/a1_paper_section6_matplotlib')
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'figures'
MODELS = ['Initial', 'Lift-refined', 'Ground-refined', 'R6V2']
COLORS = {'GNSS/INS':'#171717', 'Initial':'#8b8b8b', 'Lift-refined':'#8b4daf',
          'Ground-refined':'#d77900', 'R6V2':'#0072b2'}
LINES = {'GNSS/INS':'-', 'Initial':(0,(5,3)), 'Lift-refined':(0,(2,2)),
         'Ground-refined':(0,(6,2,1,2)), 'R6V2':'-'}
CASES = ['LAT3_Apos_s1', 'LAT3_Apos_s2', 'LAT3_Aneg_s1', 'LAT5_L_s1',
         'LON5_Aneg_v50_s1', 'MOVE_LAT3_Apos_s1', 'MOVE_LAT3_Apos_s2']
NAMES = ['LAT3 A+ s1', 'LAT3 A+ s2', 'LAT3 A- s1', 'LAT5 L s1',
         'LON5 A- 50 s1', 'MOVE LAT3 A+ s1', 'MOVE LAT3 A+ s2']
DATA = {c:{m:{kind:pd.read_csv(ROOT/'plot_data'/c/m/(kind+'.csv'))
                   for kind in ('trajectory','speed')} for m in MODELS} for c in CASES}
METRICS = pd.read_csv(ROOT/'evidence/metrics_all_windows.csv')
GROUPED = pd.read_csv(ROOT/'evidence/table2_metrics.csv')

plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':8.5,
    'axes.titlesize':9, 'axes.labelsize':8.5, 'xtick.labelsize':7.5,
    'ytick.labelsize':7.5, 'axes.spines.top':False, 'axes.spines.right':False,
    'pdf.fonttype':42, 'savefig.facecolor':'white'})

def style(model):
    return dict(color=COLORS[model], ls=LINES[model],
                lw=2.1 if model=='GNSS/INS' else 1.35)

def frame():
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.65))
    fig.subplots_adjust(left=.085, right=.985, bottom=.18, top=.74, wspace=.36)
    return fig, axes

def legend(fig, models):
    fig.legend(handles=[Line2D([0],[0],label=m,**style(m)) for m in ['GNSS/INS']+models],
               loc='upper center', bbox_to_anchor=(.52,1.005), ncol=len(models)+1,
               frameon=False, fontsize=8.1, handlelength=2.6, columnspacing=1.25)

def export(fig, name):
    for ext in ('pdf','png'):
        fig.savefig(FIG/(name+'.'+ext), dpi=220)
    plt.close(fig)

def draw_series(ax, case, kind, models=MODELS, detail=False, inset=False):
    selected = []
    for m in ['GNSS/INS']+models:
        data = DATA[case]['R6V2' if m=='GNSS/INS' else m]
        ref = m=='GNSS/INS'
        if kind=='speed':
            d = data['speed']; y = d['observed_speed_mps' if ref else 'model_speed_mps']*3.6
        else:
            d = data['trajectory']; y = d['observed_signed_turns' if ref else 'model_signed_turns']
        ax.plot(d.relative_s, y, **style(m))
        if m in ['GNSS/INS','Ground-refined','R6V2']:
            selected += [float(y.min()),float(y.max())]
    if detail:
        lo,hi=min(selected),max(selected)
        pad=max((hi-lo)*.12,.04 if kind=='turn' else .4)
        ax.set_ylim(lo-pad,hi+pad)
    ax.grid(alpha=.18)
    if not inset:
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('Speed [km/h]' if kind=='speed' else 'Signed turns [rev]')
    else:
        ax.tick_params(labelsize=6)
        ax.set_facecolor('white')

def series_inset(ax, case, kind):
    ins = ax.inset_axes([.49,.12,.48,.48])
    draw_series(ins,case,kind,detail=True,inset=True)
    ins.set_title('Detail',fontsize=6,pad=2)

def draw_xy(ax, case, models=MODELS, detail=False, inset=False):
    ref = DATA[case]['R6V2']['trajectory']
    x0,y0 = ref[['observed_x','observed_y']].iloc[0]
    points=[]
    for m in ['GNSS/INS']+models:
        d=DATA[case]['R6V2' if m=='GNSS/INS' else m]['trajectory']
        prefix='observed' if m=='GNSS/INS' else 'model'
        x,y=d[prefix+'_x']-x0,d[prefix+'_y']-y0
        ax.plot(x,y,**style(m))
        ax.plot(x.iloc[-1],y.iloc[-1],marker='x',color=COLORS[m],ms=4,mew=1)
        if not detail or m in ['GNSS/INS','Ground-refined','R6V2']:
            points.append(np.column_stack([x,y]))
    ax.plot(0,0,marker='o',ms=4,mfc='white',mec='black',zorder=20)
    points=np.concatenate(points); lo=points.min(axis=0); hi=points.max(axis=0)
    center=(lo+hi)/2; span=max(float((hi-lo).max()),2)*1.16
    ax.set_xlim(center[0]-span/2,center[0]+span/2)
    ax.set_ylim(center[1]-span/2,center[1]+span/2)
    ax.set_aspect('equal',adjustable='box'); ax.grid(alpha=.18)
    ax.ticklabel_format(style='plain',useOffset=False)
    if not inset:
        ax.set_xlabel('East [m]'); ax.set_ylabel('North [m]')
    else:
        ax.tick_params(labelsize=6); ax.set_facecolor('white')

def xy_inset(ax, case):
    ins=ax.inset_axes([.48,.1,.49,.49])
    draw_xy(ins,case,detail=True,inset=True)
    ins.set_title('Detail',fontsize=6,pad=2)

def figures():
    fig,axes=frame()
    draw_series(axes[0],'LAT5_L_s1','turn'); series_inset(axes[0],'LAT5_L_s1','turn')
    draw_series(axes[1],'LON5_Aneg_v50_s1','speed')
    axes[0].set_title('(a) LAT5 L s1',pad=6)
    axes[1].set_title('(b) LON5 A- 50 s1',pad=6)
    legend(fig,MODELS); export(fig,'figure1_development')

    fig,axes=frame(); models=['Ground-refined','R6V2']
    draw_xy(axes[0],'MOVE_LAT3_Apos_s2',models)
    draw_series(axes[1],'MOVE_LAT3_Apos_s2','turn',models)
    axes[0].set_title('(a) Trajectory',pad=6)
    axes[1].set_title('(b) Accumulated rotations',pad=6)
    legend(fig,models); export(fig,'figure2_feedback')

    for case,name in zip(CASES,NAMES):
        fig,axes=frame(); draw_xy(axes[0],case)
        kind='turn' if case.startswith(('LAT5','MOVE')) else 'speed'
        draw_series(axes[1],case,kind)
        if case.startswith('LAT3') or case=='MOVE_LAT3_Apos_s1': xy_inset(axes[0],case)
        if not case.startswith('LON5'): series_inset(axes[1],case,kind)
        axes[0].set_title('(a) '+name+' trajectory',pad=6)
        axes[1].set_title('(b) '+('Accumulated rotations' if kind=='turn' else 'Speed'),pad=6)
        legend(fig,MODELS); export(fig,'additional_'+case)

def tables():
    cols=[('LAT3 (3-window mean)','speed_rmse_mps',3),('LAT5 L s1','position_rmse_m',2),
          ('LON5 A- 50 s1','speed_rmse_mps',3),('MOVE LAT3 A+ s2','turn_error',3)]
    lines=[r'\begin{table*}[!t]',r'\centering\small',r'\setlength{\tabcolsep}{6pt}',
        r'\begin{tabular}{@{}lrrrr@{}}',r'\toprule',
        r'Model & \shortstack{LAT3\\Speed RMSE\\(m/s)} & \shortstack{LAT5\\Position RMSE\\(m)} & \shortstack{LON5\\Speed RMSE\\(m/s)} & \shortstack{MOVE s2\\Turn Error\\(rev)} \\',r'\midrule']
    for model in MODELS:
        cells=[]
        for group,key,digits in cols:
            r=GROUPED[(GROUPED.group==group)&(GROUPED.model==model)].iloc[0]
            cells.append(f'{r[key]:.{digits}f}'+(r'$^{*}$' if r.contact_flags else ''))
        lines.append(model+' & '+' & '.join(cells)+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',
        r'\caption{Representative errors across development stages; lower is better. LAT3 values are equal-weight means across three windows. $^{*}$Initial-model rollouts that failed wheel-contact validation, retained for diagnostic comparison. All results use development data.}',
        r'\label{tab:stage_summary}',r'\end{table*}']
    (ROOT/'stage_summary_table.tex').write_text('\n'.join(lines)+'\n')
    lines=[]
    for index,part in enumerate((CASES[:4],CASES[4:])):
        lines += [r'\begin{center}',r'\small',r'\setlength{\tabcolsep}{5pt}',
            r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',
            r'Window & Model & \shortstack{Speed RMSE\\(m/s)} & \shortstack{Position RMSE\\(m)} & \shortstack{Endpoint Error\\(m)} & \shortstack{Turn Error\\(rev)} \\',r'\midrule']
        for case in part:
            for i,model in enumerate(MODELS):
                r=METRICS[(METRICS.case==case)&(METRICS.model==model)].iloc[0]
                name=NAMES[CASES.index(case)].replace('+',r'$+$').replace('-',r'$-$') if i==0 else ''
                mark=r'$^{*}$' if r.replay_status!='PASS' else ''
                lines.append(name+' & '+model+mark+' & '+f'{r.speed_rmse_mps:.3f} & {r.position_rmse_m:.2f} & {r.endpoint_m:.2f} & {r.turn_error:.3f} '+r'\\')
            lines.append(r'\addlinespace[2pt]')
        lines += [r'\bottomrule',r'\end{tabular}',
            r'\captionof{table}{Individual replay-window errors: '+('LAT3 and LAT5.' if index==0 else 'LON5 and MOVE.')+
            r' $^{*}$Complete rollout with wheel-contact validation failure.}',
            r'\label{tab:all_windows_'+str(index)+r'}',r'\end{center}']
    (ROOT/'all_window_tables.tex').write_text('\n'.join(lines)+'\n')

def appendix():
    from make_appendix import main as make_appendix
    make_appendix()

def validate():
    assert len(METRICS)==28
    checked=0
    for case in CASES:
        for kind in ('trajectory','speed'):
            base=DATA[case]['R6V2'][kind]
            keys=['relative_s']+[c for c in base.columns if c.startswith('observed_')]
            for m in MODELS:
                assert np.array_equal(base[keys].to_numpy(),DATA[case][m][kind][keys].to_numpy()),(case,m,kind)
                checked+=1
        for m in MODELS:
            r=METRICS[(METRICS.case==case)&(METRICS.model==m)].iloc[0]
            assert abs(abs(r.signed_turns-r.gnss_signed_turns)-r.turn_error)<1e-8
    (ROOT/'evidence/plot_validation.json').write_text(json.dumps({
        'csv_files_checked':checked,'shared_observation_and_time_arrays_exact':True,
        'metric_rows':28,'turn_error_definition_verified':True,
        'new_simulator_runs':0,'posthoc_alignment':False,
        'display_translation':'Subtract the same recorded initial x/y from every trace in each trajectory panel.'
    },indent=2)+'\n')

if __name__=='__main__':
    validate(); figures(); tables(); appendix()
    print('Generated two main figures, seven appendix figures, and 28-row metric tables.')
