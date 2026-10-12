"""Compare alerts against reported wall failures.

Plain-language header: for each reported failure, this file asks three things.
Could the satellite see that wall around that time? If so, did an alert go up
before the failure, and how many days early? And separately, for every alert,
was there a reported failure afterwards? Alerts with no reported failure are
called "alerts without a reported event", not "false alarms", because public
failure lists miss many events. You do not need to open it.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from .geo import lonlat_to_utm


def wilson_ci(k: int, n: int, z: float = 1.959964) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return max(0.0, c - h), min(1.0, c + h)


def assign_wall(ev, wall_masks, stack, buffer_m):
    """Use the event's wall_id if given; otherwise the nearest wall within buffer_m."""
    wid = ev.get("wall_id")
    if isinstance(wid, str) and wid.strip():
        return wid.strip(), 0.0
    if pd.isna(ev.get("lon")) or pd.isna(ev.get("lat")):
        return None, None
    ex, ey = lonlat_to_utm(float(ev["lon"]), float(ev["lat"]), stack.epsg)
    xx, yy = np.meshgrid(stack.x, stack.y)
    best, best_d = None, np.inf
    for w, m in wall_masks.items():
        if m.any():
            d = float(np.min(np.hypot(xx[m] - ex, yy[m] - ey)))
            if d < best_d:
                best, best_d = w, d
    return (best, best_d) if best_d <= buffer_m else (None, best_d)


def validate(events: pd.DataFrame, episodes: list[dict], epoch_rows: list[dict],
             wall_masks: dict, stack, p: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ep = pd.DataFrame(episodes, columns=["wall_id", "first_flag_date", "raised_date", "end_date",
                                         "n_epochs", "peak_abs_vel_m_per_yr", "max_alert_px"])
    rows = pd.DataFrame(epoch_rows)
    lead = dt.timedelta(days=p["lead_window_days"])
    first, last = stack.dates[0], stack.dates[-1]
    out = []
    for _, ev in events.iterrows():
        rec = ev.to_dict()
        edate = dt.date.fromisoformat(str(ev["date"])[:10])
        wid, dist = assign_wall(rec, wall_masks, stack, p["event_buffer_m"])
        rec.update({"assigned_wall": wid, "dist_to_wall_m": dist, "outcome": None,
                    "lead_days": None, "reason": ""})
        if wid is None or wid not in wall_masks:
            rec.update(outcome="not_observable", reason="no wall within buffer")
        elif edate < first or edate > last:
            rec.update(outcome="not_observable", reason="outside data time span")
        else:
            w = rows[(rows.wall_id == wid)]
            dts = pd.to_datetime(w.date).dt.date
            pre = w[(dts >= edate - lead) & (dts < edate)]
            observed = pre[pre.n_valid_px >= p["min_cluster_pixels"]]
            if len(observed) < p["min_obs_in_window"]:
                rec.update(outcome="not_observable",
                           reason=f"{len(observed)} usable dates on this wall in the {p['lead_window_days']} days before")
            else:
                we = ep[ep.wall_id == wid].copy()
                we["raised"] = pd.to_datetime(we.raised_date).dt.date
                we["end"] = pd.to_datetime(we.end_date).dt.date
                before = we[(we.raised < edate) & (we.end >= edate - lead)]
                after = we[(we.raised >= edate) & (we.raised <= edate + dt.timedelta(days=p["late_grace_days"]))]
                if len(before):
                    earliest = max(min(before.raised), edate - lead)
                    rec.update(outcome="warned", lead_days=(edate - earliest).days)
                elif len(after):
                    rec.update(outcome="detected_after", reason="alert raised on or after the event date")
                else:
                    rec.update(outcome="missed")
        out.append(rec)
    ev_out = pd.DataFrame(out)

    # Alerts without a reported event
    ep_out = ep.copy()
    ep_out["matched_event"] = ""
    for i, e in ep_out.iterrows():
        raised = dt.date.fromisoformat(e.raised_date)
        end = dt.date.fromisoformat(e.end_date)
        for _, ev in ev_out[ev_out.assigned_wall == e.wall_id].iterrows():
            edate = dt.date.fromisoformat(str(ev["date"])[:10])
            pre = raised < edate and end >= edate - lead
            post = edate <= raised <= edate + dt.timedelta(days=p["late_grace_days"])
            if pre or post:
                ep_out.at[i, "matched_event"] = str(ev["event_id"])
                break

    observable = ev_out[ev_out.outcome != "not_observable"]
    warned = int((ev_out.outcome == "warned").sum())
    lo, hi = wilson_ci(warned, len(observable))
    years = (last - first).days / 365.25
    n_walls_observed = sum(1 for w in wall_masks if
                           (rows[rows.wall_id == w].n_valid_px >= p["min_cluster_pixels"]).mean() > 0.5)
    unmatched = int((ep_out.matched_event == "").sum()) if len(ep_out) else 0
    summary = {
        "n_events": int(len(ev_out)),
        "n_events_observable": int(len(observable)),
        "n_warned": warned,
        "n_detected_after": int((ev_out.outcome == "detected_after").sum()),
        "n_missed": int((ev_out.outcome == "missed").sum()),
        "n_not_observable": int((ev_out.outcome == "not_observable").sum()),
        "warning_rate": (warned / len(observable)) if len(observable) else None,
        "warning_rate_ci95": [lo, hi],
        "lead_days_median": (float(ev_out.lead_days.dropna().median())
                             if ev_out.lead_days.notna().any() else None),
        "lead_days_list": [int(x) for x in ev_out.lead_days.dropna()],
        "n_alert_episodes": int(len(ep_out)),
        "n_alerts_without_reported_event": unmatched,
        "alerts_without_event_per_wall_year": (unmatched / (n_walls_observed * years)
                                               if n_walls_observed and years > 0 else None),
        "n_walls_mostly_observed": n_walls_observed,
        "data_years": years,
    }
    return ev_out, ep_out, summary
