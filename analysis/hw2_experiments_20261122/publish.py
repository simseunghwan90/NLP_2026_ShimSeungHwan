"""Create paper figures and tables from audited, matched replay artifacts (no simulation)."""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import build_data

ROOT=build_data.ROOT
DEST=ROOT/'paper/hw2_experiments_2026-11-22'
FIG=DEST/'figures'
MODELS=['Baseline','Previous','R6V2']
ORDER=MODELS+['GNSS']
COL={'GNSS':'#111111','Baseline':'#888888','Previous':'#d47713','R6V2':'#0072b2'}
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def style(m):
    return dict(color=COL[m],lw=1.3 if m=='GNSS' else 1.05,ls='--' if m=='Baseline' else '-',alpha=.95)


def xy(ax,case,detail=False,labels=True):
    ref=case['R6V2']['trajectory'];x0=ref.observed_x.iloc[0];y0=ref.observed_y.iloc[0]
    points=[]
    for m in ORDER:
        t=case['R6V2' if m=='GNSS' else m]['trajectory']
        x=t.observed_x-x0 if m=='GNSS' else t.native_x-x0
        y=t.observed_y-y0 if m=='GNSS' else t.native_y-y0
        ax.plot(x,y,**style(m))
        ax.plot(x.iloc[-1],y.iloc[-1],marker='x',ms=4,mew=.9,color=COL[m])
        if not detail or m!='Baseline':points.append(np.column_stack((x,y)))
    ax.plot(0,0,'o',ms=3.5,mfc='white',mec='black',zorder=15)
    p=np.concatenate(points);lo=p.min(0);hi=p.max(0);center=(lo+hi)/2
    span=max((hi-lo).max(),4)*1.15
    ax.set_xlim(center[0]-span/2,center[0]+span/2);ax.set_ylim(center[1]-span/2,center[1]+span/2)
    ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.18)
    if labels:ax.set_xlabel('East [m]');ax.set_ylabel('North [m]')
    ax.tick_params(labelsize=7 if labels else 5)


def timeseries(ax,case,kind,detail=False):
    for m in ORDER:
        d=case['R6V2' if m=='GNSS' else m]
        if kind=='speed':
            t=d['speed'];v=(t.speed_mps if m=='GNSS' else t.native_speed_mps)*3.6
        else:
            t=d['trajectory'];h=t.observed_heading_rad if m=='GNSS' else t.native_heading_rad
            v=(h-h.iloc[0])/(2*np.pi)
        ax.plot(t.relative_s,v,**style(m))
    ax.set_xlabel('Time [s]');ax.set_ylabel('Speed [km/h]' if kind=='speed' else 'Signed turns [rev]')
    ax.grid(alpha=.18);ax.tick_params(labelsize=7)
    if detail:ax.set_ylim(-.08,2.4)


def legend(fig):
    handles=[Line2D([0],[0],label={'GNSS':'GNSS / INS','Baseline':'Baseline (initial)','Previous':'Previous','R6V2':'R6V2 (final)'}[m],**style(m)) for m in ['GNSS']+MODELS]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.51,.995),ncol=4,frameon=False,fontsize=8)


def export(fig,name):
    for ext in ['pdf','png']:fig.savefig(FIG/f'{name}.{ext}',dpi=240,facecolor='white')
    plt.close(fig)


def figures(data):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':8.5,'axes.labelsize':8,
        'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    FIG.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(2,3,figsize=(7.25,4.95),gridspec_kw={'height_ratios':[1.3,1]})
    cases=['LAT3_Apos_s2','LAT5_L_s1','LON5_Aneg_v50_s1']
    titles=['(a) Straight\nLAT3 A+ s2','(b) Circle\nLAT5 L s1','(c) Higher speed\nLON5 A− 50 s1']
    for i,(c,title) in enumerate(zip(cases,titles)):
        xy(axes[0,i],data[c]);axes[0,i].set_title(title,pad=7)
        timeseries(axes[1,i],data[c],'heading' if i==1 else 'speed')
    ins=axes[0,0].inset_axes([.51,.07,.45,.45]);xy(ins,data[cases[0]],detail=True,labels=False)
    ins.set_title('Detail',fontsize=6,pad=1)
    # Preserve the full Baseline heading trace while exposing the two refined models.
    ins=axes[1,1].inset_axes([.49,.15,.47,.42]);timeseries(ins,data[cases[1]],'heading')
    ins.set_ylim(-.12,3);ins.set_xlabel('');ins.set_ylabel('');ins.tick_params(labelsize=5);ins.set_title('0–3 rev detail',fontsize=6,pad=1)
    legend(fig);fig.subplots_adjust(left=.075,right=.99,bottom=.085,top=.895,wspace=.45,hspace=.37)
    export(fig,'representative_replays')
    fig,axes=plt.subplots(2,2,figsize=(7.25,5.2),gridspec_kw={'height_ratios':[1.2,1]})
    for i,c in enumerate(['MOVE_LAT3_Apos_s1','MOVE_LAT3_Apos_s2']):
        xy(axes[0,i],data[c]);axes[0,i].set_title(f'({"a" if i==0 else "b"}) MOVE LAT3 A+ s{i+1}',pad=7)
        if i==0:
            ins=axes[0,i].inset_axes([.08,.53,.40,.40]);xy(ins,data[c],detail=True,labels=False)
            ins.set_title('Detail',fontsize=6,pad=1)
        timeseries(axes[1,i],data[c],'heading')
        ins=axes[1,i].inset_axes([.48,.14,.48,.46]);timeseries(ins,data[c],'heading',detail=True)
        ins.set_xlabel('');ins.set_ylabel('');ins.tick_params(labelsize=5);ins.set_title('0–2.4 rev detail',fontsize=6,pad=1)
    legend(fig);fig.subplots_adjust(left=.08,right=.98,bottom=.085,top=.90,wspace=.34,hspace=.32)
    export(fig,'move_diagnostics')


