"""Read OPERA DISP-S1 and DISP-S1-STATIC granules into plain numpy arrays.

Plain-language header: this file opens the NASA map files and pulls out only the
small window around one pit. You do not need to open it.

Technical notes
---------------
* Layer names follow the OPERA DISP-S1 v1 product specification as understood at
  build time. They are collected in LAYERS/STATIC_LAYERS so one edit fixes them.
  Run `python code/02_stack.py --inspect <file.nc>` on the first real granule and
  compare the printed tree with these names before trusting any output.
  (first-real-run check: layer names against the first real granule and the product spec; see docs/VERIFY_CHECKLIST.md Part 3)
* Each lookup tries several candidate paths, then falls back to searching the
  file for a dataset with the same leaf name, so group moves do not break reads.
* Only the pixels inside the site bounding box are read (h5py slicing), so full
  frame files and pre-subset files both work.
* Displacement is line-of-sight (LOS), metres, relative to the granule's
  reference date. Rebasing onto one common start date happens in stack.py.
"""

from __future__ import annotations

import datetime as dt
import re

import numpy as np

LAYERS = {
    "displacement": ["displacement"],
    "recommended_mask": ["recommended_mask"],
    "temporal_coherence": ["temporal_coherence"],
    "water_mask": ["water_mask"],
    "x": ["x"],
    "y": ["y"],
    "reference_datetime": ["identification/reference_datetime", "reference_datetime"],
    "secondary_datetime": ["identification/secondary_datetime", "secondary_datetime"],
    "frame_id": ["identification/frame_id", "frame_id"],
    "spatial_ref": ["spatial_ref"],
}

STATIC_LAYERS = {
    "los_east": ["los_east"],
    "los_north": ["los_north"],
    "layover_shadow_mask": ["layover_shadow_mask"],
    "x": ["x"],
    "y": ["y"],
}


def _h5():
    try:
        import h5py  # type: ignore
    except ImportError as e:  # pragma: no cover - only on machines without h5py
        raise SystemExit("h5py is required to read real granules: pip install h5py") from e
    return h5py


def _find(f, candidates):
    for c in candidates:
        if c in f:
            return f[c]
    leaf = candidates[0].split("/")[-1]
    hits = []
    f.visititems(lambda name, obj: hits.append(name) if name.split("/")[-1] == leaf else None)
    return f[hits[0]] if hits else None


def _scalar_str(ds) -> str:
    v = ds[()]
    if isinstance(v, bytes):
        return v.decode()
    if isinstance(v, np.ndarray):
        v = v.item() if v.size == 1 else v[0]
        return v.decode() if isinstance(v, bytes) else str(v)
    return str(v)


def parse_datetime(s: str) -> dt.date:
    m = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if not m:
        raise ValueError(f"cannot parse a date from {s!r}")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def dates_from_filename(name: str) -> tuple[dt.date, dt.date]:
    """Fallback: OPERA DISP-S1 file names carry <reference>_<secondary> timestamps."""
    stamps = re.findall(r"(\d{8})T\d{6}Z", name)
    if len(stamps) < 2:
        raise ValueError(f"cannot find reference/secondary dates in {name}")
    return parse_datetime(stamps[0]), parse_datetime(stamps[1])


def epsg_from_spatial_ref(ds) -> int | None:
    for key in ("epsg_code", "crs_wkt", "spatial_ref"):
        if key in ds.attrs:
            val = ds.attrs[key]
            val = val.decode() if isinstance(val, bytes) else str(val)
            if val.isdigit():
                return int(val)
            codes = re.findall(r'AUTHORITY\["EPSG","(\d+)"\]|ID\["EPSG",(\d+)\]', val)
            if codes:
                last = codes[-1]
                return int(last[0] or last[1])
    return None


def _window(x, y, bbox_xy):
    xmin, ymin, xmax, ymax = bbox_xy
    xi = np.where((x >= xmin) & (x <= xmax))[0]
    yi = np.where((y >= ymin) & (y <= ymax))[0]
    if xi.size == 0 or yi.size == 0:
        return None
    return slice(xi.min(), xi.max() + 1), slice(yi.min(), yi.max() + 1)


def read_granule(path: str, bbox_xy, epsg_override: int | None = None) -> dict | None:
    """Return the window of one DISP-S1 granule, or None if the bbox misses it."""
    h5py = _h5()
    with h5py.File(path, "r") as f:
        x = _find(f, LAYERS["x"])[()]
        y = _find(f, LAYERS["y"])[()]
        win = _window(x, y, bbox_xy)
        if win is None:
            return None
        xs, ys = win
        out = {"x": x[xs], "y": y[ys], "file": path}
        for key in ("displacement", "recommended_mask", "temporal_coherence", "water_mask"):
            ds = _find(f, LAYERS[key])
            out[key] = None if ds is None else ds[ys, xs]
        if out["displacement"] is None:
            raise KeyError(f"{path}: no displacement layer found")
        try:
            out["reference_date"] = parse_datetime(_scalar_str(_find(f, LAYERS["reference_datetime"])))
            out["secondary_date"] = parse_datetime(_scalar_str(_find(f, LAYERS["secondary_datetime"])))
        except (TypeError, ValueError):
            out["reference_date"], out["secondary_date"] = dates_from_filename(path)
        sr = _find(f, LAYERS["spatial_ref"])
        out["epsg"] = epsg_override or (epsg_from_spatial_ref(sr) if sr is not None else None)
        fid = _find(f, LAYERS["frame_id"])
        out["frame_id"] = _scalar_str(fid) if fid is not None else None
    return out


def read_static(path: str, bbox_xy) -> dict | None:
    h5py = _h5()
    with h5py.File(path, "r") as f:
        x = _find(f, STATIC_LAYERS["x"])[()]
        y = _find(f, STATIC_LAYERS["y"])[()]
        win = _window(x, y, bbox_xy)
        if win is None:
            return None
        xs, ys = win
        out = {"x": x[xs], "y": y[ys]}
        for key in ("los_east", "los_north", "layover_shadow_mask"):
            ds = _find(f, STATIC_LAYERS[key])
            out[key] = None if ds is None else ds[ys, xs].astype(float)
    if out["los_east"] is not None and out["los_north"] is not None:
        out["los_up"] = np.sqrt(np.clip(1 - out["los_east"] ** 2 - out["los_north"] ** 2, 0, 1))
    return out


def inspect(path: str) -> str:
    """Return a printable tree of every dataset with shape, dtype and units."""
    h5py = _h5()
    lines = []
    with h5py.File(path, "r") as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                units = obj.attrs.get("units", b"")
                units = units.decode() if isinstance(units, bytes) else str(units)
                lines.append(f"{name:60s} {str(obj.shape):20s} {str(obj.dtype):10s} {units}")
        f.visititems(visit)
    return "\n".join(lines)
