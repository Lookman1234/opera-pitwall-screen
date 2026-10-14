#!/usr/bin/env python3
"""Step 6: simulation study of the alert rule on synthetic pits (for the preprint).

Plain-language header: runs the full detection and scoring chain many times on
made-up pits whose answer is known, varying one thing at a time: how large and how
long the precursor creep is, the alert threshold, the velocity window, the satellite
revisit, and how strongly the atmosphere tracks pit depth. It writes every result row
to paper/synthetic_study.csv and a summary to paper/synthetic_study.json, which the
preprint reads. NOTHING HERE IS REAL DATA.

Run: python code/06_synthetic_study.py [--seeds 30] [--workers 2]
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall import detect, stack as stk, synthetic as syn, validate  # noqa: E402
from pitwall.util import load_yaml  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_one(job):
    """One realization; returns one row per (window, k) evaluated."""
    p0 = load_yaml(os.path.join(ROOT, "config", "params.yaml"))
    dates, D, coh = syn.scene(job["seed"], job["amp"], job["precursor"], job["revisit"], job["sigma_atm"],
                              job["seasonal"])
    walls, stable, layover, depth, _ = syn.masks()
    s = stk.rebase(syn.granules(dates, D, coh), p0["coherence_min"], False)
    if job.get("strat"):
        stk.correct_stratified(s, -depth)
    stk.reference_to_stable(s, stable, p0["stable_min_pixels"])
    static = {"layover_shadow_mask": layover}
    ev = pd.DataFrame([{"event_id": "E1", "site_id": "synth", "wall_id": "E",
                        "date": syn.failure_date().isoformat(), "lon": np.nan, "lat": np.nan}])
    rows = []
    for w in job["windows"]:
        p = dict(p0, window_days=w)
        vel = detect.rolling_velocity(s, w, p["min_obs_in_window"])
        for k in job["ks"]:
            p["k_sigma"] = k
            er, eps, _ = detect.detect(s, walls, stable, p, static, vel=vel)
            ev_out, ep_out, summ = validate.validate(ev, eps, er, walls, s, p)
            e = ev_out.iloc[0]
            sig = pd.DataFrame(er).noise_sigma_m_per_yr.dropna()
            rows.append({k2: job[k2] for k2 in ("study", "seed", "amp", "precursor", "revisit", "sigma_atm",
                                               "seasonal")} | {"strat": int(bool(job.get("strat"))),
                "window_days": w, "k_sigma": k, "outcome": e.outcome,
                "lead_days": None if pd.isna(e.lead_days) else int(e.lead_days),
                "n_episodes": summ["n_alert_episodes"], "n_unmatched": summ["n_alerts_without_reported_event"],
                "wall_years": summ["n_walls_mostly_observed"] * summ["data_years"],
                "median_noise_sigma_m_per_yr": float(sig.median()) if len(sig) else None,
                "W_visible_px": int(next(r["n_valid_px"] for r in er if r["wall_id"] == "W"))})
    return rows


def jobs(seeds):
    """Every scene is run twice on the same seed: without and with the stratified-delay correction."""
    out = _jobs(seeds)
    return out + [j | {"strat": True} for j in out]


def _jobs(seeds):
    base = dict(revisit=12, sigma_atm=0.004, seasonal=1.2e-5, windows=[72], ks=[3.0])
    out = []
    # A: creep scale x precursor duration, at the default rule (and k sweep for the ROC-style trade-off)
    for amp, pre, sd in itertools.product([0.005, 0.01, 0.02, 0.04], [60, 120, 240], range(seeds)):
        out.append(base | dict(study="A_grid", seed=1000 + sd, amp=amp, precursor=pre, ks=[2.0, 2.5, 3.0, 3.5, 4.0]))
    # B: null scenes (no creep), atmosphere tied to depth at four strengths, k sweep
    for seas, sd in itertools.product([0.0, 1.2e-5, 2.4e-5, 4.8e-5], range(seeds)):
        out.append(base | dict(study="B_null", seed=5000 + sd, amp=0.0, precursor=120, seasonal=seas,
                               ks=[2.0, 2.5, 3.0, 3.5, 4.0]))
    # C: velocity window, mid-size creep
    for pre, sd in itertools.product([60, 120, 240], range(seeds)):
        out.append(base | dict(study="C_window", seed=9000 + sd, amp=0.01, precursor=pre, windows=[48, 72, 120]))
    # D: 6-day versus 12-day revisit
    for amp, pre, sd in itertools.product([0.005, 0.01, 0.02], [60, 120], range(seeds)):
        out.append(base | dict(study="D_revisit", seed=13000 + sd, amp=amp, precursor=pre, revisit=6))
    # E: turbulent atmosphere strength
    for atm, sd in itertools.product([0.002, 0.004, 0.008], range(seeds)):
        out.append(base | dict(study="E_atm", seed=17000 + sd, amp=0.01, precursor=120, sigma_atm=atm))
    # F, G, H: null (no-creep) baselines for the window, revisit and atmosphere variants, so every
    # warning rate can be compared with the chance rate under identical settings
    for sd in range(seeds):
        out.append(base | dict(study="F_null_window", seed=21000 + sd, amp=0.0, precursor=120, windows=[48, 72, 120]))
        out.append(base | dict(study="G_null_revisit", seed=25000 + sd, amp=0.0, precursor=120, revisit=6))
    for atm, sd in itertools.product([0.002, 0.008], range(seeds)):
        out.append(base | dict(study="H_null_atm", seed=29000 + sd, amp=0.0, precursor=120, sigma_atm=atm))
    return out


def summarise(df_all):
    S = _summarise(df_all[df_all.strat == 0])
    S["corrected"] = _summarise(df_all[df_all.strat == 1])
    return S


def _summarise(df):
    def rate(g, outcome="warned"):
        n = len(g)
        k = int((g.outcome == outcome).sum())
        lo, hi = validate.wilson_ci(k, n)
        return {"n": n, "k": k, "rate": k / n if n else None, "ci95": [lo, hi]}

    def lead(g):
        x = g.lead_days.dropna()
        return {"median": float(x.median()) if len(x) else None,
                "q25": float(x.quantile(0.25)) if len(x) else None,
                "q75": float(x.quantile(0.75)) if len(x) else None}

    def fa(g):
        wy = g.wall_years.sum()
        return {"unmatched": int(g.n_unmatched.sum()), "wall_years": float(wy),
                "per_wall_year": float(g.n_unmatched.sum() / wy) if wy else None}

    S = {}
    a = df[(df.study == "A_grid") & (df.k_sigma == 3.0)]
    S["A_grid"] = [{"amp": amp, "precursor": pre, **rate(g), "lead": lead(g[g.outcome == "warned"]),
                    "warned_before_onset": int(((g.outcome == "warned") & (g.lead_days > pre)).sum()),
                    "outcomes": g.outcome.value_counts().to_dict(),
                    "total_creep_cm": 100 * amp * float(np.log((pre + 4) / 4)),
                    "v_mid_cm_per_yr": 100 * amp / (pre / 2 + 4) * 365.25,
                    "v_last_cm_per_yr": 100 * amp / (12 + 4) * 365.25}
                   for (amp, pre), g in a.groupby(["amp", "precursor"])]
    ak = df[df.study == "A_grid"]
    nk = df[(df.study == "B_null") & (df.seasonal == 1.2e-5)]
    S["k_tradeoff"] = [{"k_sigma": k, "warned": rate(ak[ak.k_sigma == k]),
                        "warned_before_onset": int(((ak.k_sigma == k) & (ak.outcome == "warned")
                                                    & (ak.lead_days > ak.precursor)).sum()),
                        "false_alerts": fa(nk[nk.k_sigma == k])} for k in sorted(ak.k_sigma.unique())]
    b = df[df.study == "B_null"]
    S["B_null"] = [{"seasonal": seas, "k_sigma": k, **fa(g)} for (seas, k), g in b.groupby(["seasonal", "k_sigma"])]
    c = df[df.study == "C_window"]
    S["C_window"] = [{"window_days": w, "precursor": pre, **rate(g), "lead": lead(g[g.outcome == "warned"]),
                      "noise_cm_per_yr": 100 * float(g.median_noise_sigma_m_per_yr.median())}
                     for (w, pre), g in c.groupby(["window_days", "precursor"])]
    d6 = df[df.study == "D_revisit"]
    S["D_revisit"] = []
    for (amp, pre), g in d6.groupby(["amp", "precursor"]):
        g12 = a[(a.amp == amp) & (a.precursor == pre)]
        S["D_revisit"].append({"amp": amp, "precursor": pre, "r6": rate(g), "lead6": lead(g[g.outcome == "warned"]),
                               "r12": rate(g12), "lead12": lead(g12[g12.outcome == "warned"]),
                               "noise6_cm_per_yr": 100 * float(g.median_noise_sigma_m_per_yr.median())})
    e = df[df.study == "E_atm"]
    S["E_atm"] = [{"sigma_atm_mm": 1000 * atm, **rate(g), "lead": lead(g[g.outcome == "warned"]),
                   "noise_cm_per_yr": 100 * float(g.median_noise_sigma_m_per_yr.median())}
                  for atm, g in e.groupby("sigma_atm")]
    def chance(g):
        r = rate(g)
        return r | fa(g)

    S["chance"] = {
        "k_sweep_12d_w72": {str(k): chance(b[(b.seasonal == 1.2e-5) & (b.k_sigma == k)]) for k in sorted(b.k_sigma.unique())},
        "window": {str(w): chance(g) for w, g in df[df.study == "F_null_window"].groupby("window_days")},
        "revisit6": chance(df[df.study == "G_null_revisit"]),
        "atm": {str(1000 * atm): chance(g) for atm, g in df[df.study == "H_null_atm"].groupby("sigma_atm")},
    }
    S["chance"]["atm"]["4.0"] = S["chance"]["k_sweep_12d_w72"]["3.0"]
    S["noise_default_cm_per_yr"] = 100 * float(a.median_noise_sigma_m_per_yr.median())
    S["hidden_wall_visible_px_max"] = int(df.W_visible_px.max())
    S["n_realizations"] = int(df.groupby(["study", "seed", "amp", "precursor", "revisit", "sigma_atm",
                                          "seasonal", "strat"]).ngroups)
    return S


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--summarise-only", action="store_true")
    ap.add_argument("--only", nargs="*", help="run only these studies and replace their rows in the CSV")
    a = ap.parse_args()
    out_csv = os.path.join(ROOT, "paper", "synthetic_study.csv")
    if not a.summarise_only:
        js = jobs(a.seeds)
        if a.only:
            js = [j for j in js if j["study"] in a.only]
        t0 = time.time()
        rows = []
        with ProcessPoolExecutor(a.workers) as ex:
            for i, r in enumerate(ex.map(run_one, js, chunksize=4)):
                rows += r
                if (i + 1) % 50 == 0:
                    print(f"{i + 1}/{len(js)} realizations, {time.time() - t0:.0f} s", flush=True)
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        new = pd.DataFrame(rows)
        if a.only and os.path.exists(out_csv):
            old = pd.read_csv(out_csv)
            if "strat" not in old:
                old["strat"] = 0
            new = pd.concat([old[~old.study.isin(a.only)], new], ignore_index=True)
        new.to_csv(out_csv, index=False)
    df = pd.read_csv(out_csv)
    S = summarise(df)
    S["seeds_per_cell"] = a.seeds
    with open(os.path.join(ROOT, "paper", "synthetic_study.json"), "w") as f:
        json.dump(S, f, indent=2)
    print(json.dumps(S["A_grid"][:3], indent=1))


if __name__ == "__main__":
    main()
