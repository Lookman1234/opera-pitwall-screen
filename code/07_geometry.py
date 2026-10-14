#!/usr/bin/env python3
"""Step 7: what the satellite geometry lets it see on a pit wall (for the preprint).

Plain-language header: the radar measures movement only along its own slanted line
of sight, and steep walls can be hidden. This step works out, for every direction a
wall can face, (1) how much of a downslope slide the satellite would actually record,
and (2) whether the wall is hidden (layover or shadow), for the ascending and
descending Sentinel-1 passes. It also computes the fastest movement each radar can
record between two passes. Pure geometry: no downloads. Writes paper/geometry.json.

Conventions. Line-of-sight (LOS) unit vector l points from the ground to the
satellite (OPERA DISP-S1: positive displacement = toward the satellite). A wall face
with aspect a (direction the face looks toward, clockwise from north) and slope s
has downslope unit vector d = (sin a cos s, cos a cos s, -sin s) in (east, north, up).
The recorded fraction of a downslope slide is p = d . l. Sentinel-1 is right-looking,
so the ground-to-satellite azimuth is heading - 90 degrees.

Layover and shadow (planar-slope approximation in the range plane): with the slope
angle projected on the range direction, alpha_r = atan(tan s * cos(a - az_gs)),
layover occurs when alpha_r > theta (face tilted toward the radar more steeply than
the incidence angle), and shadow when -alpha_r > 90 - theta.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = 299792458.0
SENSORS = {
    "Sentinel-1 C-band": {"freq_hz": 5.405e9, "revisits": [6, 12, 24]},
    "NISAR L-band": {"freq_hz": 1.257e9, "revisits": [12]},
}
# Typical Sentinel-1 headings at mid-northern latitudes (degrees clockwise from north)
PASSES = {"ascending": 348.0, "descending": 192.0}
INCIDENCES = [30.0, 39.0, 46.0]     # IW swath near, mid, far (approx. 29-46 degrees)
SLOPES = [35.0, 45.0, 55.0]


def los(heading, inc):
    az = math.radians(heading - 90.0)
    i = math.radians(inc)
    return np.array([math.sin(i) * math.sin(az), math.sin(i) * math.cos(az), math.cos(i)]), (heading - 90.0) % 360


def downslope(aspect, slope):
    a, s = np.radians(aspect), np.radians(slope)
    return np.stack([np.sin(a) * np.cos(s), np.cos(a) * np.cos(s), -np.sin(s) * np.ones_like(a)], axis=-1)


def visibility(aspect, slope, az_gs, inc):
    ar = np.degrees(np.arctan(np.tan(np.radians(slope)) * np.cos(np.radians(aspect - az_gs))))
    lay = ar > inc
    sha = -ar > (90.0 - inc)
    return np.where(lay, "layover", np.where(sha, "shadow", "visible"))


def main():
    out = {"conventions": "p = downslope . LOS(ground->satellite); positive LOS displacement = toward satellite",
           "passes": PASSES}
    asp = np.arange(0, 360, 1.0)
    out["aliasing"] = []
    for name, sp in SENSORS.items():
        lam = C / sp["freq_hz"]
        for r in sp["revisits"]:
            out["aliasing"].append({"sensor": name, "wavelength_cm": 100 * lam, "revisit_days": r,
                                    "max_los_cm_per_revisit": 100 * lam / 4,
                                    "max_los_cm_per_yr": 100 * lam / 4 / r * 365.25})
    curves, summary = {}, []
    for inc in INCIDENCES:
        for slope in SLOPES:
            best = np.zeros_like(asp)
            vis_any = np.zeros(asp.shape, bool)
            row = {"incidence_deg": inc, "slope_deg": slope}
            for pname, head in PASSES.items():
                l, azgs = los(head, inc)
                p = downslope(asp, slope) @ l
                v = visibility(asp, slope, azgs, inc)
                ok = v == "visible"
                sens = np.where(ok, np.abs(p), 0.0)
                best = np.maximum(best, sens)
                vis_any |= ok
                row[pname] = {"frac_visible": float(ok.mean()), "frac_layover": float((v == "layover").mean()),
                              "frac_shadow": float((v == "shadow").mean()),
                              "frac_sens_ge_0.5": float((sens >= 0.5).mean()),
                              "frac_sens_lt_0.2": float((sens < 0.2).mean())}
                if inc == 39.0 and slope == 45.0:
                    curves[pname] = {"aspect": asp.tolist(), "p": p.tolist(), "vis": v.tolist()}
            row["either"] = {"frac_visible": float(vis_any.mean()), "frac_sens_ge_0.5": float((best >= 0.5).mean()),
                             "frac_sens_lt_0.2": float((best < 0.2).mean())}
            summary.append(row)
    out["aspect_summary"] = summary
    out["curves_inc39_slope45"] = curves
    # the two pilot walls (aspect from the pit layout; overall slope 45 degrees assumed)
    pilot = []
    for wall, a in [("Continental D East highwall (faces west)", 270.0), ("Saga Pit north wall (faces south)", 180.0)]:
        for inc in INCIDENCES:
            rec = {"wall": wall, "aspect_deg": a, "slope_deg": 45.0, "incidence_deg": inc}
            for pname, head in PASSES.items():
                l, azgs = los(head, inc)
                p = float(downslope(np.array([a]), 45.0)[0] @ l)
                rec[pname] = {"p": p, "vis": str(visibility(np.array([a]), 45.0, azgs, inc)[0])}
            pilot.append(rec)
    out["pilot_walls"] = pilot
    with open(os.path.join(ROOT, "paper", "geometry.json"), "w") as f:
        json.dump(out, f, indent=1)
    for r in summary:
        if r["incidence_deg"] == 39.0:
            print(r["slope_deg"], {k: r[k] for k in ("ascending", "descending", "either")})
    for r in pilot:
        print(r)
    for r in out["aliasing"]:
        print(r)


if __name__ == "__main__":
    main()