def tables(metrics):
    w=json.loads((ROOT/'experiments/evidence/2026-11-22_r5_stages/windows.json').read_text())
    groups=[('Stationary / self-check',lambda s:s.startswith(('LAT1_','SELFCHECK'))),
      ('LAT3: straight / zero point',lambda s:s.startswith('LAT3_')),
      ('LAT4/5: constant steering',lambda s:s.startswith(('LAT4_','LAT5_'))),
      ('LAT6: varying steering',lambda s:s.startswith('LAT6_')),
      ('LON2: pedal / acceleration',lambda s:s.startswith('LON2_')),
      ('LON3: braking ladder',lambda s:s.startswith('LON3_')),
      ('LON5/K: higher-speed straight',lambda s:s.startswith(('LON5_','LONK_'))),
      ('MOVE: repositioning',lambda s:s.startswith('MOVE_'))]
    inventory=[];seen=[]
    for title,pred in groups:
        cases=[k for k in w if pred(k)];seen+=cases
        inventory.append(dict(group=title,windows=len(cases),duration_min=sum(w[k]['duration_s'] for k in cases)/60,matched=sum(k in set(metrics.case) for k in cases)))
    assert len(seen)==len(set(seen))==len(w)==28
    inv=pd.DataFrame(inventory);inv.to_csv(DEST/'inventory.csv',index=False)
    lines=[r'\begin{table}[t]',r'\centering\small',r'\setlength{\tabcolsep}{3pt}',r'\begin{tabular}{@{}lrrr@{}}',r'\toprule',r'Test family & $n$ & Min. & $n_{3}$ \\',r'\midrule']
    for r in inv.itertuples():lines.append(f'{r.group} & {r.windows} & {r.duration_min:.2f} & {r.matched} '+r'\\')
    lines += [r'\midrule',f'Total & 28 & {inv.duration_min.sum():.2f} & 7 '+r'\\',r'\bottomrule',r'\end{tabular}',r'\caption{Development inventory: $n$ is the number of retained replay windows, not independent experiments. $n_3$ counts windows in the matched three-model comparison. Durations include retained starts and stops.}',r'\label{tab:exp_inventory}',r'\end{table}']
    (DEST/'inventory_table.tex').write_text('\n'.join(lines)+'\n')
    cols=['speed_rmse_mps','position_rmse_m','endpoint_m','turn_error']
    grouping=[('LAT3 (3-window mean)',[c for c in metrics.case.unique() if c.startswith('LAT3_')]),('LAT5 L s1',['LAT5_L_s1']),('LON5 A$-$ 50 s1',['LON5_Aneg_v50_s1']),('MOVE LAT3 A$+$ s1',['MOVE_LAT3_Apos_s1']),('MOVE LAT3 A$+$ s2',['MOVE_LAT3_Apos_s2'])]
    lines=[r'\begin{table*}[t]',r'\centering\small',r'\setlength{\tabcolsep}{7pt}',r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',r'Window / group & Model & Speed RMSE & Position RMSE & Endpoint error & Turn error \\',r' & & [m/s] & [m] & [m] & [rev] \\',r'\midrule']
    agg=[]
    for gi,(title,cases) in enumerate(grouping):
        for mi,m in enumerate(MODELS):
            subset=metrics[(metrics.case.isin(cases))&(metrics.model==m)];vals=subset[cols].mean()
            flagged=(subset.replay_status!='PASS').any();name=m+(r'$^{\dagger}$' if flagged else '')
            lines.append((title if mi==0 else '')+' & '+name+' & '+' & '.join(f'{vals[c]:.3f}' if c in ['speed_rmse_mps','turn_error'] else f'{vals[c]:.2f}' for c in cols)+r' \\')
            agg.append(dict(group=title,model=m,windows=len(cases),contact_flags=bool(flagged),**vals.to_dict()))
        if gi<len(grouping)-1:lines.append(r'\addlinespace[2pt]')
    lines += [r'\bottomrule',r'\end{tabular}',r'\caption{Matched development replays. Lower is better for all errors. LAT3 rows are equal-weight arithmetic means of three window-level metrics; other rows are individual windows. $^{\dagger}$Full rollouts completed, but the wheel-contact validation failed; these results remain failures and are included to expose Baseline behavior. These diagnostic metrics do not change the original validation status.}',r'\label{tab:exp_results}',r'\end{table*}']
    (DEST/'results_table.tex').write_text('\n'.join(lines)+'\n');pd.DataFrame(agg).to_csv(DEST/'grouped_metrics.csv',index=False)
    # Complete per-window supplement, derived from the same unrounded CSV.
    lines=[r'\begin{table}[t]',r'\centering\small',r'\setlength{\tabcolsep}{3pt}',r'\begin{tabular}{@{}lrrrr@{}}',r'\toprule',r'Model & $E_v$ & $E_p$ & $E_{\rm end}$ & $E_{\rm turn}$ \\',r' & [m/s] & [m] & [m] & [rev] \\',r'\midrule']
    for i,r in enumerate(metrics.itertuples()):
        if i%3==0:
            label=r.case.replace('_',' ')
            lines.append(r'\multicolumn{5}{@{}l}{\textit{'+label+f' ({r.duration_s:.2f} s)'+r'}} \\')
        name=r.model+(r'$^{\dagger}$' if r.replay_status!='PASS' else '')
        lines.append(f'{name} & {r.speed_rmse_mps:.3f} & {r.position_rmse_m:.2f} & {r.endpoint_m:.2f} & {r.turn_error:.3f} '+r'\\')
        if i%3==2 and i<len(metrics)-1:lines.append(r'\addlinespace[3pt]')
    lines += [r'\bottomrule',r'\end{tabular}',r'\caption{All seven windows and all three models, without aggregation. Group headers give window durations. The $\dagger$ marker has the same meaning as in Table~\ref{tab:exp_results}. Inputs and scoring intervals are identical across models.}',r'\label{tab:exp_complete}',r'\end{table}']
    (DEST/'complete_table.tex').write_text('\n'.join(lines)+'\n')
    def row(c,m):return metrics[(metrics.case==c)&(metrics.model==m)].iloc[0]
    calc={}
    for key,c in [('Circle','LAT5_L_s1'),('High','LON5_Aneg_v50_s1')]:
        calc[key+'SpeedReduction']=100*(1-row(c,'R6V2').speed_rmse_mps/row(c,'Previous').speed_rmse_mps)
    s=metrics[metrics.case.str.startswith('LAT3_')].groupby('model').speed_rmse_mps.mean()
    calc['StraightSpeedReduction']=100*(1-s['R6V2']/s['Previous'])
    (DEST/'numeric_macros.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+f'{v:.1f}'+r'\%}' for k,v in calc.items())+'\n')
    return calc


def main():
    DEST.mkdir(exist_ok=True)
    data,metrics=build_data.main();figures(data);calculated=tables(metrics)
    for f in ['metrics.csv','figure_sources.json','costs.json','windows.json']:
        shutil.copy2(build_data.OUT/'comparison'/f,DEST/f)
    provenance={'scope':'Development comparison; no heldout claim. No vehicle parameters changed for publication.',
      'source_inventory':'experiments/evidence/2026-11-22_r5_stages/windows.json',
      'selection_record':'experiments/evidence/2026-11-22_hw2_experiments/design.json',
      'baseline_audit':'experiments/evidence/2026-11-22_lat3_three_models/baseline_audit.json',
      'human_attribution':'paper/hw2_comparison_plan.json',
      'nuvo_evidence':'experiments/evidence/2026-11-22_nuvo_intake/received/REPORT.md',
      'matched_windows':len(metrics.case.unique()),'matched_rollouts':len(metrics),
      'validation_status_counts':metrics.replay_status.value_counts().to_dict(),
      'computed_percentages':calculated,
      'source_manuscripts':json.loads((ROOT/'paper/hw2_comparison_plan.json').read_text())['manuscript_sources']['files']}
    for item in provenance['source_manuscripts']:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
    (DEST/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    print('Published figures and numeric tables:',DEST)

if __name__=='__main__':main()
