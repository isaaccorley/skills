"""Seeded pgfplots examples and a generic schematic for visual review."""

from pathlib import Path
import shutil
import subprocess

import numpy as np


def write_csv(path, header, array):
    np.savetxt(path, array, delimiter=',', header=header, comments='', fmt='%.6f')


def compile_figure(output: Path, stem: str, body: str) -> None:
    document = r'''\documentclass[border=2pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{times,mathptmx,amsmath,amssymb,graphicx,xcolor}
\input{figure-style.tex}
\begin{document}
\begin{minipage}{5.5in}\centering
''' + body + '\n\\end{minipage}\n\\end{document}\n'
    (output / f'{stem}.tex').write_text(document)
    with (output / f'{stem}.log.txt').open('w') as log:
        subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'{stem}.tex'],
                       cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)


def make_gallery(output: Path, assets: Path, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    shutil.copy2(assets / 'figure-style.tex', output / 'figure-style.tex')
    shutil.copy2(assets / 'method-diagram.tex', output / 'method-diagram.tex')
    x = np.arange(0, 101, 10)
    for panel in ('train', 'shift'):
        for name,offset,tau in [('proposed',.89,29),('baseline',.83,35)]:
            if panel == 'train':
                truth = .42 + (offset-.42) * (1-np.exp(-x/tau))
            else:
                truth = offset - (x/100)**1.2 * (.22 if name=='proposed' else .35)
            runs = truth + rng.normal(0,.018,(8,len(x)))
            mean, sd = runs.mean(0), runs.std(0,ddof=1)
            write_csv(output/f'{panel}-{name}.csv','x,mean,low,high',np.c_[x,mean,mean-sd,mean+sd])
    axes=[]
    for panel,xlabel,title in [('train','Training Epoch','(a) Learning'),('shift','Corruption Severity (\\%)','(b) Robustness')]:
        content=rf'''\begin{{minipage}}{{0.485\linewidth}}\centering
\begin{{tikzpicture}}
\begin{{axis}}[paperaxis,faintgrid,height=2.15in,width=\linewidth,
 title={{{title}}},xlabel={{{xlabel}}},ylabel={{Accuracy}},
 xmin=0,xmax=100,ymin=.37,ymax=.93,ytick={{.4,.5,.6,.7,.8,.9}},
 legend style={{at={{(.03,.97)}},anchor=north west,font=\scriptsize}}]
'''
        for name,color,style in [('proposed','coral','focus'),('baseline','blue','comparison')]:
            content+=rf'''\addplot[name path={name}lo,draw=none,forget plot] table[x=x,y=low,col sep=comma] {{{panel}-{name}.csv}};
\addplot[name path={name}hi,draw=none,forget plot] table[x=x,y=high,col sep=comma] {{{panel}-{name}.csv}};
\addplot[{color}!13,draw=none,forget plot] fill between[of={name}lo and {name}hi];
\addplot[{style}] table[x=x,y=mean,col sep=comma] {{{panel}-{name}.csv}};
'''
            # Legend on the learning panel sits in vacant upper-left space.
            if panel=='train': content+=rf'\addlegendentry{{{name.title()}}}'+'\n'
        content+='\\end{axis}\n\\end{tikzpicture}\n\\end{minipage}'
        axes.append(content)
    compile_figure(output,'01-curves',r'\noindent '+r'\hfill'.join(axes))
    ablations=['Full','No gate','No skip','No norm','Small head']
    means=np.array([.84,.76,.79,.73,.80])+rng.normal(0,.008,5)
    shifted=means-rng.uniform(.06,.15,5)
    write_csv(output/'ablation.csv','x,standard,shifted,sd1,sd2',np.c_[np.arange(5),means,shifted,rng.uniform(.012,.025,5),rng.uniform(.017,.035,5)])
    compile_figure(output,'02-ablation',r'''\begin{tikzpicture}
\begin{axis}[paperaxis,faintgrid,ybar=1.5pt,width=.96\linewidth,height=2.35in,
 bar width=24pt,ymin=0,ymax=1,ytick={0,.2,.4,.6,.8,1},ylabel={Accuracy},
 xtick={0,1,2,3,4},xticklabels={Full,No gate,No skip,No norm,Small head},
 xmin=-.5,xmax=4.5,
 legend columns=2,legend style={at={(.5,1.10)},anchor=south}]
\addplot[draw=coral,fill=coral,line width=.4pt,error bars/.cd,y dir=both,y explicit,error bar style={ink!80,line width=.5pt}]
 table[x=x,y=standard,y error=sd1,col sep=comma] {ablation.csv};
\addlegendentry{Standard}
\addplot[draw=blue,fill=blue,line width=.4pt,error bars/.cd,y dir=both,y explicit,error bar style={ink!80,line width=.5pt}]
 table[x=x,y=shifted,y error=sd2,col sep=comma] {ablation.csv};
\addlegendentry{Shifted}
\end{axis}\end{tikzpicture}''')
    latency=np.array([6,12,22,34,55,86,130])
    quality=np.array([.63,.69,.77,.75,.82,.80,.88])+rng.normal(0,.004,7)
    names=['Tiny','Small','Proposed-S','Wide','Proposed-M','Deep','Proposed-L']
    parts=[r'''\begin{tikzpicture}
\begin{axis}[paperaxis,faintgrid,width=.96\linewidth,height=2.45in,
 tick label style={font=\fontsize{8}{9.6}\selectfont,ink},
 label style={font=\fontsize{10}{12}\selectfont,ink},
 xmode=log,xmin=4,xmax=195,ymin=.58,ymax=.95,
 xtick={5,10,20,50,100},xticklabels={5,10,20,50,100},
 ytick={.6,.7,.8,.9},xlabel={Latency (ms)},ylabel={Accuracy}]
''']
    frontier=[0,1,2,4,6]
    parts.append('\\addplot[coral!55,dashed,forget plot] coordinates {'+' '.join(f'({latency[i]},{quality[i]})' for i in frontier)+'};\n')
    for i,name in enumerate(names):
        ours=name.startswith('Proposed')
        parts.append(rf'\addplot[only marks,{"focus" if ours else "comparison"}] coordinates {{({latency[i]},{quality[i]})}};'+'\n')
        anchor,shift=('north',-5) if i in {3,5} else ('south',5)
        parts.append(rf'\node[font=\fontsize{{9}}{{10.8}}\selectfont,text={"coral" if ours else "blue"},anchor={anchor},yshift={shift}pt] at (axis cs:{latency[i]},{quality[i]}) {{{name}}};'+'\n')
    parts.append('\\end{axis}\\end{tikzpicture}')
    compile_figure(output,'03-tradeoff',''.join(parts))
    write_csv(output/'tradeoff.csv','latency,accuracy',np.c_[latency,quality])
    compile_figure(output,'04-diagram',r'\input{method-diagram.tex}')
    return [
        dict(id='01-curves',title='A · Learning and robustness',backend='TikZ / pgfplots',caption='Seeded synthetic accuracy curves. Means and ±1 SD across eight simulated runs; shared axes. Focus: line weights, markers, bands, and paired-panel spacing.'),
        dict(id='02-ablation',title='B · Compact solid bars',backend='TikZ / pgfplots',caption='Synthetic means and illustrative SD error bars for five variants under two conditions. Approved grouped-bar style: solid fills, narrow within-group gaps, and wider bars to reduce unused space.'),
        dict(id='03-tradeoff',title='C · Quality–cost trade-off',backend='TikZ / pgfplots',caption='Synthetic model measurements. Approved scatter style with larger point labels and axis text; the dashed guide joins nondominated points.'),
        dict(id='04-diagram',title='D · Method schematic',backend='TikZ',caption='Generic illustrative pipeline, not an experiment. Focus: drawn operations, stage headings, small math labels, and restrained colored fills.'),
    ]
