#!/usr/bin/env python3
"""Step 4: draw the figures.

Plain-language header: makes two pictures per pit and satellite track.
  1. Coverage map: which wall squares the satellite can watch (blue), which it sees
     but with too much noise (orange), and which it cannot see at all (aqua).
  2. Wall timelines: for each wall, the fastest movement seen on each date against
     the alert threshold, with alerts shaded and reported failures marked.
Figures carry a DRAFT stamp until you have checked everything; --final removes it.
Output: paper/figures/*.png
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import geo, stack as stk  # noqa: E402
from pitwall.util import load_config  # noqa: E402

# Reference palette (dataviz skill), first three categorical slots, which validate all-pairs
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
})


def stamp(fig, final):
    if not final:
        fig.text(0.99, 0.995, "DRAFT - unverified", ha="right", va="top", fontsize=9,
                 color="#b00020", fontweight="bold")


def coverage_map(site, frame, s, static, walls, stable, events, p, out, final):
    frac_valid = s.valid.mean(0)
    wall_any = np.zeros(frac_valid.shape, bool)
    for w in walls:
        wall_any |= geo.features_mask([w], s.x, s.y, s.epsg)
    cls = np.full(frac_valid.shape, np.nan)
    hidden = (static["layover_shadow_mask"] != 0) if static is not None and "layover_shadow_mask" in static \
        else np.zeros_like(wall_any)
    cls[wall_any] = 0
    cls[wall_any & (frac_valid < p["coherent_epoch_frac"])] = 1
    cls[wall_any & hidden] = 2
    ext = [(s.x[0] - s.x.mean()) / 1000, (s.x[-1] - s.x.mean()) / 1000,
           (s.y[-1] - s.y.mean()) / 1000, (s.y[0] - s.y.mean()) / 1000]
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    ax.imshow(frac_valid, cmap="Greys", vmin=0, vmax=1.6, extent=ext, origin="upper", alpha=0.35)
    ax.imshow(cls, cmap=ListedColormap([BLUE, ORANGE, AQUA]), vmin=-0.5, vmax=2.5, extent=ext,
              origin="upper", interpolation="nearest")
    for w in walls:
        for rings in w["polygons"]:
            rx, ry = geo.lonlat_to_utm(np.array(rings[0])[:, 0], np.array(rings[0])[:, 1], s.epsg)
            ax.plot((np.asarray(rx) - s.x.mean()) / 1000, (np.asarray(ry) - s.y.mean()) / 1000,
                    color=INK, lw=0.8)
            ax.text((np.mean(rx) - s.x.mean()) / 1000, (np.mean(ry) - s.y.mean()) / 1000,
                    str(w["properties"]["wall_id"]), ha="center", va="center", fontsize=9,
                    fontweight="bold", color=INK,
                    bbox=dict(boxstyle="round,pad=0.2", fc=SURF, ec="none", alpha=0.8))
    for st in stable:
        for rings in st["polygons"]:
            for ring in rings:
                rx, ry = geo.lonlat_to_utm(np.array(ring)[:, 0], np.array(ring)[:, 1], s.epsg)
                ax.plot((np.asarray(rx) - s.x.mean()) / 1000, (np.asarray(ry) - s.y.mean()) / 1000,
                        color=INK2, lw=0.8, ls="--")
    ev = events.dropna(subset=["lon", "lat"]) if len(events) else events
    for _, e in ev.iterrows():
        ex, ey = geo.lonlat_to_utm(float(e.lon), float(e.lat), s.epsg)
        ax.plot((ex - s.x.mean()) / 1000, (ey - s.y.mean()) / 1000, marker="X", ms=10,
                mfc=INK, mec=SURF, mew=1.5)
        ax.annotate(str(e.event_id), ((ex - s.x.mean()) / 1000, (ey - s.y.mean()) / 1000),
                    xytext=(6, 6), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Easting from centre (km)")
    ax.set_ylabel("Northing from centre (km)")
    ax.set_aspect("equal")
    ax.grid(False)
    ax.legend(handles=[Patch(color=BLUE, label="Watched (coherent)"),
                       Patch(color=ORANGE, label=f"Seen but noisy (valid < {p['coherent_epoch_frac']:.0%} of dates)"),
                       Patch(color=AQUA, label="Not visible (layover or shadow)"),
                       plt.Line2D([], [], color=INK2, ls="--", label="Stable reference ground")],
              loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, frameon=False, fontsize=8)
    ax.set_title(f"{site['name']}  |  track {frame}\nWall visibility, {s.dates[0]} to {s.dates[-1]}",
                 fontsize=10, loc="left")
    fig.tight_layout()
    stamp(fig, final)
    fig.savefig(os.path.join(out, f"{site['id']}_{frame}_coverage.png"), dpi=200)
    plt.close(fig)


def timelines(site, frame, epochs, alerts, events, out, final):
    walls = list(dict.fromkeys(epochs.wall_id))
    fig, axes = plt.subplots(len(walls), 1, figsize=(7.2, 1.7 * len(walls) + 0.6), sharex=True, squeeze=False)
    ymax = np.nanmax(epochs.max_abs_vel_m_per_yr.to_numpy(dtype=float) * 100) if len(epochs) else 1
    for ax, wid in zip(axes[:, 0], walls):
        e = epochs[epochs.wall_id == wid]
        d = pd.to_datetime(e.date)
        ax.plot(d, e.max_abs_vel_m_per_yr.astype(float) * 100, color=BLUE, lw=2, label="Fastest wall patch")
        ax.plot(d, e.threshold_m_per_yr.astype(float) * 100, color=INK2, lw=1, ls="--", label="Alert threshold")
        for _, a in alerts[(alerts.wall_id == wid)].iterrows():
            end = max(pd.to_datetime(a.end_date), pd.to_datetime(a.raised_date) + pd.Timedelta(days=12))
            ax.axvspan(pd.to_datetime(a.raised_date), end, color=ORANGE, alpha=0.25, lw=0)
        for _, ev in events[(events.assigned_wall == wid)].iterrows():
            ax.axvline(pd.to_datetime(ev.date), color=INK, lw=1.5)
            ax.text(pd.to_datetime(ev.date), ymax * 1.02, f" {ev.event_id}: {ev.outcome.replace('_', ' ')}",
                    fontsize=8, va="top", ha="left")
        ax.set_ylim(0, ymax * 1.1)
        ax.set_ylabel(f"Wall {wid}\ncm/yr", fontsize=8)
    axes[0, 0].legend(handles=[plt.Line2D([], [], color=BLUE, lw=2, label="Fastest wall patch (line-of-sight speed)"),
                               plt.Line2D([], [], color=INK2, ls="--", label="Alert threshold"),
                               Patch(color=ORANGE, alpha=0.25, label="Alert raised"),
                               plt.Line2D([], [], color=INK, lw=1.5, label="Reported failure")],
                      loc="lower left", bbox_to_anchor=(0, 1.15), ncol=2, frameon=False, fontsize=8)
    axes[-1, 0].xaxis.set_major_locator(mdates.YearLocator())
    axes[-1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(f"{site['name']}  |  track {frame}: wall movement against the alert rule",
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    stamp(fig, final)
    fig.savefig(os.path.join(out, f"{site['id']}_{frame}_timelines.png"), dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--final", action="store_true", help="remove DRAFT stamps (only after verification)")
    a = ap.parse_args()
    sites, p = load_config(a.root)
    proc = os.path.join(a.root, "data", "processed")
    out = os.path.join(a.root, "paper", "figures")
    os.makedirs(out, exist_ok=True)
    ev_all = pd.read_csv(os.path.join(proc, "event_outcomes_by_track.csv"), dtype={"wall_id": str})
    al_all = pd.read_csv(os.path.join(proc, "alerts.csv"), dtype={"wall_id": str})
    for site in sites:
        walls = geo.load_geojson_polygons(os.path.join(a.root, site["walls"]))
        stable = geo.load_geojson_polygons(os.path.join(a.root, site["stable"]))
        for sp in sorted(glob.glob(os.path.join(proc, site["id"], "F*_stack.npz"))):
            frame = os.path.basename(sp).split("_")[0]
            s = stk.load(sp)
            stp = sp.replace("_stack.npz", "_static.npz")
            static = dict(np.load(stp)) if os.path.exists(stp) else None
            ev = ev_all[(ev_all.site_id == site["id"]) & (ev_all.frame == frame)]
            al = al_all[(al_all.site_id == site["id"]) & (al_all.frame == frame)] if len(al_all) else al_all
            epochs = pd.read_csv(os.path.join(proc, site["id"], f"{frame}_epochs.csv"), dtype={"wall_id": str})
            coverage_map(site, frame, s, static, walls, stable, ev, p, out, a.final)
            timelines(site, frame, epochs, al, ev, out, a.final)
            print(f"figures: {site['id']} {frame}")


if __name__ == "__main__":
    main()
