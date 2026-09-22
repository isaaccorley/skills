"""Matplotlib examples driven by seeded synthetic data for style evaluation."""

import csv
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm


def make_gallery(output: Path, assets: Path, seed: int) -> list[dict]:
    sys.path.insert(0,str(assets))
    from figstyle import ACCENT, COLORS, INK, SOFT, ORDERED, SIGNED, WARM, apply_style, export, tint, cell_text_color
    font=apply_style()
    rng=np.random.default_rng(seed)
    # E. Dense comparisons: each point is a single synthetic aggregate.
    methods=['Linear','Kernel','Forest','MLP','Small net','Wide net','Variant','Proposed']
    conditions=['Clean','Mild','Moderate','Strong','Severe']
    with (output/'category-data.csv').open('w') as stream:
        writer=csv.writer(stream)
        writer.writerow(['panel','method','condition','score','xlabel'])
        for pi,panel in enumerate(['Retrieval','Classification','Regression']):
            for mi,method in enumerate(methods):
                base=.60+.025*mi+rng.normal(0,.025)
                for ci,condition in enumerate(conditions):
                    value=base-.040*ci+rng.normal(0,.015)+.02*pi
                    writer.writerow([panel,method,condition,f'{value:.4f}','Score'])
    subprocess.run([sys.executable,str(assets/'category-comparison.py'),str(output/'category-data.csv'),
                    '--highlight','Proposed','--related','Variant','--output',str(output/'05-category')],check=True)
    # F. Raw samples and empirical distributions.
    names=['Reference','Variant','Proposed']
    colors=[COLORS['blue'],COLORS['brown'],ACCENT]
    shared=rng.normal(0,.045,40)
    samples=np.array([.69+shared+rng.normal(0,.02,40),.76+shared+rng.normal(0,.018,40),.83+shared+rng.normal(0,.016,40)])
    fig,axs=plt.subplots(1,2,figsize=(5.5,2.6))
    fig.subplots_adjust(left=.10,right=.985,bottom=.22,top=.86,wspace=.38)
    ax=axs[0]
    violin=ax.violinplot(samples.T,positions=[1,2,3],widths=.7,showextrema=False)
    for body,color in zip(violin['bodies'],colors,strict=True):
        body.set_facecolor(tint(color,.2)); body.set_edgecolor(color); body.set_alpha(1); body.set_linewidth(.6)
    for i,(sample,color) in enumerate(zip(samples,colors,strict=True),1):
        ax.scatter(i+rng.uniform(-.13,.13,len(sample)),sample,s=5,facecolors=color,alpha=.42,edgecolors='none',zorder=3)
        q1,median,q3=np.quantile(sample,[.25,.5,.75])
        ax.plot([i,i],[q1,q3],color=INK,linewidth=1.8,zorder=4)
        ax.scatter(i,median,s=11,c='white',edgecolors=INK,linewidths=.5,zorder=5)
    ax.set(xticks=[1,2,3],xticklabels=names,ylabel='Score',ylim=(.54,.98),title='(a) Sample distributions')
    ax.tick_params(axis='x',labelsize=6.7)
    ax=axs[1]
    for color,name,scale in zip(colors,names,[.23,.16,.11],strict=True):
        errors=np.sort(rng.gamma(1.5,scale,180))
        ax.step(errors,np.arange(1,181)/180,color=color,label=name,linewidth=1.1 if name=='Proposed' else .9)
    ax.set(xlabel='Absolute Error',ylabel='Fraction of Samples',xlim=(0,1.15),ylim=(0,1.02),title='(b) Error distributions')
    ax.legend(loc='lower right',fontsize=6.7)
    export(fig,output/'06-distributions'); plt.close(fig)
    np.savetxt(output/'distribution-data.csv',samples.T,delimiter=',',header=','.join(names),comments='')
    # G. Values and changes, both annotated so color is not the only encoding.
    scores=rng.uniform(.64,.84,(4,6))+np.arange(4)[:,None]*.025
    delta=rng.normal(.018,.045,(4,6)); delta[-1]+= .03
    fig,axs=plt.subplots(1,2,figsize=(5.5,2.65))
    fig.subplots_adjust(left=.13,right=.985,bottom=.31,top=.85,wspace=.27)
    for ax,values,title,cmap,norm in zip(axs,[scores,delta],['(a) Accuracy','(b) Change from baseline'],
                                       [WARM,SIGNED],[plt.Normalize(.60,.95),TwoSlopeNorm(vmin=-.12,vcenter=0,vmax=.12)],strict=True):
        im=ax.imshow(values,cmap=cmap,norm=norm,aspect='auto')
        ax.grid(False)
        ax.spines[['left','bottom']].set_visible(False)
        ax.set(xticks=np.arange(6),xticklabels=['A','B','C','D','E','F'],title=title,xlabel='Dataset')
        ax.set_yticks(np.arange(4),['Linear','Kernel','Variant','Proposed'] if ax is axs[0] else [])
        ax.tick_params(length=0)
        for (row,col),value in np.ndenumerate(values):
            rgba=cmap(norm(value))
            label=f'{value:.2f}' if ax is axs[0] else ('0.00' if abs(value)<.005 else f'{value:+.2f}')
            ax.text(col,row,label,ha='center',va='center',fontsize=7.2 if ax is axs[0] else 6.4,color=cell_text_color(rgba))
        ax.set_xticks(np.arange(-.5,6,1),minor=True); ax.set_yticks(np.arange(-.5,4,1),minor=True)
        ax.grid(which='minor',color='white',linewidth=1.2); ax.tick_params(which='minor',length=0)
        pos=ax.get_position()
        cax=fig.add_axes([pos.x0,.10,pos.width,.045])
        cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[.6,.75,.9] if ax is axs[0] else [-.12,0,.12])
        cb.outline.set_visible(False); cb.ax.tick_params(labelsize=6.5,length=2,width=.4)
    export(fig,output/'07-heatmaps'); plt.close(fig)
    np.savez(output/'heatmap-data.npz',scores=scores,change=delta)
    # H. Two measurements share scale; residuals have a separate zero-centered scale.
    xy=np.linspace(-100,100,160); xx,yy=np.meshgrid(xy,xy)
    field=np.zeros_like(xx)
    for _ in range(10):
        x0,y0=rng.uniform(-100,100,2); sx,sy=rng.uniform(15,50,2)
        field+=rng.uniform(.2,1.2)*np.exp(-((xx-x0)/sx)**2-((yy-y0)/sy)**2)
    field/=field.max()
    disturbance=.07*np.sin(xx/16)*np.cos(yy/23)+rng.normal(0,.012,xx.shape)
    predicted=np.clip(field+disturbance,0,1)
    residual=predicted-field
    fig,axs=plt.subplots(1,3,figsize=(5.5,2.35))
    fig.subplots_adjust(left=.09,right=.99,bottom=.32,top=.86,wspace=.12)
    images=[]
    for i,(ax,array,title) in enumerate(zip(axs,[field,predicted,residual],['(a) Reference field','(b) Predicted field','(c) Residual'],strict=True)):
        im=ax.imshow(array,origin='lower',extent=(-100,100,-100,100),cmap=WARM if i<2 else SIGNED,
                     vmin=0 if i<2 else -.12,vmax=1 if i<2 else .12,rasterized=True)
        images.append(im); ax.grid(False)
        ax.set(xticks=[-100,0,100],yticks=[-100,0,100],xlabel='x (km)',title=title)
        ax.tick_params(labelsize=6)
        if i: ax.set_yticklabels([])
        else: ax.set_ylabel('y (km)',fontsize=8)
    a,b=axs[0].get_position(),axs[1].get_position()
    cax=fig.add_axes([a.x0,.12,b.x1-a.x0,.04]); cb=fig.colorbar(images[0],cax=cax,orientation='horizontal',ticks=[0,.5,1])
    cb.set_label('Normalized magnitude',fontsize=7,labelpad=2); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=6,length=2)
    a=axs[2].get_position(); cax=fig.add_axes([a.x0,.12,a.width,.04])
    cb=fig.colorbar(images[2],cax=cax,orientation='horizontal',ticks=[-.12,0,.12]); cb.set_label('Signed error',fontsize=7,labelpad=2)
    cb.outline.set_visible(False); cb.ax.tick_params(labelsize=6,length=2)
    export(fig,output/'08-fields'); plt.close(fig)
    np.savez(output/'field-data.npz',x=xy,reference=field,predicted=predicted)
    (output/'font.txt').write_text(font+'\n')
    return [
        dict(id='05-category',title='E · Category comparison',backend='Python / Matplotlib',caption='Synthetic aggregate scores for eight methods and five ordered conditions. Focus: row alignment, coral emphasis, method labels, and the shared legend strip.'),
        dict(id='06-distributions',title='F · Sample and error distributions',backend='Python / Matplotlib',caption='Left: forty synthetic samples per method; violins, individual observations, and median/interquartile markers. Right: empirical CDFs of 180 synthetic errors per method.'),
        dict(id='07-heatmaps',title='G · Scores and signed changes',backend='Python / Matplotlib',caption='Seeded random score matrices. Sequential colors for magnitude, a zero-centered diverging scale for signed change, and explicit numeric annotations.'),
        dict(id='08-fields',title='H · Spatial fields and residuals',backend='Python / Matplotlib',caption='Synthetic Cartesian fields. Reference and prediction share one magnitude scale; residuals use a separate signed scale. Focus: raster/vector balance, colorbars, and panel packing.'),
    ]
