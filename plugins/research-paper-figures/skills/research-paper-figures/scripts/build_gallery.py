"""Build a synthetic figure gallery and a paper-width PDF proof.

Run: python build_gallery.py --output gallery-output [--seed 42]
Requires numpy, matplotlib, Pillow, pdflatex, and pdftoppm.
"""

import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from matplotlib.font_manager import FontProperties, findfont

from gallery_python import make_gallery as python_gallery
from gallery_tikz import make_gallery as tikz_gallery


def render(output: Path, stem: str) -> None:
    subprocess.run(['pdftoppm','-r','190','-png','-singlefile',f'{stem}.pdf',stem],cwd=output,check=True)


def make_proof(output: Path, entries: list[dict]) -> None:
    captions=[
        'The learning advantage persists under corruption. The proposed curve rises faster during training and degrades more gradually as corruption increases. Means and bands show eight simulated runs and $\\pm$1 SD.',
        'Each removed component reduces accuracy in this synthetic example. Input shift lowers scores across all variants, while the relative ordering is largely preserved. Bars show synthetic means with illustrative SD intervals.',
        'Higher accuracy comes with greater latency, but some models pay more without improving accuracy. The dashed guide joins nondominated synthetic measurements. Open squares identify comparison models, with larger direct labels for readability.',
        'Training learns a representation that is reused at inference. The encoder and adaptive head are optimized together, then frozen to produce predictions and uncertainty estimates. This is an illustrative architecture, not an experimental result.',
        'Condition sensitivity is visible within each method. Connecting the markers reveals how scores change as conditions become harder, which a single aggregate score would hide. All values are synthetic aggregates.',
        'The proposed method shifts scores upward and errors downward in this synthetic example. Left: 40 observations per method, with medians and interquartile ranges overlaid on violin densities. Right: empirical CDFs of 180 absolute errors per method.',
        'Absolute performance and improvement are different comparisons. A high score does not by itself establish a gain over the baseline. The panels separate synthetic accuracy from signed changes and annotate both directly.',
        'Similar broad patterns can conceal structured local errors. A separate residual panel reveals differences that are harder to see when comparing the two magnitude maps. The first two synthetic fields share a scale; errors use a zero-centered scale.',
    ]
    preamble=r'''\documentclass{article}
\usepackage[letterpaper,left=1.5in,right=1.5in,top=.7in,bottom=.7in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{times,mathptmx,graphicx,xcolor,caption}
\definecolor{soft}{HTML}{D8D3C6}
\definecolor{ink}{HTML}{241A18}
\color{ink}
\captionsetup{font=small,labelfont=bf}
\pagestyle{empty}
\begin{document}
'''
    pages=[]
    for entry,caption in zip(entries,captions,strict=True):
        first,rest=caption.split('. ',1)
        pages.append(r'\noindent {\small SYNTHETIC FIGURE STUDY}\hfill {\small '+entry['backend']+r'}\par\medskip'+'\n'+
                     r'\noindent{\Large\bfseries '+entry['title'].replace(' · ',' — ')+r'}\par\bigskip'+'\n'+
                     r'\begin{figure}[h]\centering'+'\n'+
                     r'\includegraphics[width=\linewidth]{'+entry['id']+r'.pdf}'+'\n'+
                     r'\caption{\textbf{'+first+r'.} '+rest+r'}'+'\n'+
                     r'\end{figure}\clearpage'+'\n')
        entry['paper_caption']=caption
    (output/'gallery.tex').write_text(preamble+''.join(pages)+'\\end{document}\n')
    with (output/'gallery-build.log').open('w') as log:
        subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','gallery.tex'],cwd=output,stdout=log,stderr=subprocess.STDOUT,check=True)


def make_contact_sheets(output: Path, entries: list[dict]) -> None:
    title_font=ImageFont.truetype(findfont(FontProperties(family='serif',weight='bold')),30)
    small_font=ImageFont.truetype(findfont(FontProperties(family='serif')),23)
    for batch in range(2):
        sheet=Image.new('RGB',(1800,1180),'white'); draw=ImageDraw.Draw(sheet)
        for index,entry in enumerate(entries[batch*4:batch*4+4]):
            col,row=index%2,index//2
            x,y=col*900+25,row*590+20
            draw.text((x,y),entry['title'],font=title_font,fill='#241a18')
            draw.text((x,y+39),entry['backend']+' · synthetic example',font=small_font,fill='#6e6e6e')
            pic=Image.open(output/(entry['id']+'.png')).convert('RGB')
            pic.thumbnail((850,470),Image.Resampling.LANCZOS)
            sheet.paste(pic,(x+(850-pic.width)//2,y+90+(470-pic.height)//2))
        sheet.save(output/f'gallery-{batch+1}.png')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    assets=Path(__file__).resolve().parents[1]/'assets'
    entries=tikz_gallery(output,assets,args.seed)+python_gallery(output,assets,args.seed+1)
    for entry in entries:
        render(output,entry['id'])
    make_proof(output,entries)
    make_contact_sheets(output,entries)
    (output/'gallery.json').write_text(json.dumps({'seed':args.seed,'figures':entries},indent=2)+'\n')
    print(f'Gallery ready: {output}/gallery.pdf')


if __name__=='__main__':
    main()
