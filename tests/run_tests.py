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


def test_auto_walls_name_east_wall():
    from pitwall import dem
    x, y = fixture.grid()
    xx, yy = np.meshgrid(x, y)
    r = np.hypot(xx - fixture.X0, yy - fixture.Y0)
    z = 2000 - np.clip((1050 - r) / 600, 0, 1) * 600.0          # 45-degree walls between r=450 and 1050
    masks, props = dem.auto_walls(z, x, y, (fixture.X0, fixture.Y0), 1200)
    assert "faces_W_E" in masks and "faces_S_N" in masks and "faces_E_W" in masks, sorted(masks)
    m = masks["faces_W_E"]
    assert (xx[m] > fixture.X0).all()                            # east side of the pit
    assert abs(props["faces_W_E"]["aspect_deg"] - 270) < 10, props["faces_W_E"]
    assert abs(props["faces_W_E"]["slope_deg"] - 45) < 3, props["faces_W_E"]
    st = dem.auto_stable(z, x, y, (fixture.X0, fixture.Y0), 1300, 1800)
    assert st.any() and not (st & (r < 1300)).any()


def test_district_mode_finds_two_pits():
    import importlib.util
    spec = importlib.util.spec_from_file_location("autowalls", os.path.join(ROOT, "code", "01b_auto_walls.py"))
    aw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aw)
    n = 200
    x = 400000.0 + (np.arange(n) + 0.5) * 30
    y = 4500000.0 - (np.arange(n) + 0.5) * 30
    xx, yy = np.meshgrid(x, y)
    z = 2000 + 0.02 * (xx - x[0])                               # gently tilted ground
    for (cx, cy, rad, dep) in [(x[50], y[60], 700, 250), (x[150], y[140], 450, 150)]:
        r = np.hypot(xx - cx, yy - cy)
        z = z - np.clip((rad - r) / rad, 0, 1) * dep * 1.0
        z = np.where(r < rad, np.minimum(z, 2000 + 0.02 * (xx - x[0]) - dep * np.clip((rad - r) / (0.6 * rad), 0, 1)), z)
    labels, pits = aw.dem.find_pits(z)
    assert len(pits) == 2, [(p["area_m2"], p["depth_m"]) for p in pits]
    assert abs(x[int(round(pits[0]["ix"]))] - x[50]) < 120 and abs(y[int(round(pits[0]["iy"]))] - y[60]) < 120
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "config", "sites"))
        params = yaml.safe_load(open(os.path.join(ROOT, "config", "params.yaml")))
        site = {"id": "dist", "name": "Synthetic district (not real)"}
        aw.district(tmp, site, z, x, y, 32612, params, tmp, False)
        zz = np.load(os.path.join(tmp, "data", "processed", "dist", "auto_walls.npz"))
        names = [str(s) for s in zz["names"]]
        assert any(s.startswith("pit1_faces_") for s in names) and any(s.startswith("pit2_faces_") for s in names)
        assert os.path.exists(os.path.join(tmp, "dist_auto_walls.png"))


def test_regrid_nearest_identity_and_shift():
    from pitwall import dem
    x, y = fixture.grid()
    m = np.zeros((len(y), len(x)), bool)
    m[10:20, 30:40] = True
    assert (dem.regrid_nearest(m, x, y, x, y) == m).all()
    shifted = dem.regrid_nearest(m, x, y, x + 14.0, y - 14.0)    # under half a pixel: same cells
    assert (shifted == m).all()


def test_refine_stable_drops_settling_ground():
    from pitwall import sitemasks
    dates, D, coh, _ = fixture.truth()
    D = D.copy()
    x, y = fixture.grid()
    cand = np.zeros(D.shape[1:], bool)
    cand[:20, :] = True                                           # candidate strip along the top
    days = np.array([(d - dates[0]).days for d in dates]) / 365.25
    D[:, :20, :10] += (-0.05 * days)[:, None, None]               # a settling "dump top" inside the strip
    s = stk.rebase(fixture.granules_from_truth(dates, D, coh), 0.0, False)
    kept = sitemasks.refine_stable(s, cand)
    assert kept[:20, :10].sum() == 0, int(kept[:20, :10].sum())
    assert kept.sum() > 0.3 * cand.sum()


