#!/usr/bin/env python3
"""Step 3: raise alerts on each wall and score them against reported failures.

Plain-language header: this step applies the alert rule from config/params.yaml
to every wall, works out how well the satellite can see each wall, and compares
alerts with the failure list in config/events.csv. It writes:

  data/processed/<pit>/F<frame>_epochs.csv     wall-by-date table (speed, noise, alert size)
  data/processed/alerts.csv                    every alert, and whether a reported failure followed
  data/processed/event_outcomes.csv            every failure: warned / missed / not observable, lead days
  data/processed/wall_coverage.csv             how well each wall can be seen
  paper/stats.json                             every number the paper and README quote
  data/processed/qa_report.txt                 (appended) counts and checks

With two satellite tracks over a pit, an event counts as warned if either track warned.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import detect, sitemasks, stack as stk, validate  # noqa: E402
from pitwall.util import load_config  # noqa: E402

RANK = {"warned": 0, "detected_after": 1, "missed": 2, "not_observable": 3}


def load_static(path, shape):
    if not os.path.exists(path):
        return None
    z = dict(np.load(path))
    if z.get("los_east") is not None and z["los_east"].shape != shape:
        return None
    return z


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--events", default=None)
    a = ap.parse_args()
    sites, p = load_config(a.root)
    events_all = pd.read_csv(a.events or os.path.join(a.root, "config", "events.csv"), dtype=str)
    proc = os.path.join(a.root, "data", "processed")
    qa, cov_rows, ev_rows, al_rows, track_stats = [], [], [], [], []
    done_sites = []
    for site in sites:
        stacks = sorted(glob.glob(os.path.join(proc, site["id"], "F*_stack.npz")))
        if not stacks:
            qa.append(f"{site['id']}: SKIPPED, no stacks (no wall outlines yet, or step 2 not run)")
            continue
        done_sites.append(site)
        ev_site = events_all[events_all.site_id == site["id"]].reset_index(drop=True).copy()
        aliases = site.get("wall_aliases") or {}
        ev_site["wall_id_reported"] = ev_site["wall_id"]
        ev_site["wall_id"] = ev_site["wall_id"].map(lambda w: aliases.get(w, w) if isinstance(w, str) else w)
        for sp in stacks:
            frame = os.path.basename(sp).split("_")[0]
            s = stk.load(sp)
            shape = s.disp.shape[1:]
            static = load_static(sp.replace("_stack.npz", "_static.npz"), shape)
            wall_masks, props, wall_src = sitemasks.wall_masks(a.root, site, s.x, s.y, s.epsg)
            smp = sp.replace("_stack.npz", "_stable_mask.npy")
            stable_mask = np.load(smp) if os.path.exists(smp) else sitemasks.stable_mask(a.root, site, s.x, s.y, s.epsg)[0]
            rows, eps, _ = detect.detect(s, wall_masks, stable_mask, p, static)
            pd.DataFrame(rows).to_csv(os.path.join(proc, site["id"], f"{frame}_epochs.csv"), index=False)
            cov = detect.wall_coverage(s, wall_masks, static, props, p["coherent_epoch_frac"])
            for wid, c in cov.items():
                cov_rows.append({"site_id": site["id"], "frame": frame, "wall_id": wid, **c})
            ev_out, ep_out, summ = validate.validate(ev_site, eps, rows, wall_masks, s, p)
            ev_out["site_id"], ev_out["frame"] = site["id"], frame
            ep_out["site_id"], ep_out["frame"] = site["id"], frame
            ev_rows.append(ev_out)
            al_rows.append(ep_out)
            alias = detect.aliasing_limit_m_per_yr(s.dates)
            track_stats.append({"site_id": site["id"], "frame": frame, "n_dates": len(s.dates),
                                "first_date": s.dates[0].isoformat(), "last_date": s.dates[-1].isoformat(),
                                "segment_breaks": list(s.breaks), **alias, **summ})
            unassigned = ev_out[ev_out.assigned_wall.isna()]
            qa.append(f"{site['id']} {frame}: walls {len(wall_masks)} ({wall_src}) "
                      f"(px {', '.join(f'{k}={int(v.sum())}' for k, v in wall_masks.items())}), "
                      f"stable px {int(stable_mask.sum())}, alert episodes {len(eps)}, "
                      f"events {len(ev_out)} (unassigned to a wall: {len(unassigned)}), "
                      f"static {'used' if static is not None else 'not available or grid mismatch'}")
            empty = [k for k, v in wall_masks.items() if not v.any()]
            if empty:
                qa.append(f"  WARNING walls with zero pixels on this grid: {empty}")

    ev = pd.concat(ev_rows, ignore_index=True) if ev_rows else pd.DataFrame()
    if not done_sites:
        print("No site has wall outlines and stacks yet; nothing to validate.")
    al = pd.concat(al_rows, ignore_index=True) if al_rows else pd.DataFrame()
    cov = pd.DataFrame(cov_rows)
    ev.to_csv(os.path.join(proc, "event_outcomes_by_track.csv"), index=False)
    al.to_csv(os.path.join(proc, "alerts.csv"), index=False)
    cov.to_csv(os.path.join(proc, "wall_coverage.csv"), index=False)

    # best outcome per event across tracks
    best = []
    if len(ev):
        for eid, g in ev.groupby("event_id", sort=True):
            g = g.assign(r=g.outcome.map(RANK)).sort_values(["r", "lead_days"], ascending=[True, False])
            best.append(g.iloc[0].drop(labels="r"))
    best = pd.DataFrame(best)
    if not len(best):
        best = pd.DataFrame(columns=["event_id", "outcome", "lead_days"])
    best.to_csv(os.path.join(proc, "event_outcomes.csv"), index=False)
    observable = best[best.outcome != "not_observable"] if len(best) else best
    warned = int((best.outcome == "warned").sum()) if len(best) else 0
    lo, hi = validate.wilson_ci(warned, len(observable))
    leads = [int(x) for x in best.lead_days.dropna()] if len(best) else []
    stats = {
        "generated": dt.date.today().isoformat(),
        "params": p,
        "sites": [{k: s.get(k) for k in ("id", "name", "operator", "bbox", "pit_center", "wall_aliases")}
                  for s in done_sites],
        "tracks": track_stats,
        "combined": {
            "n_events": int(len(best)),
            "n_events_observable": int(len(observable)),
            "n_warned": warned,
            "n_detected_after": int((best.outcome == "detected_after").sum()) if len(best) else 0,
            "n_missed": int((best.outcome == "missed").sum()) if len(best) else 0,
            "n_not_observable": int((best.outcome == "not_observable").sum()) if len(best) else 0,
            "warning_rate": warned / len(observable) if len(observable) else None,
            "warning_rate_ci95": [lo, hi],
            "lead_days": sorted(leads),
            "lead_days_median": float(np.median(leads)) if leads else None,
            "n_alert_episodes": int(len(al)),
            "n_alerts_without_reported_event": int((al.matched_event == "").sum()) if len(al) else 0,
        },
        "coverage": {
            "n_wall_tracks": int(len(cov)),
            "median_usable_frac": float(cov.usable_frac.median()) if len(cov) else None,
            "n_wall_tracks_usable_below_25pct": int((cov.usable_frac < 0.25).sum()) if len(cov) else 0,
        },
    }
    os.makedirs(os.path.join(a.root, "paper"), exist_ok=True)
    with open(os.path.join(a.root, "paper", "stats.json"), "w") as f:
        json.dump(stats, f, indent=2, default=str)
    with open(os.path.join(proc, "qa_report.txt"), "a") as f:
        f.write("\nQA REPORT (step 3: detection and validation)\n" + "\n".join(qa) + "\n")
        c = stats["combined"]
        f.write(f"Events {c['n_events']}: warned {c['n_warned']}, detected after {c['n_detected_after']}, "
                f"missed {c['n_missed']}, not observable {c['n_not_observable']}; "
                f"alert episodes {c['n_alert_episodes']} "
                f"({c['n_alerts_without_reported_event']} without a reported event)\n")
    print("\n".join(qa))
    print(json.dumps(stats["combined"], indent=2))


if __name__ == "__main__":
    main()
