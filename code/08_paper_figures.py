#!/usr/bin/env python3
"""Step 8: figures for the preprint, from paper/geometry.json and paper/synthetic_study.json.

Plain-language header: draws the preprint's charts. Every value comes from the files
steps 6 and 7 write, so the pictures cannot disagree with the numbers in the text.
Output: paper/preprint/fig_*.pdf (vector, for LaTeX) and .png previews.
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import detect, stack as stk, synthetic as syn  # noqa: E402
from pitwall.util import load_yaml  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "paper", "preprint")
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
RAMP = ["#e8f1fc", "#b9d3f5", "#86b3ec", "#5592e2", "#2a78d6", "#1b5cb0", "#123f7c"]   # one-hue sequential
W1 = 3.4   # single column width, inches

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8, "legend.fontsize": 7, "xtick.labelsize": 7,
    "ytick.labelsize": 7, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
})


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=220)
    plt.close(fig)


def fig_geometry(G):
    c = G["curves_inc39_slope45"]
    fig, ax = plt.subplots(figsize=(W1, 2.3))
    for pname, col, ls in [("ascending", BLUE, "-"), ("descending", ORANGE, "--")]:
        a = np.array(c[pname]["aspect"])
        p = np.array(c[pname]["p"])
        v = np.array(c[pname]["vis"])
        vis = np.where(v == "visible", np.abs(p), np.nan)
        hid = np.where(v != "visible", np.abs(p), np.nan)
        ax.plot(a, vis, color=col, lw=1.6, ls=ls, label=f"{pname.capitalize()} pass")
        ax.plot(a, hid, color=col, lw=0.8, ls=":", alpha=0.8)
        span = a[v != "visible"]
        if span.size:
            ax.axvspan(span.min(), span.max(), color=col, alpha=0.10, lw=0)
    for x, lab in [(270, "D East\n(Continental)"), (180, "North wall\n(Saga)")]:
        ax.axvline(x, color=INK2, lw=0.6)
        ax.text(x + 4, 1.02, lab, fontsize=6, va="top", ha="left", color=INK)
    ax.set_xlim(0, 359)
    ax.set_ylim(0, 1.05)
    ax.set_xticks([0, 45, 90, 135, 180, 225, 270, 315])
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    ax.set_xlabel("Direction the wall faces (aspect)")
    ax.set_ylabel(r"Recorded fraction $|\hat{d}\cdot\hat{l}|$")
    ax.legend(loc="lower left", frameon=False, ncol=2, bbox_to_anchor=(0, 1.0))
    save(fig, "fig_geometry")


def fig_example(seed=1003):
    p = load_yaml(os.path.join(ROOT, "config", "params.yaml"))
    dates, D, coh = syn.scene(seed, amp=0.02, precursor_days=120)
    walls, stable, layover, _, patch = syn.masks()
    s = stk.rebase(syn.granules(dates, D, coh), p["coherence_min"], False)
    stk.reference_to_stable(s, stable, p["stable_min_pixels"])
    rows, eps, vel = detect.detect(s, walls, stable, p, {"layover_shadow_mask": layover})
    import pandas as pd
    r = pd.DataFrame(rows)
    fig, axes = plt.subplots(2, 1, figsize=(W1, 3.3), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]})
    t = pd.to_datetime([d.isoformat() for d in s.dates])
    truth = D[:, patch].mean(1) - D[:, stable].mean(1)
    obs = np.array([np.nanmean(np.where(s.valid[i][patch], s.disp[i][patch], np.nan)) for i in range(len(t))])
    ax = axes[0]
    ax.plot(t, 100 * truth, color=INK2, lw=1.0, label="Simulated truth (patch mean)")
    ax.plot(t, 100 * obs, color=BLUE, lw=1.4, marker="o", ms=1.8, label="Recovered (valid pixels)")
    ax.set_ylabel("LOS displacement (cm)")
    ax.legend(frameon=False, loc="upper left", fontsize=6)
    ax = axes[1]
    for wid, col, lab in [("E", BLUE, "East wall (creep)"), ("N", AQUA, "North wall (stable)")]:
        w = r[r.wall_id == wid]
        ax.plot(pd.to_datetime(w.date), 100 * w.max_abs_vel_m_per_yr.astype(float), color=col, lw=1.4, label=lab)
    thr = r[r.wall_id == "E"]
    ax.plot(pd.to_datetime(thr.date), 100 * thr.threshold_m_per_yr.astype(float), color=INK2, lw=0.9, ls="--",
            label="Alert threshold")
    for e in eps:
        if e["wall_id"] not in ("E", "N"):
            continue
        ax.axvspan(pd.to_datetime(e["raised_date"]), pd.to_datetime(e["end_date"]) + pd.Timedelta(days=12),
                   color=ORANGE if e["wall_id"] == "E" else AQUA, alpha=0.25, lw=0)
    for a_ in axes:
        a_.axvline(pd.to_datetime(syn.failure_date().isoformat()), color=INK, lw=1.0)
        a_.axvline(pd.to_datetime(syn.failure_date().isoformat()) - pd.Timedelta(days=120), color=INK2, lw=0.6, ls=":")
    ax.set_ylabel("Fastest patch speed (cm/yr)")
    ax.legend(frameon=False, loc="upper right", fontsize=6)
    ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    save(fig, "fig_example")
    n_north = sum(1 for e in eps if e["wall_id"] == "N")
    n_south = sum(1 for e in eps if e["wall_id"] == "S")
    lead = None
    for e in eps:
        if e["wall_id"] == "E":
            lead = (syn.failure_date() - pd.to_datetime(e["raised_date"]).date()).days
            break
    return {"seed": seed, "lead_days": lead, "north_alerts": n_north, "south_alerts": n_south, "episodes": eps}


def _grid_panel(ax, A, title):
    amps = sorted({a["amp"] for a in A})
    pres = sorted({a["precursor"] for a in A})
    M = np.array([[next(a["rate"] for a in A if a["amp"] == am and a["precursor"] == pr) for am in amps] for pr in pres])
    L = [[next(a["lead"]["median"] for a in A if a["amp"] == am and a["precursor"] == pr) for am in amps] for pr in pres]
    im = ax.imshow(M, cmap=matplotlib.colors.ListedColormap(RAMP), vmin=0, vmax=1, origin="lower", aspect="auto")
    for i in range(len(pres)):
        for j in range(len(amps)):
            lead = L[i][j]
            txt = f"{100 * M[i, j]:.0f}%" + (f"\n{lead:.0f} d" if lead is not None else "")
            ax.text(j, i, txt, ha="center", va="center", fontsize=6.5, color="white" if M[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(amps)))
    ax.set_xticklabels([f"{100 * a:g}" for a in amps])
    ax.set_yticks(range(len(pres)))
    ax.set_yticklabels([str(p) for p in pres])
    ax.set_xlabel("Creep scale $A$ (cm)")
    ax.set_title(title, loc="left")
    ax.grid(False)
    return im


def fig_grid(S):
    fig = plt.figure(figsize=(7.0, 2.25))
    a0 = fig.add_axes([0.07, 0.2, 0.40, 0.68])
    a1 = fig.add_axes([0.52, 0.2, 0.40, 0.68], sharey=a0)
    cax = fig.add_axes([0.94, 0.2, 0.012, 0.68])
    _grid_panel(a0, S["A_grid"], "(a) Without stratified-delay correction")
    im = _grid_panel(a1, S["corrected"]["A_grid"], "(b) With stratified-delay correction")
    a0.set_ylabel("Precursor duration (days)")
    plt.setp(a1.get_yticklabels(), visible=False)
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Warned before failure", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    save(fig, "fig_grid")


def fig_tradeoff(S):
    fig, ax = plt.subplots(figsize=(W1, 2.3))
    for D, col, lab, ls in [(S, BLUE, "Without correction", "-"), (S["corrected"], ORANGE, "With correction", "--")]:
        K = D["k_tradeoff"]
        x = [k["false_alerts"]["per_wall_year"] for k in K]
        y = [100 * k["warned"]["rate"] for k in K]
        ax.plot(x, y, color=col, lw=1.6, ls=ls, marker="o", ms=4, label=lab)
        for k, xi, yi in zip(K, x, y):
            if k["k_sigma"] in (2.0, 3.0, 4.0):
                off = (4, -9) if col == BLUE else (-12, 4)
                ax.annotate(f"$k$={k['k_sigma']:g}", (xi, yi), xytext=off, textcoords="offset points", fontsize=6,
                            color=col)
    ax.set_xlabel("Alerts without an event (per wall-year, no-creep scenes)")
    ax.set_ylabel("Warned before failure (%)")
    ax.set_ylim(0, 100)
    ax.set_xlim(left=-0.03)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "fig_tradeoff")


def fig_null(S):
    fig, ax = plt.subplots(figsize=(W1, 2.1))
    seas = sorted({b["seasonal"] for b in S["B_null"]})
    for D, k, col, ls, lab in [(S, 3.0, BLUE, "-", "Without correction, $k=3$"),
                               (S, 4.0, AQUA, ":", "Without correction, $k=4$"),
                               (S["corrected"], 3.0, ORANGE, "--", "With correction, $k=3$")]:
        y = [next(b["per_wall_year"] for b in D["B_null"] if b["seasonal"] == s_ and b["k_sigma"] == k) for s_ in seas]
        ax.plot([1e5 * s_ for s_ in seas], y, color=col, lw=1.5, ls=ls, marker="o", ms=3.5, label=lab)
    ax.set_xlabel(r"Depth-correlated seasonal delay $c$ (mm per 100 m of depth)")
    ax.set_ylabel("Alerts per wall-year")
    ax.set_xticks([1e5 * s_ for s_ in seas])
    ax.set_xticklabels([f"{1e5 * s_:.1f}" for s_ in seas])
    cor = S["corrected"]["B_null"]
    n_al = sum(b["unmatched"] for b in cor if b["k_sigma"] == 3.0)
    wy = sum(b["wall_years"] for b in cor if b["k_sigma"] == 3.0)
    ax.text(2.6, 0.1, f"With correction: {n_al} alerts\nin {wy:,.0f} wall-years", fontsize=6.5, color=ORANGE,
            va="bottom", ha="left")
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(bottom=-0.05)
    save(fig, "fig_null")


def main():
    G = json.load(open(os.path.join(ROOT, "paper", "geometry.json")))
    S = json.load(open(os.path.join(ROOT, "paper", "synthetic_study.json")))
    fig_geometry(G)
    ex = fig_example()
    fig_grid(S)
    fig_tradeoff(S)
    fig_null(S)
    with open(os.path.join(ROOT, "paper", "example_run.json"), "w") as f:
        json.dump(ex, f, indent=1, default=str)
    print("figures written; example lead", ex["lead_days"])


if __name__ == "__main__":
    main()
