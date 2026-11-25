#!/usr/bin/env python3
"""Interactive treemap + sunburst of the module tree (lines, modules, cost)."""
import argparse
import os

import plotly.graph_objects as go

DEFAULT_TIMES = "/Users/mauriciogomez/.rh-fix/times-rich.txt"


def load_times(path):
    t = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = line.split()
            if len(p) >= 4:
                try:
                    t[p[0]] = float(p[2])
                except ValueError:
                    pass
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--times", default=DEFAULT_TIMES)
    ap.add_argument("--treemap", default="dashboard/rh-module-treemap.html")
    ap.add_argument("--sunburst", default="dashboard/rh-module-sunburst.html")
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
    times = load_times(args.times)
    nodes = {"": {"lines": 0, "modules": 0, "cost": 0.0, "parent": "",
                  "label": "RH proof"}}
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    lines = sum(1 for _ in fh)
            except OSError:
                continue
            cost = times.get(m, 0.0)
            segs = m.split(".")
            parent = ""
            for i, seg in enumerate(segs):
                key = seg if not parent else parent + "." + seg
                if key not in nodes:
                    nodes[key] = {"lines": 0, "modules": 0, "cost": 0.0,
                                  "parent": parent, "label": seg}
                if i == len(segs) - 1:
                    nodes[key]["lines"] += lines
                    nodes[key]["modules"] += 1
                    nodes[key]["cost"] += cost
                parent = key

    keys = sorted(nodes, key=lambda k: (k.count("."), k))
    for k in reversed(keys):
        par = nodes[k]["parent"]
        if par:
            nodes[par]["lines"] += nodes[k]["lines"]
            nodes[par]["modules"] += nodes[k]["modules"]
            nodes[par]["cost"] += nodes[k]["cost"]

    ids = [k for k in keys]
    labels = [nodes[k]["label"] for k in keys]
    parents = [nodes[k]["parent"] for k in keys]
    values = [nodes[k]["lines"] for k in keys]
    costs = [round(nodes[k]["cost"], 1) for k in keys]
    mods = [nodes[k]["modules"] for k in keys]

    hover = ("<b>%{label}</b><br>%{value:,} lines · %{customdata[0]:,} modules"
             "<br>Σ median compile: %{customdata[1]:,.1f} s<extra></extra>")

    for kind, out in (("treemap", args.treemap), ("sunburst", args.sunburst)):
        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values,
            branchvalues="total",
            customdata=list(zip(mods, costs)),
            hovertemplate=hover,
            marker=dict(colors=costs, colorscale="Magma", showscale=True,
                        colorbar=dict(title=dict(text="Σ median s",
                                                 font=dict(color="#dbe7f5")),
                                      tickfont=dict(color="#dbe7f5"))),
            maxdepth=4 if kind == "treemap" else 6,
            textfont=dict(color="#f2eaff"),
        ))
        if kind == "sunburst":
            fig.data[0].update(marker_line=dict(width=0.5, color="#05030a"))
        fig.update_layout(
            title=dict(text=f"Riemann Hypothesis formalization — {kind}  ·  "
                            f"{len(keys)-1:,} namespaces  ·  {sum(mods):,} modules",
                       font=dict(color="#f2eaff", size=16)),
            template="plotly_dark", paper_bgcolor="#05030a",
            margin=dict(l=10, r=10, t=60, b=10),
        )
        fig.write_html(out, include_plotlyjs=True, full_html=True)
        print("wrote", out)


if __name__ == "__main__":
    main()
