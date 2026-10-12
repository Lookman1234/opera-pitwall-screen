"""Synthetic test pit with a known answer.

Plain-language header: this file invents a fake pit so we can check the code
finds what we planted. NOTHING HERE IS REAL DATA. The fake pit has four walls:

  E  a patch creeps faster and faster, then fails on 2018-07-15  -> should be WARNED
  N  fails suddenly on 2019-05-01 with no creep beforehand        -> should be MISSED
  W  creeps and fails on 2018-10-01, but the satellite cannot see
     this wall (hidden behind the slope)                          -> NOT OBSERVABLE
  S  never moves
  plus one event dated before the data starts                     -> NOT OBSERVABLE

The fake granules mimic OPERA's layout: displacement relative to a reference
date that resets every 15 acquisitions, a temporal-coherence layer, and noise
from the atmosphere (smooth, changes every date, partly tied to pit depth, as
real radar delay is) plus pixel noise.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
from scipy import ndimage

from pitwall import geo, stack as stk

EPSG = 32612
NX = NY = 120
PIX = 30.0
X0, Y0 = 400000.0, 4500000.0          # grid centre (fictional location)
START = dt.date(2017, 1, 6)
N_ACQ = 90
REVISIT = 12
MINISTACK = 15

EVENTS = [
    # id, wall_id (blank = locate by lon/lat), date, offset from centre (dx, dy) used for lon/lat
    ("E1", "", "2018-07-15", (750.0, 0.0)),
    ("N1", "N", "2019-05-01", None),
    ("W1", "W", "2018-10-01", None),
    ("S0", "S", "2016-03-01", None),
]
EXPECTED = {"E1": "warned", "N1": "missed", "W1": "not_observable", "S0": "not_observable"}


def grid():
    x = X0 + (np.arange(NX) - NX / 2 + 0.5) * PIX
    y = Y0 - (np.arange(NY) - NY / 2 + 0.5) * PIX           # north-up, y decreasing like real rasters
    return x, y


def sector_ring(az0, az1, r0=450.0, r1=1050.0, n=24):
    az = np.radians(np.linspace(az0, az1, n))
    outer = [(X0 + r1 * math.sin(a), Y0 + r1 * math.cos(a)) for a in az]
    inner = [(X0 + r0 * math.sin(a), Y0 + r0 * math.cos(a)) for a in az[::-1]]
    pts = outer + inner + [outer[0]]
    lon, lat = geo.utm_to_lonlat([p[0] for p in pts], [p[1] for p in pts], EPSG, use_pyproj=False)
    return [[float(a), float(b)] for a, b in zip(lon, lat)]


def square(h):
    pts = [(X0 - h, Y0 - h), (X0 + h, Y0 - h), (X0 + h, Y0 + h), (X0 - h, Y0 + h), (X0 - h, Y0 - h)]
    lon, lat = geo.utm_to_lonlat([p[0] for p in pts], [p[1] for p in pts], EPSG, use_pyproj=False)
    return [[float(a), float(b)] for a, b in zip(lon, lat)]


WALLS = {"N": (-45, 45, 180), "E": (45, 135, 270), "S": (135, 225, 0), "W": (225, 315, 90)}
# aspect = direction the wall face looks toward (into the pit): east wall faces west (270)


def walls_geojson():
    feats = []
    for wid, (a0, a1, aspect) in WALLS.items():
        feats.append({"type": "Feature",
                      "properties": {"wall_id": wid, "aspect_deg": aspect, "slope_deg": 45},
                      "geometry": {"type": "Polygon", "coordinates": [sector_ring(a0, a1)]}})
    return {"type": "FeatureCollection", "features": feats}


def stable_geojson():
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"name": "rim ring"},
        "geometry": {"type": "Polygon", "coordinates": [square(1750.0), square(1500.0)]}}]}


def _log_creep(t_days, ts, tf, amp):
    """Accelerating creep to failure (inverse velocity falls linearly), in metres."""
    out = np.zeros_like(t_days, dtype=float)
    on = (t_days >= ts) & (t_days < tf)
    tau = (t_days[on] - ts) / (tf - ts + 4.0)
    out[on] = -amp * np.log(1 - tau)
    out[t_days >= tf] = -amp * np.log(1 - (tf - ts) / (tf - ts + 4.0))
    return out


def truth(seed=7):
    """Return dates, true displacement [T,ny,nx] (m), coherence [T,ny,nx], layover mask."""
    rng = np.random.default_rng(seed)
    x, y = grid()
    xx, yy = np.meshgrid(x, y)
    r = np.hypot(xx - X0, yy - Y0)
    az = (np.degrees(np.arctan2(xx - X0, yy - Y0)) + 360) % 360
    depth = np.clip((1050 - r) / 600, 0, 1) * 300.0                 # m below rim
    dates = [START + dt.timedelta(days=REVISIT * i) for i in range(N_ACQ + 1)]
    days = np.array([(d - START).days for d in dates], float)
    T = len(dates)
    D = np.zeros((T, NY, NX))
    coh = np.full((T, NY, NX), 0.9) + rng.normal(0, 0.03, (T, NY, NX))

    def patch(cx, cy, rad):
        return np.hypot(xx - cx, yy - cy) < rad

    def dd(s):
        return (dt.date.fromisoformat(s) - START).days

    # E wall: precursor creep from 2018-03-01, failure 2018-07-15
    pe = patch(X0 + 750, Y0, 160)
    D[:, pe] += _log_creep(days, dd("2018-03-01"), dd("2018-07-15"), 0.02)[:, None]
    # decorrelation where per-revisit motion exceeds lambda/4, and for 3 dates after failure
    step = np.abs(np.diff(D[:, pe].mean(1), prepend=0))
    lost = (step > 0.055466 / 4) | ((days >= dd("2018-07-15")) & (days < dd("2018-07-15") + 36))
    for t in np.where(lost)[0]:
        coh[t][pe] = 0.2
    # N wall: sudden failure, no precursor; post-failure decorrelation
    pn = patch(X0, Y0 + 750, 160)
    for t in np.where((days >= dd("2019-05-01")) & (days < dd("2019-05-01") + 36))[0]:
        coh[t][pn] = 0.2
    # W wall: creep present, but layover/shadow hides the whole wall
    pw = patch(X0 - 750, Y0, 160)
    D[:, pw] += _log_creep(days, dd("2018-05-01"), dd("2018-10-01"), 0.02)[:, None]
    layover = ((az >= 225) & (az < 315) & (r > 400) & (r < 1100)).astype(np.uint8)
    # atmosphere: smooth turbulent screen + seasonal delay proportional to depth
    for t in range(T):
        screen = ndimage.gaussian_filter(rng.normal(0, 1, (NY, NX)), 25)
        screen = screen / (screen.std() + 1e-12) * 0.004
        D[t] += screen + 0.000012 * depth * math.cos(2 * math.pi * days[t] / 365.25)
    D += rng.normal(0, 0.0015, D.shape)
    D -= D[0]
    return dates, D.astype(np.float32), np.clip(coh, 0, 1).astype(np.float32), layover


def granules_from_truth(dates, D, coh, drop_secondary=None):
    """Cut the truth into OPERA-style granules with a reference date that resets every MINISTACK."""
    x, y = grid()
    grans, ref_i = [], 0
    for i in range(1, len(dates)):
        if dates[i].isoformat() != drop_secondary:
            grans.append({"displacement": D[i] - D[ref_i], "temporal_coherence": coh[i],
                          "recommended_mask": None, "water_mask": None, "x": x, "y": y, "epsg": EPSG,
                          "reference_date": dates[ref_i], "secondary_date": dates[i]})
        if i % MINISTACK == 0:
            ref_i = i
    return grans


def build_project(root, params_src):
    """Write a complete synthetic project layout under root (config, processed stacks)."""
    import shutil
    import yaml
    os.makedirs(os.path.join(root, "config", "sites"), exist_ok=True)
    os.makedirs(os.path.join(root, "data", "processed", "synth"), exist_ok=True)
    shutil.copy(params_src, os.path.join(root, "config", "params.yaml"))
    with open(os.path.join(root, "config", "sites", "synth_walls.geojson"), "w") as f:
        json.dump(walls_geojson(), f)
    with open(os.path.join(root, "config", "sites", "synth_stable.geojson"), "w") as f:
        json.dump(stable_geojson(), f)
    lon0, lat0 = geo.utm_to_lonlat(X0 - 1800, Y0 - 1800, EPSG, use_pyproj=False)
    lon1, lat1 = geo.utm_to_lonlat(X0 + 1800, Y0 + 1800, EPSG, use_pyproj=False)
    with open(os.path.join(root, "config", "sites.yaml"), "w") as f:
        yaml.safe_dump({"exclude_operators": ["Employer Co"], "sites": [{
            "id": "synth", "name": "Synthetic test pit (not real)", "operator": "Nobody",
            "bbox": [float(lon0), float(lat0), float(lon1), float(lat1)], "epsg": EPSG,
            "walls": "config/sites/synth_walls.geojson", "stable": "config/sites/synth_stable.geojson",
            "enabled": True}]}, f)
    rows = ["event_id,site_id,wall_id,date,lon,lat,size_class,source,source_url,confidence,notes"]
    for eid, wid, date, off in EVENTS:
        lon = lat = ""
        if off:
            lo, la = geo.utm_to_lonlat(X0 + off[0], Y0 + off[1], EPSG, use_pyproj=False)
            lon, lat = f"{float(lo):.6f}", f"{float(la):.6f}"
        rows.append(f"{eid},synth,{wid},{date},{lon},{lat},,synthetic,,test,SYNTHETIC")
    with open(os.path.join(root, "config", "events.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")

    import yaml as _y
    params = _y.safe_load(open(params_src))
    dates, D, coh, layover = truth()
    s = stk.rebase(granules_from_truth(dates, D, coh), params["coherence_min"], params["use_recommended_mask"])
    x, y = grid()
    stable_mask = geo.features_mask(geo.load_geojson_polygons(
        os.path.join(root, "config", "sites", "synth_stable.geojson")), x, y, EPSG)
    stk.reference_to_stable(s, stable_mask, params["stable_min_pixels"])
    stk.save(s, os.path.join(root, "data", "processed", "synth", "F99999_stack.npz"))
    # static: descending-like LOS (look from the east, ~38 deg incidence), layover over the W wall
    inc, head = math.radians(38), math.radians(190)
    los_e = np.full((NY, NX), math.sin(inc) * math.cos(head))
    los_n = np.full((NY, NX), -math.sin(inc) * math.sin(head))
    np.savez_compressed(os.path.join(root, "data", "processed", "synth", "F99999_static.npz"),
                        los_east=los_e, los_north=los_n,
                        los_up=np.sqrt(1 - los_e**2 - los_n**2), layover_shadow_mask=layover,
                        x=x, y=y)
    return dates, D
