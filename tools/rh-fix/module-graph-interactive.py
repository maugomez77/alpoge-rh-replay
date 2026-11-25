#!/usr/bin/env python3
"""Interactive WebGL view of the module import graph (Plotly, self-contained HTML).

Consumes the .npz/.json from module-graph-layout.py. Edges are sampled with a
weight favouring low-degree sources so the periphery stays visible; pan, zoom
and hover work in the browser.

Usage:
  module-graph-interactive.py [--npz PATH] [--meta PATH] [--out HTML]
                              [--max-edges 120000]
"""
import argparse
import json

import numpy as np
import plotly.graph_objects as go

PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--out", default="dashboard/rh-module-graph.html")
    ap.add_argument("--max-edges", type=int, default=120_000)
    args = ap.parse_args()

    d = np.load(args.npz)
    xy = d["xy"].astype(np.float64)
    edges = d["edges"].astype(np.int64)
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    names = meta["nodes"]
    roots = np.array([c.split(".")[0] for c in meta["clusters"]])
    uniq = sorted(set(roots.tolist()))
    color = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}

    deg = np.bincount(edges.ravel(), minlength=len(xy))
    rng = np.random.default_rng(42)
    w = 1.0 / np.sqrt(deg[edges[:, 0]] + 1.0)
    k = min(args.max_edges, len(edges))
    keep = rng.choice(len(edges), size=k, replace=False, p=w / w.sum())
    ek = edges[keep]

    fig = go.Figure()
    for r in uniq:
        sel = ek[roots[ek[:, 0]] == r]
        if len(sel) == 0:
            continue
        x = np.empty(len(sel) * 3)
        y = np.empty(len(sel) * 3)
        x[0::3] = xy[sel[:, 0], 0]
        x[1::3] = xy[sel[:, 1], 0]
        x[2::3] = np.nan
        y[0::3] = xy[sel[:, 0], 1]
        y[1::3] = xy[sel[:, 1], 1]
        y[2::3] = np.nan
        fig.add_trace(go.Scattergl(
            x=x, y=y, mode="lines", name=f"{r} edges",
            line=dict(color=color[r], width=0.5), opacity=0.22,
            hoverinfo="skip", showlegend=False))

    dmax = deg.max()
    for r in uniq:
        sel = np.where(roots == r)[0]
        fig.add_trace(go.Scattergl(
            x=xy[sel, 0], y=xy[sel, 1], mode="markers",
            name=r, marker=dict(
                size=(1.2 + 5.0 * np.sqrt(deg[sel] / dmax)).clip(1.2, 7),
                color=color[r], line=dict(width=0), opacity=0.9),
            text=[names[i] for i in sel],
            customdata=deg[sel],
            hovertemplate="<b>%{text}</b><br>degree %{customdata}<extra></extra>"))

    fig.update_layout(
        title=dict(text=f"Riemann Hypothesis formalization — import graph · "
                        f"{len(xy):,} modules · {len(edges):,} imports",
                   font=dict(color="#f2eaff", size=16)),
        template="plotly_dark",
        paper_bgcolor="#05030a", plot_bgcolor="#05030a",
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        legend=dict(bgcolor="rgba(5,3,10,0.6)", font=dict(color="#dbe7f5"),
                    itemsizing="constant", tracegroupgap=0),
        hovermode="closest",
        dragmode="pan",
    )
    fig.write_html(args.out, include_plotlyjs=True, full_html=True)
    print(f"wrote {args.out} ({k:,} of {len(edges):,} edges drawn)")


if __name__ == "__main__":
    main()
