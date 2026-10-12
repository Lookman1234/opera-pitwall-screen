#!/usr/bin/env python3
"""Step 1b: find wall outlines and stable ground automatically from the Copernicus 30 m elevation model.

Plain-language header: for each site with a pit_center in config/sites.yaml and no
hand-drawn walls file, this step downloads the free elevation model, marks steep
ground near the pit as wall (named by the way it faces and the side of the pit it
is on), marks gentle ground in a ring outside as candidate stable ground, and
draws a preview map (paper/figures/<site>_auto_walls.png) for you to check.

Outputs: data/processed/<site>/auto_walls.npz, and config/sites/<site>_walls.auto.geojson
when rasterio is installed (open it at https://geojson.io to inspect or edit; rename
it to <site>_walls.geojson to make your edited version the one that is used).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LightSource  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import dem, geo  # noqa: E402
from pitwall.util import load_config, site_dir  # noqa: E402

INK, INK2, SURF, BLUE, ORANGE = "#0b0b0b", "#52514e", "#fcfcfb", "#2a78d6", "#eb6834"


def guess_epsg(lon, lat):
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def build(site, z, x, y, epsg, p):
    cx, cy = geo.lonlat_to_utm(site["pit_center"][0], site["pit_center"][1], epsg)
    r = float(site["pit_radius_m"])
    masks, props = dem.auto_walls(z, x, y, (float(cx), float(cy)), r, p.get("auto_wall_slope_min_deg", 25.0))
    stable = dem.auto_stable(z, x, y, (float(cx), float(cy)), r + p.get("auto_stable_gap_m", 500.0),
                             r + p.get("auto_stable_width_m", 2000.0), p.get("auto_stable_slope_max_deg", 10.0))
    names = sorted(masks)
    labels = np.zeros(z.shape, np.int16)
    for i, n in enumerate(names):
        labels[masks[n]] = i + 1
    return names, labels, props, stable, (float(cx), float(cy), r)


def preview(site, z, x, y, names, labels, props, stable, centre, aliases, out, final, pits=None):
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(np.nan_to_num(z, nan=np.nanmean(z)), vert_exag=2, dx=30, dy=30)
    ext = [(x[0] - centre[0]) / 1000, (x[-1] - centre[0]) / 1000, (y[-1] - centre[1]) / 1000, (y[0] - centre[1]) / 1000]
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(hs, cmap="Greys_r", extent=ext, origin="upper", alpha=0.9)
    ax.imshow(np.where(stable, 1.0, np.nan), cmap=matplotlib.colors.ListedColormap([ORANGE]), extent=ext,
              origin="upper", alpha=0.35, interpolation="nearest")
    ax.imshow(np.where(labels > 0, 1.0, np.nan), cmap=matplotlib.colors.ListedColormap([BLUE]), extent=ext,
              origin="upper", alpha=0.6, interpolation="nearest")
    xx, yy = np.meshgrid(x, y)
    alias_of = {v: k for k, v in (aliases or {}).items()}
    xk, yk = (x - centre[0]) / 1000, (y - centre[1]) / 1000
    for i, n in enumerate(names):
        m = labels == i + 1
        ax.contour(xk, yk, m.astype(float), levels=[0.5], colors=[INK], linewidths=0.5)
        if pits is not None:
            continue                       # district mode: label pits, not every wall section
        lx, ly = (xx[m].mean() - centre[0]) / 1000, (yy[m].mean() - centre[1]) / 1000
        txt = n.replace("faces_", "") + (f"\n= {alias_of[n]}" if n in alias_of else "")
        ax.text(lx, ly, txt, fontsize=7, ha="center", va="center", color=INK,
                bbox=dict(boxstyle="round,pad=0.15", fc=SURF, ec="none", alpha=0.8))
    for pt in pits or []:
        ax.text(xk[int(round(pt["ix"]))], yk[int(round(pt["iy"]))], f"pit {pt['pit']}", fontsize=9,
                fontweight="bold", ha="center", va="center", color=INK,
                bbox=dict(boxstyle="round,pad=0.2", fc=SURF, ec=INK, lw=0.6))
    t = np.linspace(0, 2 * np.pi, 200)
    if centre[2] > 0:
        ax.plot(centre[2] / 1000 * np.sin(t), centre[2] / 1000 * np.cos(t), color=INK2, lw=0.8, ls="--")
    ax.set_xlabel("Easting from pit centre (km)")
    ax.set_ylabel("Northing from pit centre (km)")
    ax.grid(False)
    ax.legend(handles=[matplotlib.patches.Patch(color=BLUE, alpha=0.6, label="Wall section (slope >= 25 deg). Label W_E = faces west, on the east side"),
                       matplotlib.patches.Patch(color=ORANGE, alpha=0.35, label="Candidate stable ground (slope <= 10 deg)"),
                       plt.Line2D([], [], color=INK2, ls="--", label="Search radius around pit centre")],
              loc="upper left", bbox_to_anchor=(0, -0.08), frameon=False, fontsize=8)
    ax.set_title(f"{site['name']}: automatic wall outlines\nElevation: Copernicus GLO-30 (acquired about 2011-2015)",
                 fontsize=10, loc="left")
    fig.tight_layout()
    if not final:
        fig.text(0.99, 0.995, "DRAFT - unverified", ha="right", va="top", fontsize=9, color="#b00020", fontweight="bold")
    fig.savefig(out, dpi=200)
    plt.close(fig)


def district(root, s, z, x, y, epsg, p, figs, final):
    """No pit centre given: find every pit in the box and outline the walls of each.

    Wall names get a pit prefix (pit3_faces_S_N). Events stay unmatched until the reported
    pit is identified on the preview map and its number is put in wall_aliases.
    """
    pit_lab, pits = dem.find_pits(z)
    names, labels, props = [], np.zeros(z.shape, np.int16), {}
    stable = np.zeros(z.shape, bool)
    for pt in pits:
        cx, cy = float(x[int(round(pt["ix"]))]), float(y[int(round(pt["iy"]))])
        r = pt["radius_m"] * 1.3 + 150
        m, pr = dem.auto_walls(z, x, y, (cx, cy), r, p.get("auto_wall_slope_min_deg", 25.0))
        for k in sorted(m):
            n = f"pit{pt['pit']}_{k}"
            names.append(n)
            labels[m[k] & (labels == 0)] = len(names)
            props[n] = pr[k] | {"wall_id": n}
        stable |= dem.auto_stable(z, x, y, (cx, cy), r + p.get("auto_stable_gap_m", 500.0),
                                  r + p.get("auto_stable_width_m", 2000.0), p.get("auto_stable_slope_max_deg", 10.0))
    for pt in pits:   # stable ground never inside any pit
        cx, cy = float(x[int(round(pt["ix"]))]), float(y[int(round(pt["iy"]))])
        xx, yy = np.meshgrid(x, y)
        stable &= np.hypot(xx - cx, yy - cy) > pt["radius_m"] * 1.3 + 650
    out = site_dir(root, "processed", s["id"])
    np.savez_compressed(os.path.join(out, "auto_walls.npz"), labels=labels, names=np.array(names),
                        aspect=np.array([props[n]["aspect_deg"] for n in names]),
                        slope=np.array([props[n]["slope_deg"] for n in names]),
                        stable=stable, x=x, y=y, epsg=epsg, dem=z)
    with open(os.path.join(out, "pits_found.json"), "w") as f:
        json.dump([{k: v for k, v in pt.items() if k != "label"} | {
            "lon_lat": [float(v) for v in geo.utm_to_lonlat(float(x[int(round(pt["ix"]))]),
                                                            float(y[int(round(pt["iy"]))]), epsg)]}
            for pt in pits], f, indent=2)
    write_geojson(os.path.join(root, "config", "sites", f"{s['id']}_walls.auto.geojson"),
                  labels, names, props, x, y, epsg)
    centre = (float(x.mean()), float(y.mean()), 0.0)
    preview(s | {"name": s["name"] + " (all pits found)"}, z, x, y, names, labels, props, stable, centre,
            s.get("wall_aliases"), os.path.join(figs, f"{s['id']}_auto_walls.png"), final, pits=pits)
    print(f"{s['id']}: district mode, {len(pits)} pits, {len(names)} wall sections; "
          "identify the reported pit on the preview, then set pit_center or wall_aliases")


def write_geojson(path, labels, names, props, x, y, epsg):
    try:
        from rasterio import features, transform  # type: ignore
    except ImportError:
        return False
    tr = transform.from_origin(x[0] - 15, y[0] + 15, 30, 30)
    feats = []
    for geom, val in features.shapes(labels, mask=labels > 0, transform=tr):
        n = names[int(val) - 1]
        rings = []
        for ring in geom["coordinates"]:
            r = np.array(ring)
            lo, la = geo.utm_to_lonlat(r[:, 0], r[:, 1], epsg)
            rings.append([[round(float(a), 6), round(float(b), 6)] for a, b in zip(lo, la)])
        feats.append({"type": "Feature", "properties": props[n], "geometry": {"type": "Polygon", "coordinates": rings}})
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    sites, p = load_config(a.root)
    figs = os.path.join(a.root, "paper", "figures")
    os.makedirs(figs, exist_ok=True)
    for s in sites:
        if os.path.exists(os.path.join(a.root, s.get("walls") or "~")):
            print(f"{s['id']}: hand-drawn walls file present; automatic outlines not needed")
            continue
        lon_c = s["pit_center"][0] if s.get("pit_center") else (s["bbox"][0] + s["bbox"][2]) / 2
        lat_c = s["pit_center"][1] if s.get("pit_center") else (s["bbox"][1] + s["bbox"][3]) / 2
        epsg = s.get("epsg") or guess_epsg(lon_c, lat_c)
        z, x, y = dem.fetch_dem_utm(s["bbox"], epsg)
        if not s.get("pit_center"):
            district(a.root, s, z, x, y, epsg, p, figs, a.final)
            continue
        import datetime as _dt
        with open(os.path.join(a.root, "data", "raw", "PROVENANCE.txt"), "a") as f:
            for u in dem.tile_urls(s["bbox"]):
                f.write(f"{_dt.date.today().isoformat()} | {os.path.basename(u)} | read remotely (window) | "
                        f"{u} | site={s['id']}; {dem.COPDEM_CREDIT}\n")
        names, labels, props, stable, centre = build(s, z, x, y, epsg, p)
        out = site_dir(a.root, "processed", s["id"])
        np.savez_compressed(os.path.join(out, "auto_walls.npz"), labels=labels, names=np.array(names),
                            aspect=np.array([props[n]["aspect_deg"] for n in names]),
                            slope=np.array([props[n]["slope_deg"] for n in names]),
                            stable=stable, x=x, y=y, epsg=epsg, dem=z)
        write_geojson(os.path.join(a.root, "config", "sites", f"{s['id']}_walls.auto.geojson"),
                      labels, names, props, x, y, epsg)
        preview(s, z, x, y, names, labels, props, stable, centre, s.get("wall_aliases"),
                os.path.join(figs, f"{s['id']}_auto_walls.png"), a.final)
        missing = [k for k, v in (s.get("wall_aliases") or {}).items() if v not in names]
        print(f"{s['id']}: {len(names)} wall sections, stable candidates {int(stable.sum())} px"
              + (f"; WARNING aliases point to missing walls: {missing}" if missing else ""))


if __name__ == "__main__":
    main()
