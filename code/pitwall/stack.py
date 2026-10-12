"""Stitch granules into one movement history per pixel, and reference it to stable ground.

Plain-language header: each NASA map says how far the ground moved since some
starting date, and that starting date changes every few months. This file chains
the maps together so every 30 m square has one continuous history from one
start date, then subtracts the average movement of ground you marked as stable,
so whole-scene effects (weather in the radar signal) cancel out. You do not
need to open it.

Rebasing rule. A granule g says d_g = D(sec_g) - D(ref_g) per pixel. Sorting by
secondary date and setting D(t0) = 0 at the earliest reference, each granule is
placed with D(sec_g) = D(ref_g) + d_g, which requires D(ref_g) to be known, i.e.
ref_g is t0 or the secondary date of an earlier granule. When it is not (a gap
in the archive), a new segment starts and the break is recorded; detection never
fits a velocity across a segment break.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Stack:
    dates: list            # list[datetime.date], length T
    disp: np.ndarray       # [T, ny, nx] float32, metres LOS, cumulative from dates[0] within segment
    coherence: np.ndarray  # [T, ny, nx] float32 temporal coherence of the granule that produced the epoch
    valid: np.ndarray      # [T, ny, nx] bool, pixel passes masks at that epoch
    segment: np.ndarray    # [T] int, segment id; values are comparable only within one segment
    x: np.ndarray
    y: np.ndarray
    epsg: int
    breaks: list = field(default_factory=list)  # dates where a new segment started
    meta: dict = field(default_factory=dict)


def rebase(granules: list[dict], coherence_min: float, use_recommended_mask: bool = True) -> Stack:
    """Chain granules (dicts from disp_io.read_granule or the synthetic fixture) into a Stack."""
    if not granules:
        raise ValueError("no granules to stack")
    g0 = granules[0]
    shape = g0["displacement"].shape
    for g in granules:
        if g["displacement"].shape != shape:
            raise ValueError("granules have different window shapes; check frame and bbox")
    # one granule per secondary date (latest reference wins if an archive holds reprocessed duplicates)
    by_sec: dict = {}
    for g in sorted(granules, key=lambda g: (g["secondary_date"], g["reference_date"])):
        by_sec[g["secondary_date"]] = g
    ordered = [by_sec[k] for k in sorted(by_sec)]

    t0 = min(g["reference_date"] for g in ordered)
    known = {t0: (np.zeros(shape, np.float32), 0)}   # date -> (cumulative, segment)
    dates = [t0]
    disp = [np.zeros(shape, np.float32)]
    coh = [np.ones(shape, np.float32)]
    valid = [np.ones(shape, bool)]
    seg = [0]
    breaks = []
    current_seg = 0
    for g in ordered:
        d = np.asarray(g["displacement"], dtype=np.float32)
        ref = g["reference_date"]
        if ref in known:
            base, s = known[ref]
        else:
            current_seg += 1
            breaks.append(ref.isoformat())
            base, s = np.zeros(shape, np.float32), current_seg
            known[ref] = (base, s)
            dates.append(ref)
            disp.append(base)
            coh.append(np.ones(shape, np.float32))
            valid.append(np.ones(shape, bool))
            seg.append(s)
        cum = base + d
        c = np.asarray(g.get("temporal_coherence") if g.get("temporal_coherence") is not None
                       else np.ones(shape), dtype=np.float32)
        ok = np.isfinite(cum) & (c >= coherence_min)
        if use_recommended_mask and g.get("recommended_mask") is not None:
            ok &= np.asarray(g["recommended_mask"]) == 1
        if g.get("water_mask") is not None:
            # [VERIFY water_mask convention: assumed 1 = land, 0 = water]
            ok &= np.asarray(g["water_mask"]) != 0
        known[g["secondary_date"]] = (cum, s)
        dates.append(g["secondary_date"])
        disp.append(cum)
        coh.append(c)
        valid.append(ok)
        seg.append(s)

    order = np.argsort(np.array(dates, dtype="datetime64[D]"), kind="stable")
    return Stack(
        dates=[dates[i] for i in order],
        disp=np.stack([disp[i] for i in order]).astype(np.float32),
        coherence=np.stack([coh[i] for i in order]).astype(np.float32),
        valid=np.stack([valid[i] for i in order]),
        segment=np.array([seg[i] for i in order]),
        x=np.asarray(g0["x"]), y=np.asarray(g0["y"]),
        epsg=int(g0["epsg"]), breaks=breaks,
    )


def reference_to_stable(stack: Stack, stable_mask: np.ndarray, min_pixels: int = 20) -> np.ndarray:
    """Subtract the per-epoch median of valid stable-area pixels. Returns the per-epoch offset.

    Epochs where fewer than min_pixels stable pixels are valid are marked invalid
    everywhere (offset NaN), because their reference is not trustworthy.
    """
    offsets = np.full(len(stack.dates), np.nan)
    for t in range(len(stack.dates)):
        sel = stable_mask & stack.valid[t]
        if sel.sum() >= min_pixels:
            offsets[t] = float(np.median(stack.disp[t][sel]))
            stack.disp[t] -= offsets[t]
        else:
            stack.valid[t] &= False
    return offsets


def save(stack: Stack, path: str) -> None:
    np.savez_compressed(
        path, dates=np.array([d.isoformat() for d in stack.dates]), disp=stack.disp,
        coherence=stack.coherence, valid=stack.valid, segment=stack.segment,
        x=stack.x, y=stack.y, epsg=stack.epsg, breaks=np.array(stack.breaks, dtype=str),
    )


def load(path: str) -> Stack:
    z = np.load(path, allow_pickle=False)
    return Stack(
        dates=[dt.date.fromisoformat(s) for s in z["dates"]], disp=z["disp"],
        coherence=z["coherence"], valid=z["valid"], segment=z["segment"],
        x=z["x"], y=z["y"], epsg=int(z["epsg"]), breaks=list(z["breaks"]),
    )
