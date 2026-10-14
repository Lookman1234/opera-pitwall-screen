#!/usr/bin/env python3
"""Optional step 0: draft a candidate failure list from MSHA's public accident file.

Plain-language header: use this only if GroundFall-US is not ready. It reads MSHA's
weekly accident file, keeps reports at your pilot mines whose type mentions a fall
of face, highwall, or wall, and writes data/processed/msha_candidates.csv. These are
CANDIDATES: MSHA lists accidents (mostly injuries), not every wall failure, and gives
no exact location on the wall. You review each one, add the wall_id and, if known,
the location, and copy the ones you accept into config/events.csv.

Input: Accidents.zip from https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp
(download it in a browser and put it in data/raw/msha/). Mine IDs come from
msha_mine_id in config/sites.yaml.
(first-real-run check: the column names below against the Accidents definition file; see docs/VERIFY_CHECKLIST.md Part 3)
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitwall.util import load_config, log_provenance  # noqa: E402

COLS = {"mine_id": ["MINE_ID"], "date": ["ACCIDENT_DT", "ACCIDENT_DATE"],
        "classification": ["CLASSIFICATION", "ACCIDENT_TYPE"], "narrative": ["NARRATIVE"],
        "doc": ["DOCUMENT_NO"]}
KEYWORDS = ["FALL OF FACE", "HIGHWALL", "FALL OF ROCK", "SLIDE", "WALL"]
SOURCE = "https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp"


def pick(df, key):
    for c in COLS[key]:
        if c in df.columns:
            return c
    raise SystemExit(f"Column for {key} not found; columns are {list(df.columns)[:30]}...")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--zip", default="data/raw/msha/Accidents.zip")
    a = ap.parse_args()
    sites, _ = load_config(a.root)
    zpath = os.path.join(a.root, a.zip)
    log_provenance(zpath, SOURCE, os.path.join(a.root, "data", "raw", "PROVENANCE.txt"), note="MSHA Accidents")
    with zipfile.ZipFile(zpath) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        df = pd.read_csv(z.open(name), sep="|", dtype=str, encoding="latin-1")
    mid, dcol, ccol = pick(df, "mine_id"), pick(df, "date"), pick(df, "classification")
    ids = {str(s.get("msha_mine_id")).lstrip("0"): s["id"] for s in sites if s.get("msha_mine_id")}
    df["_mine"] = df[mid].astype(str).str.lstrip("0")
    df = df[df._mine.isin(ids)]
    text = df[ccol].fillna("")
    if "NARRATIVE" in df.columns:
        text = text + " " + df["NARRATIVE"].fillna("")
    df = df[text.str.upper().str.contains("|".join(KEYWORDS))]
    out = pd.DataFrame({
        "event_id": ["MSHA-" + str(v) for v in (df[pick(df, "doc")] if "DOCUMENT_NO" in df else df.index)],
        "site_id": df._mine.map(ids), "wall_id": "",
        "date": pd.to_datetime(df[dcol], errors="coerce").dt.date.astype(str),
        "lon": "", "lat": "", "size_class": "", "source": "MSHA Accidents", "source_url": SOURCE,
        "confidence": "candidate", "notes": df[ccol].fillna(""),
    })
    path = os.path.join(a.root, "data", "processed", "msha_candidates.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.to_csv(path, index=False)
    print(f"{len(out)} candidate events written to {path}. Review each before copying to config/events.csv.")


if __name__ == "__main__":
    main()
