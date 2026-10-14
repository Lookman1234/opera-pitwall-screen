"""Wall and stable-ground masks for a site, from hand-drawn GeoJSON or the automatic outlines.

Plain-language header: one place that answers "which squares are wall, which are
stable ground?" for every later step. A hand-drawn or PitGeom file always wins;
otherwise the automatic outlines from step 1b are used. You do not need to open it.
"""

from __future__ import annotations

import os

import numpy as np

from . import geo
from .dem import regrid_nearest


def auto_path(root, site):
    return os.path.join(root, "data", "processed", site["id"], "auto_walls.npz")


def has_walls(root, site):
    return os.path.exists(os.path.join(root, site.get("walls") or "~missing~")) or os.path.exists(auto_path(root, site))


def wall_masks(root, site, x, y, epsg):
    """Return ({wall_id: bool mask}, {wall_id: properties}, source)."""
    p = os.path.join(root, site.get("walls") or "~missing~")
    if os.path.exists(p):
        feats = geo.load_geojson_polygons(p)
        masks = {str(f["properties"]["wall_id"]): geo.features_mask([f], x, y, epsg) for f in feats}
        props = {str(f["properties"]["wall_id"]): f["properties"] for f in feats}
        return masks, props, "file"
    z = np.load(auto_path(root, site), allow_pickle=False)
    names = [str(n) for n in z["names"]]
    masks = {n: regrid_nearest(z["labels"] == i + 1, z["x"], z["y"], x, y) for i, n in enumerate(names)}
    props = {n: {"wall_id": n, "aspect_deg": float(z["aspect"][i]), "slope_deg": float(z["slope"][i])}
             for i, n in enumerate(names)}
    return masks, props, "auto"


def stable_mask(root, site, x, y, epsg):
    p = os.path.join(root, site.get("stable") or "~missing~")
    if os.path.exists(p):
        return geo.features_mask(geo.load_geojson_polygons(p), x, y, epsg), "file"
    z = np.load(auto_path(root, site), allow_pickle=False)
    return regrid_nearest(z["stable"], z["x"], z["y"], x, y), "auto"


def refine_stable(stack, candidates, keep_frac=0.5):
    """Keep the candidate pixels whose whole-record trend is closest to the candidates' median.

    Automatic stable ground can include waste-dump tops or tailings that settle. Ranking
    candidates by the size of their long-term trend and keeping the quieter half removes
    most of those, without looking at the walls or the failure dates.
    """
    days = np.array([(d - stack.dates[0]).days for d in stack.dates], float) / 365.25
    sel = candidates.copy()
    d = stack.disp[:, sel]
    v = stack.valid[:, sel]
    seg = stack.segment
    main = seg == np.bincount(seg).argmax()
    t, d, v = days[main], d[main], v[main]
    w = v.astype(float)
    n = w.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        tm = (w * t[:, None]).sum(0) / n
        dm = (w * np.where(v, d, 0)).sum(0) / n
        vel = (w * (t[:, None] - tm) * (np.where(v, d, 0) - dm)).sum(0) / (w * (t[:, None] - tm) ** 2).sum(0)
    dev = np.abs(vel - np.nanmedian(vel))
    ok = np.isfinite(dev) & (n >= 0.5 * main.sum())
    if ok.sum() == 0:
        return candidates
    cut = np.nanquantile(dev[ok], keep_frac)
    keep = ok & (dev <= cut)
    out = np.zeros_like(candidates)
    out[np.nonzero(candidates)] = keep
    return out


def elevation(root, site, x, y):
    """DEM heights on the stack grid from step 1b's file, or None if step 1b has not run."""
    from .dem import regrid_values
    p = auto_path(root, site)
    if not os.path.exists(p):
        return None
    z = np.load(p, allow_pickle=False)
    if "dem" not in z:
        return None
    return regrid_values(z["dem"], z["x"], z["y"], x, y)
