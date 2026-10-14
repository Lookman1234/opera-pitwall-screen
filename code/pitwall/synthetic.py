"""Parameterised synthetic pit for the simulation study in the preprint.

Plain-language header: builds made-up pits with a known answer so the alert rule
can be tested thousands of times under controlled conditions: how big and how long
the precursor creep is, how noisy the atmosphere is, how deep the pit is, and how
often the satellite passes. NOTHING HERE IS REAL DATA. You do not need to open it.

Scene. A 3.6 km x 3.6 km grid at 30 m posting with a 600 m deep conical pit
(walls between 450 m and 1050 m from the centre, about 45 degrees), split into four
walls by facing direction. The west wall is hidden by layover. A stable ring of
natural ground lies 1.5 to 1.75 km from the centre.

Signals.
* Precursor creep on a 160 m radius patch of the east wall, accelerating toward a
  failure date t_f in the inverse-velocity (Fukuzono) form:
  d(t) = -A ln(1 - (t - t_s)/(t_f - t_s + 4 d)), for t_s <= t < t_f,
  so 1/v falls linearly to 4 days at failure. A is the creep scale (m); t_f - t_s is
  the precursor duration.
* Coherence loss: pixels in the creep patch decorrelate (coherence 0.2) on any
  revisit whose motion exceeds a quarter wavelength (phase aliasing) and for 36 days
  after failure.
* Atmosphere: a turbulent screen per date (Gaussian-filtered noise, 750 m
  correlation scale, standard deviation sigma_atm) plus a seasonal stratified delay
  proportional to depth below the rim, c * depth * cos(2 pi t / 1 yr).
* Pixel noise: independent Gaussian, sigma_px.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
from scipy import ndimage

EPSG = 32612
NX = NY = 120
PIX = 30.0
X0, Y0 = 400000.0, 4500000.0
START = dt.date(2017, 1, 6)
SPAN_DAYS = 1092
FAIL_DAY = 560
MINISTACK = 15
WAVELENGTH_C = 0.055465763
WALLS = {"N": (-45, 45), "E": (45, 135), "S": (135, 225), "W": (225, 315)}


def grid():
    x = X0 + (np.arange(NX) - NX / 2 + 0.5) * PIX
    y = Y0 - (np.arange(NY) - NY / 2 + 0.5) * PIX
    return x, y


def masks():
    x, y = grid()
    xx, yy = np.meshgrid(x, y)
    r = np.hypot(xx - X0, yy - Y0)
    az = (np.degrees(np.arctan2(xx - X0, yy - Y0)) + 360) % 360
    ring = (r >= 450) & (r <= 1050)
    walls = {}
    for k, (a0, a1) in WALLS.items():
        a0m, a1m = a0 % 360, a1 % 360
        sel = ((az >= a0m) | (az < a1m)) if a0m > a1m else ((az >= a0m) & (az < a1m))
        walls[k] = ring & sel
    stable = (np.maximum(np.abs(xx - X0), np.abs(yy - Y0)) >= 1500) & \
             (np.maximum(np.abs(xx - X0), np.abs(yy - Y0)) <= 1750)
    layover = walls["W"].astype(np.uint8)
    depth = np.clip((1050 - r) / 600, 0, 1) * 600.0
    patch = np.hypot(xx - (X0 + 750), yy - Y0) < 160
    return walls, stable, layover, depth, patch


def creep(t_days, ts, tf, amp):
    out = np.zeros_like(t_days, dtype=float)
    if amp <= 0:
        return out
    on = (t_days >= ts) & (t_days < tf)
    out[on] = -amp * np.log(1 - (t_days[on] - ts) / (tf - ts + 4.0))
    out[t_days >= tf] = -amp * np.log(1 - (tf - ts) / (tf - ts + 4.0))
    return out


def scene(seed, amp=0.02, precursor_days=120, revisit=12, sigma_atm=0.004, seasonal=1.2e-5,
          sigma_px=0.0015):
    """Return (dates, truth displacement [T,ny,nx] m, coherence [T,ny,nx])."""
    rng = np.random.default_rng(seed)
    _, _, _, depth, patch = masks()
    n = SPAN_DAYS // revisit
    days = np.arange(n + 1, dtype=float) * revisit
    dates = [START + dt.timedelta(days=int(d)) for d in days]
    T = len(days)
    D = np.zeros((T, NY, NX))
    coh = np.clip(0.9 + rng.normal(0, 0.03, (T, NY, NX)), 0, 1)
    c = creep(days, FAIL_DAY - precursor_days, FAIL_DAY, amp)
    D[:, patch] += c[:, None]
    step = np.abs(np.diff(c, prepend=0.0))
    lost = (step > WAVELENGTH_C / 4) | ((days >= FAIL_DAY) & (days < FAIL_DAY + 36))
    if amp > 0:
        for t in np.where(lost)[0]:
            coh[t][patch] = 0.2
    for t in range(T):
        s = ndimage.gaussian_filter(rng.normal(0, 1, (NY, NX)), 25)
        D[t] += s / (s.std() + 1e-12) * sigma_atm + seasonal * depth * math.cos(2 * math.pi * days[t] / 365.25)
    D += rng.normal(0, sigma_px, D.shape)
    D -= D[0]
    return dates, D.astype(np.float32), coh.astype(np.float32)


def granules(dates, D, coh):
    x, y = grid()
    out, ref = [], 0
    for i in range(1, len(dates)):
        out.append({"displacement": D[i] - D[ref], "temporal_coherence": coh[i], "recommended_mask": None,
                    "water_mask": None, "x": x, "y": y, "epsg": EPSG,
                    "reference_date": dates[ref], "secondary_date": dates[i]})
        if i % MINISTACK == 0:
            ref = i
    return out


def failure_date():
    return START + dt.timedelta(days=FAIL_DAY)
