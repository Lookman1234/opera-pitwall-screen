"""Find wall movement that stands out from the noise, and measure where the satellite can see.

Plain-language header: for every wall square and every date, this file works out
how fast that square has been moving over the last couple of months. It compares
that speed with how "jittery" ground you marked as stable looks on the same
date. A wall raises an alert only when a patch of neighbouring squares moves
clearly faster than the jitter, on at least two dates in a row. It also scores
each wall for how well the satellite can see it. You do not need to open it.

All thresholds live in config/params.yaml and are written into the stats file,
so every number in the paper states the rule that produced it.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .geo import downslope_vector

SENTINEL1_WAVELENGTH_M = 0.055465763  # C-band, 5.405 GHz


def rolling_velocity(stack, window_days: int, min_obs: int) -> np.ndarray:
    """LOS velocity [T, ny, nx] in metres/year from a least-squares line over the trailing window.

    Only epochs in the same segment as epoch t and inside (t - window, t] are used.
    Pixels with fewer than min_obs valid epochs in the window get NaN.
    """
    T = len(stack.dates)
    days = np.array([(d - stack.dates[0]).days for d in stack.dates], dtype=float)
    vel = np.full(stack.disp.shape, np.nan, dtype=np.float32)
    for t in range(T):
        idx = np.where((stack.segment == stack.segment[t]) & (days <= days[t])
                       & (days > days[t] - window_days))[0]
        if idx.size < min_obs:
            continue
        w = stack.valid[idx].astype(float)                       # [k, ny, nx]
        ty = (days[idx] / 365.25)[:, None, None]
        d = np.where(stack.valid[idx], stack.disp[idx], 0.0)
        n = w.sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            tm = (w * ty).sum(0) / n
            dm = (w * d).sum(0) / n
            sxx = (w * (ty - tm) ** 2).sum(0)
            sxy = (w * (ty - tm) * (d - dm)).sum(0)
            v = sxy / sxx
        v[(n < min_obs) | (sxx <= 0)] = np.nan
        vel[t] = v
    return vel


def robust_sigma(values: np.ndarray) -> float:
    v = values[np.isfinite(values)]
    if v.size < 10:
        return np.nan
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def wall_coverage(stack, wall_masks: dict, static: dict | None, walls_props: dict,
                  coherent_epoch_frac: float) -> dict:
    """Per-wall visibility: geometry (layover/shadow), coherence over time, LOS sensitivity."""
    frac_valid = stack.valid.mean(0)
    out = {}
    for wid, m in wall_masks.items():
        n = int(m.sum())
        rec = {"n_pixels": n, "area_m2": n * abs(float(np.diff(stack.x[:2])[0]) * float(np.diff(stack.y[:2])[0]))}
        if n == 0:
            out[wid] = rec | {"usable_frac": 0.0}
            continue
        if static is not None and static.get("layover_shadow_mask") is not None:
            # (first-real-run check: layover_shadow_mask convention: assumed nonzero = layover or shadow; see docs/VERIFY_CHECKLIST.md Part 3)
            geom_ok = static["layover_shadow_mask"] == 0
        else:
            geom_ok = np.ones_like(m)
        coh_ok = frac_valid >= coherent_epoch_frac
        rec["geometry_visible_frac"] = float(geom_ok[m].mean())
        rec["coherent_frac"] = float(coh_ok[m].mean())
        rec["usable_frac"] = float((geom_ok & coh_ok)[m].mean())
        rec["median_coherence"] = float(np.nanmedian(stack.coherence[:, m]))
        props = walls_props.get(wid, {})
        if (static is not None and static.get("los_east") is not None
                and props.get("aspect_deg") is not None and props.get("slope_deg") is not None):
            dvec = downslope_vector(float(props["aspect_deg"]), float(props["slope_deg"]))
            proj = (dvec[0] * static["los_east"][m] + dvec[1] * static["los_north"][m]
                    + dvec[2] * static["los_up"][m])
            rec["los_sensitivity"] = float(np.nanmean(np.abs(proj)))
            rec["expected_los_sign"] = int(np.sign(np.nanmean(proj)))
        else:
            rec["los_sensitivity"] = None
        out[wid] = rec
    return out


def detect(stack, wall_masks: dict, stable_mask: np.ndarray, p: dict, static: dict | None = None, vel=None):
    """Run the alert rule. Returns (per_epoch_rows, episodes, velocity array).

    vel: optional precomputed rolling velocity (same window settings), so several
    thresholds can be evaluated on one realization without recomputing it.
    """
    if vel is None:
        vel = rolling_velocity(stack, p["window_days"], p["min_obs_in_window"])
    geom_ok = None
    if static is not None and static.get("layover_shadow_mask") is not None:
        geom_ok = static["layover_shadow_mask"] == 0
    rows, episodes = [], []
    sigmas = np.array([robust_sigma(vel[t][stable_mask]) for t in range(len(stack.dates))])
    struct = np.ones((3, 3), bool)
    for wid, m in wall_masks.items():
        wall = m if geom_ok is None else (m & geom_ok)
        flags = []
        for t, date in enumerate(stack.dates):
            v = vel[t]
            sig = sigmas[t]
            thr = max(p["k_sigma"] * sig, p["velocity_floor_m_per_yr"]) if np.isfinite(sig) else np.nan
            ok = wall & np.isfinite(v)
            n_ok = int(ok.sum())
            alert_px = 0
            vmax = float(np.nanmax(np.abs(v[ok]))) if n_ok else np.nan
            cx = cy = np.nan
            if np.isfinite(thr) and n_ok:
                hot = ok & (np.abs(v) > thr)
                lab, nlab = ndimage.label(hot, structure=struct)
                if nlab:
                    sizes = ndimage.sum(hot, lab, index=np.arange(1, nlab + 1))
                    keep = np.isin(lab, 1 + np.where(sizes >= p["min_cluster_pixels"])[0])
                    alert_px = int(keep.sum())
                    if alert_px:
                        yy, xx = np.nonzero(keep)
                        cx, cy = float(stack.x[xx].mean()), float(stack.y[yy].mean())
            flags.append(alert_px > 0)
            rows.append({"wall_id": wid, "date": date.isoformat(), "n_valid_px": n_ok,
                         "noise_sigma_m_per_yr": None if not np.isfinite(sig) else float(sig),
                         "threshold_m_per_yr": None if not np.isfinite(thr) else float(thr),
                         "alert_px": alert_px, "max_abs_vel_m_per_yr": None if not np.isfinite(vmax) else vmax,
                         "alert_x": cx, "alert_y": cy})
        episodes += _episodes(wid, stack.dates, flags, rows[-len(stack.dates):], p["persistence_epochs"])
    return rows, episodes, vel


def _episodes(wid, dates, flags, wrows, persistence):
    eps, run = [], []
    for i, f in enumerate(flags + [False]):
        if f:
            run.append(i)
            continue
        if len(run) >= persistence:
            # an alert is "raised" on the epoch where persistence is first satisfied
            raised = run[persistence - 1]
            eps.append({"wall_id": wid, "first_flag_date": dates[run[0]].isoformat(),
                        "raised_date": dates[raised].isoformat(),
                        "end_date": dates[run[-1]].isoformat(), "n_epochs": len(run),
                        "peak_abs_vel_m_per_yr": max(wrows[j]["max_abs_vel_m_per_yr"] or 0 for j in run),
                        "max_alert_px": max(wrows[j]["alert_px"] for j in run)})
        run = []
    return eps


def aliasing_limit_m_per_yr(dates) -> dict:
    """Fastest LOS motion one revisit can record without phase ambiguity (lambda/4 per interval)."""
    gaps = np.diff(np.array(sorted(set(dates)), dtype="datetime64[D]")).astype(float)
    gaps = gaps[gaps > 0]
    if gaps.size == 0:
        return {"median_revisit_days": None, "max_unambiguous_los_m_per_yr": None}
    med = float(np.median(gaps))
    return {"median_revisit_days": med,
            "max_unambiguous_los_m_per_yr": float(SENTINEL1_WAVELENGTH_M / 4 / med * 365.25)}
