"""Export fixed-time speed, rear-axle paths and cumulative-turn comparisons."""
import argparse
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/trial03_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import OUT

def main():
    p=argparse.ArgumentParser();p.add_argument('labels',nargs='+');a=p.parse_args()
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    d=pd.read_csv(OUT/'metrics.csv');cases=sorted(set(d[d.label.isin(a.labels)].session))
    for name in cases:
        base=OUT/'comparisons'/('R5_'+name+'.csv')
        if not base.exists():continue
        q=pd.read_csv(base);fig,axs=plt.subplots(1,3,figsize=(15,4.1),layout='constrained')
        axs[0].plot(q.relative_s,q.observed_v,'k',label='Recorded',lw=1.5)
        axs[1].plot(q.observed_x-q.observed_x.iloc[0],q.observed_y-q.observed_y.iloc[0],'k',lw=1.5)
        axs[1].plot(q.observed_x.iloc[-1]-q.observed_x.iloc[0],q.observed_y.iloc[-1]-q.observed_y.iloc[0],'kx',ms=8)
        oh=np.unwrap(q.observed_heading);axs[2].plot(q.relative_s,(oh-oh[0])/(2*np.pi),'k',lw=1.5)
        palette=['#1577b7','#299447','#be3b43','#8656aa','#886543','#da5caa']
        for index,label in enumerate(['R5']+a.labels):
            f=OUT/'comparisons'/(label+'_'+name+'.csv')
            if not f.exists():continue
            v=pd.read_csv(f);nh=np.unwrap(v.native_heading)
            color='#cd7c30' if label=='R5' else palette[(index-1)%len(palette)]
            axs[0].plot(v.relative_s,v.native_v,label=label,lw=1,color=color)
            axs[1].plot(v.native_x-q.observed_x.iloc[0],v.native_y-q.observed_y.iloc[0],lw=1,color=color)
            axs[1].plot(v.native_x.iloc[-1]-q.observed_x.iloc[0],v.native_y.iloc[-1]-q.observed_y.iloc[0],marker='x',ms=6,color=color)
            axs[2].plot(v.relative_s,(nh-nh[0])/(2*np.pi),lw=1,color=color)
        axs[0].set(xlabel='Recorded time from fixed start (s)',ylabel='Speed (m/s)');axs[0].legend(fontsize=8)
        axs[1].set(xlabel='Rear axle X (m)',ylabel='Rear axle Y (m)');axs[1].set_aspect('equal',adjustable='datalim')
        axs[2].set(xlabel='Recorded time from fixed start (s)',ylabel='Signed unwrapped turns')
        for ax in axs:ax.grid(alpha=.2)
        fig.suptitle(name+' | initial pose only; continuous replay; dt=0.01s')
        fig.savefig(folder/(name+'.png'),dpi=140);plt.close(fig)

if __name__=='__main__':main()
