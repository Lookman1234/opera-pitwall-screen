#!/usr/bin/env python3
"""Step 2: stitch each pit's granules into one movement history per pixel, per satellite track.

Plain-language header: this step reads the downloaded maps, keeps only the area
around the pit, chains them into one continuous history for every 30 m square,
removes squares the data says are unreliable, and lines everything up against
the ground you marked as stable. Output: data/processed/<pit>/<frame>_stack.npz
plus a few lines in data/processed/qa_report.txt.

Use --inspect FILE to print every layer in one granule (do this once on real data
and compare with the names in code/pitwall/disp_io.py).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import disp_io, geo, sitemasks, stack as stk  # noqa: E402
from pitwall.util import load_config, site_dir  # noqa: E402


def frame_of(path):
    m = re.search(r"F(\d{5})", os.path.basename(path))
    return m.group(1) if m else "unknown"


def bbox_xy(site, epsg):
    lon0, lat0, lon1, lat1 = site["bbox"]
    xs, ys = geo.lonlat_to_utm([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1], epsg)
    return min(xs), min(ys), max(xs), max(ys)


def guess_epsg(site):
    lon = (site["bbox"][0] + site["bbox"][2]) / 2
    lat = (site["bbox"][1] + site["bbox"][3]) / 2
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def process_site(root, site, params, qa):
    raw = os.path.join(root, "data", "raw", site["id"])
    out = site_dir(root, "processed", site["id"])
    files = sorted(glob.glob(os.path.join(raw, "disp", "*.nc")) + glob.glob(os.path.join(raw, "disp", "*.h5")))
    if not files:
        raise SystemExit(f"{site['id']}: no granules in {raw}/disp; run 01_fetch.py first")
    by_frame = defaultdict(list)
    for f in files:
        by_frame[frame_of(f)].append(f)
    for frame, fl in sorted(by_frame.items()):
        epsg = site.get("epsg") or guess_epsg(site)
        box = bbox_xy(site, epsg)
        grans = [g for g in (disp_io.read_granule(f, box, site.get("epsg")) for f in fl) if g is not None]
        if not grans:
            qa.append(f"{site['id']} F{frame}: bbox not inside any granule")
            continue
        file_epsg = grans[0]["epsg"]
        if file_epsg and file_epsg != epsg:      # wrong zone guess: re-read in the file's own zone
            epsg = file_epsg
            box = bbox_xy(site, epsg)
            grans = [g for g in (disp_io.read_granule(f, box, epsg) for f in fl) if g is not None]
        for g in grans:
            g["epsg"] = epsg
        s = stk.rebase(grans, params["coherence_min"], params["use_recommended_mask"])
        stable_mask, stable_src = sitemasks.stable_mask(root, site, s.x, s.y, epsg)
        n_cand = int(stable_mask.sum())
        if stable_src == "auto":
            stable_mask = sitemasks.refine_stable(s, stable_mask, params.get("auto_stable_keep_frac", 0.5))
        np.save(os.path.join(out, f"F{frame}_stable_mask.npy"), stable_mask)
        offsets = stk.reference_to_stable(s, stable_mask, params["stable_min_pixels"])
        stk.save(s, os.path.join(out, f"F{frame}_stack.npz"))
        static_files = [f for f in glob.glob(os.path.join(raw, "static", "*")) if frame_of(f) == frame]
        if static_files:
            st = disp_io.read_static(static_files[0], box)
            np.savez_compressed(os.path.join(out, f"F{frame}_static.npz"),
                                **{k: v for k, v in st.items() if v is not None})
        n_dropped = int(np.isnan(offsets).sum())
        qa.append(f"{site['id']} F{frame}: {len(grans)} granules -> {len(s.dates)} dates "
                  f"({s.dates[0]} to {s.dates[-1]}), grid {s.disp.shape[1]}x{s.disp.shape[2]} px, "
                  f"EPSG {epsg}, segment breaks {s.breaks or 'none'}, stable px {int(stable_mask.sum())} "
                  f"({stable_src}; {n_cand} candidates), "
                  f"dates dropped for thin stable reference {n_dropped}, "
                  f"static {'yes' if static_files else 'MISSING'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--inspect", metavar="FILE")
    a = ap.parse_args()
    if a.inspect:
        print(disp_io.inspect(a.inspect))
        return
    sites, params = load_config(a.root)
    qa = []
    for s in sites:
        if not sitemasks.has_walls(a.root, s):
            qa.append(f"{s['id']}: SKIPPED, no wall outlines yet (hand-drawn file or step 1b)")
            continue
        process_site(a.root, s, params, qa)
    path = os.path.join(a.root, "data", "processed", "qa_report.txt")
    with open(path, "w") as f:
        f.write("QA REPORT (step 2: stacking)\n" + "\n".join(qa) + "\n")
    print("\n".join(qa))
    with open(os.path.join(a.root, "data", "processed", "params_used.json"), "w") as f:
        json.dump(params, f, indent=2)


if __name__ == "__main__":
    main()
