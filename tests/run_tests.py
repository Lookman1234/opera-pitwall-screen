#!/usr/bin/env python3
"""Run every test. Plain-language header: proves the code finds what was planted in
the synthetic pit, and that the maths helpers are right. Run: python tests/run_tests.py
(works with or without pytest installed). Expected last line: ALL TESTS PASSED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "code"))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fixture  # noqa: E402
from pitwall import detect, geo, stack as stk, validate  # noqa: E402


def test_utm_known_value():
    # On zone 12's central meridian (-111) at 40N: easting 500000, northing = k0 * meridian arc
    x, y = geo.lonlat_to_utm(-111.0, 40.0, 32612, use_pyproj=False)
    assert abs(x - 500000.0) < 1e-6, x
    assert abs(y - 4427757.22) < 0.5, y


def test_utm_round_trip():
    lon = np.array([-114.2, -112.15, -110.1])
    lat = np.array([33.1, 40.52, 46.9])
    x, y = geo.lonlat_to_utm(lon, lat, 32612, use_pyproj=False)
    lo, la = geo.utm_to_lonlat(x, y, 32612, use_pyproj=False)
    assert np.allclose(lo, lon, atol=1e-8) and np.allclose(la, lat, atol=1e-8)


def test_polygon_with_hole():
    x, y = fixture.grid()
    m = geo.features_mask(_polys(fixture.stable_geojson()), x, y, fixture.EPSG)
    # ring between 1500 and 1750 m half-width: centre excluded, ring included
    c = len(x) // 2
    assert not m[c, c]
    assert m.sum() > 0
    expected = ((np.abs(x - fixture.X0)[None, :] < 1750) & (np.abs(y - fixture.Y0)[:, None] < 1750)
                & ~((np.abs(x - fixture.X0)[None, :] < 1500) & (np.abs(y - fixture.Y0)[:, None] < 1500)))
    assert abs(int(m.sum()) - int(expected.sum())) <= 8, (m.sum(), expected.sum())


def _polys(gj):
    return [{"properties": f["properties"], "polygons": [f["geometry"]["coordinates"]]} for f in gj["features"]]


def test_rebase_exact_without_noise():
    dates, D, coh, _ = fixture.truth()
    s = stk.rebase(fixture.granules_from_truth(dates, D, coh), coherence_min=0.0, use_recommended_mask=False)
    assert len(s.dates) == len(dates)
    assert s.breaks == []
    assert np.allclose(s.disp, D, atol=1e-5)


def test_rebase_records_gap():
    dates, D, coh, _ = fixture.truth()
    # drop the granule whose secondary date becomes the next reference: chain must break
    drop = dates[fixture.MINISTACK].isoformat()
    s = stk.rebase(fixture.granules_from_truth(dates, D, coh, drop_secondary=drop), 0.0, False)
    assert s.breaks == [drop], s.breaks
    assert len(set(s.segment.tolist())) == 2


def test_wilson():
    lo, hi = validate.wilson_ci(1, 2)
    assert 0.09 < lo < 0.10 and 0.90 < hi < 0.91, (lo, hi)
    assert validate.wilson_ci(0, 0) == (None, None)


def test_aliasing_limit():
    dates, *_ = fixture.truth()
    a = detect.aliasing_limit_m_per_yr(dates)
    assert a["median_revisit_days"] == 12.0
    assert abs(a["max_unambiguous_los_m_per_yr"] - 0.4220) < 0.001, a


def test_end_to_end_synthetic():
    with tempfile.TemporaryDirectory() as tmp:
        fixture.build_project(tmp, os.path.join(ROOT, "config", "params.yaml"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "code", "03_detect_validate.py"), "--root", tmp],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + r.stdout
        ev = pd.read_csv(os.path.join(tmp, "data", "processed", "event_outcomes.csv"))
        got = dict(zip(ev.event_id, ev.outcome))
        assert got == fixture.EXPECTED, got
        e1 = ev[ev.event_id == "E1"].iloc[0]
        assert e1.assigned_wall == "E", e1.assigned_wall          # located by lon/lat, no wall_id given
        # creep starts 136 days before failure; the 3-sigma rule can only fire once the creep
        # outpaces the noise (~0.1 m/yr here), so the warning must fall inside that span
        assert 1 <= e1.lead_days < 136, e1.lead_days
        cov = pd.read_csv(os.path.join(tmp, "data", "processed", "wall_coverage.csv")).set_index("wall_id")
        assert cov.loc["W", "geometry_visible_frac"] < 0.05
        assert cov.loc["E", "usable_frac"] > 0.9
        stats = json.load(open(os.path.join(tmp, "paper", "stats.json")))
        c = stats["combined"]
        assert c["n_warned"] == 1 and c["n_missed"] == 1 and c["n_not_observable"] == 2
        # print for the record (alerts without events come from the synthetic seasonal delay)
        print(f"    synthetic: lead E1 = {int(e1.lead_days)} days; alert episodes {c['n_alert_episodes']}, "
              f"without reported event {c['n_alerts_without_reported_event']}")


def test_excluded_operator_refused():
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        fixture.build_project(tmp, os.path.join(ROOT, "config", "params.yaml"))
        p = os.path.join(tmp, "config", "sites.yaml")
        cfg = yaml.safe_load(open(p))
        cfg["sites"][0]["operator"] = "Employer Co Mining LLC"
        yaml.safe_dump(cfg, open(p, "w"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "code", "03_detect_validate.py"), "--root", tmp],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "excluded operator" in (r.stderr + r.stdout)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print("ALL TESTS PASSED" if not failed else f"{failed} TEST(S) FAILED")
    sys.exit(1 if failed else 0)
