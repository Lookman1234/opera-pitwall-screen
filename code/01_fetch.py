#!/usr/bin/env python3
"""Step 1: download OPERA DISP-S1 granules and the matching STATIC files for each pilot pit.

Plain-language header: this step downloads the NASA ground-movement maps for the
small area around each pit, and writes down exactly what was downloaded and when
(data/raw/PROVENANCE.txt). It needs a free NASA Earthdata login, read from the
EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables (the GitHub runner
sets these from your repository secrets) or from ~/.netrc. You normally run it by
pressing "Run workflow" on GitHub, not by hand.

Tools: opera-utils (`opera-utils disp-s1-download`, flags --bbox --frame-id
--output-dir --end-datetime --num-workers, per its README) for the time series,
asf_search for DISP-S1-STATIC.
[VERIFY collection short names and the STATIC frame file-name pattern on the first run]
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall.util import load_config, log_provenance, site_dir  # noqa: E402

DISP_LANDING = "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1"
STATIC_LANDING = "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-static-v1-1"
STATIC_SHORT_NAME = "OPERA_L3_DISP-S1-STATIC_V1"


def ensure_netrc():
    user, pw = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    path = os.path.expanduser("~/.netrc")
    if user and pw and not os.path.exists(path):
        with open(path, "w") as f:
            f.write(f"machine urs.earthdata.nasa.gov login {user} password {pw}\n")
        os.chmod(path, 0o600)
    if not os.path.exists(path):
        raise SystemExit("No Earthdata login found. Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD, "
                         "or create ~/.netrc (see docs/PUBLISH_GUIDE.md, 'Earthdata login').")


def fetch_disp(site, out_dir, workers):
    bbox = [str(v) for v in site["bbox"]]
    frames = site.get("frame_ids") or [None]
    for fr in frames:
        cmd = ["opera-utils", "disp-s1-download", "--bbox", *bbox, "--output-dir", out_dir,
               "--num-workers", str(workers)]
        if fr is not None:
            cmd += ["--frame-id", str(fr)]
        if site.get("end_date"):
            cmd += ["--end-datetime", site["end_date"]]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)


def fetch_static(site, out_dir):
    import asf_search as asf  # type: ignore
    lon0, lat0, lon1, lat1 = site["bbox"]
    wkt = f"POLYGON(({lon0} {lat0},{lon1} {lat0},{lon1} {lat1},{lon0} {lat1},{lon0} {lat0}))"
    results = asf.search(shortName=STATIC_SHORT_NAME, intersectsWith=wkt)
    frames = {f"F{int(f):05d}" for f in site.get("frame_ids") or []}
    if not frames:
        disp_files = glob.glob(os.path.join(out_dir, "..", "disp", "*"))
        frames = {m.group(0) for f in disp_files for m in [re.search(r"F\d{5}", os.path.basename(f))] if m}
    keep = [r for r in results if not frames or any(fr in r.properties["fileID"] for fr in frames)]
    print(f"STATIC: {len(results)} found, {len(keep)} match frames {sorted(frames)}", flush=True)
    session = asf.ASFSession()
    user, pw = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    if user and pw:
        session.auth_with_creds(user, pw)
    for r in keep:
        r.download(path=out_dir, session=session)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--site", help="only this site id")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    sites, _ = load_config(a.root)
    ensure_netrc()
    prov = os.path.join(a.root, "data", "raw", "PROVENANCE.txt")
    for s in sites:
        if a.site and s["id"] != a.site:
            continue
        raw = site_dir(a.root, "raw", s["id"])
        ddir, sdir = os.path.join(raw, "disp"), os.path.join(raw, "static")
        os.makedirs(ddir, exist_ok=True)
        os.makedirs(sdir, exist_ok=True)
        before = set(glob.glob(os.path.join(raw, "*", "*")))
        fetch_disp(s, ddir, a.workers)
        fetch_static(s, sdir)
        for f in sorted(set(glob.glob(os.path.join(raw, "*", "*"))) - before):
            land = STATIC_LANDING if "/static/" in f else DISP_LANDING
            log_provenance(f, land, prov, note=f"site={s['id']} bbox={s['bbox']} frames={s.get('frame_ids') or 'auto'}")
        print(f"{s['id']}: {len(glob.glob(os.path.join(ddir, '*')))} DISP files, "
              f"{len(glob.glob(os.path.join(sdir, '*')))} STATIC files", flush=True)


if __name__ == "__main__":
    main()