def test_unlocated_event_is_not_counted():
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        fixture.build_project(tmp, os.path.join(ROOT, "config", "params.yaml"))
        with open(os.path.join(tmp, "config", "events.csv"), "a") as f:
            f.write("X9,synth,Saga_N,2018-09-01,,,,test,,test,wall name not on this site\n")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "code", "03_detect_validate.py"), "--root", tmp],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        c = json.load(open(os.path.join(tmp, "paper", "stats.json")))["combined"]
        assert c["n_unlocated"] == 1 and c["n_events_observable"] == 2 and c["n_not_observable"] == 2, c


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


def test_end_to_end_with_automatic_walls():
    import importlib.util
    import yaml
    spec = importlib.util.spec_from_file_location("autowalls", os.path.join(ROOT, "code", "01b_auto_walls.py"))
    aw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aw)
    with tempfile.TemporaryDirectory() as tmp:
        fixture.build_project(tmp, os.path.join(ROOT, "config", "params.yaml"))
        for f in ("synth_walls.geojson", "synth_stable.geojson"):
            os.remove(os.path.join(tmp, "config", "sites", f))
        cfgp = os.path.join(tmp, "config", "sites.yaml")
        cfg = yaml.safe_load(open(cfgp))
        lon, lat = geo.utm_to_lonlat(fixture.X0, fixture.Y0, fixture.EPSG, use_pyproj=False)
        cfg["sites"][0].update(pit_center=[float(lon), float(lat)], pit_radius_m=1200,
                               wall_aliases={"N": "faces_S_N", "W": "faces_E_W", "S": "faces_N_S"})
        yaml.safe_dump(cfg, open(cfgp, "w"))
        x, y = fixture.grid()
        xx, yy = np.meshgrid(x, y)
        z = 2000 - np.clip((1050 - np.hypot(xx - fixture.X0, yy - fixture.Y0)) / 600, 0, 1) * 600.0
        params = yaml.safe_load(open(os.path.join(tmp, "config", "params.yaml")))
        names, labels, props, stable, centre = aw.build(cfg["sites"][0], z, x, y, fixture.EPSG, params)
        np.savez_compressed(os.path.join(tmp, "data", "processed", "synth", "auto_walls.npz"), labels=labels,
                            names=np.array(names), aspect=np.array([props[n]["aspect_deg"] for n in names]),
                            slope=np.array([props[n]["slope_deg"] for n in names]), stable=stable, x=x, y=y,
                            epsg=fixture.EPSG, dem=z)
        aw.preview(cfg["sites"][0], z, x, y, names, labels, props, stable, centre,
                   cfg["sites"][0]["wall_aliases"], os.path.join(tmp, "auto_walls.png"), False)
        for script in ("03_detect_validate.py", "04_figures.py"):
            r = subprocess.run([sys.executable, os.path.join(ROOT, "code", script), "--root", tmp],
                               capture_output=True, text=True)
            assert r.returncode == 0, script + r.stderr + r.stdout
        ev = pd.read_csv(os.path.join(tmp, "data", "processed", "event_outcomes.csv"))
        got = dict(zip(ev.event_id, ev.outcome))
        assert got == fixture.EXPECTED, got
        assert ev.set_index("event_id").loc["E1", "assigned_wall"] == "faces_W_E"
        assert os.path.exists(os.path.join(tmp, "paper", "figures", "synth_F99999_coverage.png"))


def test_excluded_operator_refused():
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        fixture.build_project(tmp, os.path.join(ROOT, "config", "params.yaml"))
        p = os.path.join(tmp, "config", "sites.yaml")
        cfg = yaml.safe_load(open(p))
        cfg["sites"][0]["name"] = "Example Employer Pit"
        yaml.safe_dump(cfg, open(p, "w"))
        with open(os.path.join(tmp, "config", "exclude.local.yaml"), "w") as f:
            f.write("exclude:\n  - Example Employer\n")
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
