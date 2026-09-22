# LaTeX layouts

Input `figure-style.tex` in the document preamble. Load `graphicx`, `xcolor`,
`amsmath`, `amssymb`, and `subcaption` as needed. Use the project's engine and
body fonts. Keep reduced CSVs separate from figure geometry. Input paths resolve
from the LaTeX build directory.

For two panels supporting one comparison:

```latex
\begin{figure}[!t]
  \centering
  \begin{subfigure}{0.485\linewidth}\input{figs/panel-a}\end{subfigure}\hfill
  \begin{subfigure}{0.485\linewidth}\input{figs/panel-b}\end{subfigure}
  \caption{\textbf{Descriptive finding.} Left: ... Right: ... State aggregation.}
  \label{fig:comparison}
\end{figure}
```

For a plot beside a table, use top-aligned minipages with `\vspace{0pt}` and
separate captions. Set `\captionsetup{type=table}` locally in the table minipage.
Plot height 1.5 in is a useful starting point; align their top content baselines.

For a supporting plot inline with prose, use a right-side `wrapfigure` at
`0.48\textwidth`, around 1.55 in plot height. Tune the optional wrapped line count
after compilation; avoid section/page boundaries that make wrapping unstable.

For exported Python figures:

```latex
\begin{figure}[!t]
  \centering
  \includegraphics[width=\linewidth]{figs/results.pdf}
  \caption{\textbf{Descriptive finding.} Explain markers and measurement.}
  \label{fig:results}
\end{figure}
```

Dense category figures can use `0.9\linewidth` if their effective label sizes
remain readable. Measure cropped output width; do not assume it equals figsize.
Use `figure*` only for a figure spanning both columns of a two-column paper.
Print `\the\linewidth` at the insertion point when the width is uncertain.
