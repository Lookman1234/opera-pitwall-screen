# Your verification checklist

*Plain-language: before anything goes public under your name, you check it. Parts 1, 2 and 4 can be done now. Parts 3 and 5 fill in once the real data has run (I will add the exact rows, numbers and links then). Tick each box and add the date.*

## Part 1: The code works (15 min, can do now)

Pick one:
- [ ] **Option A, run it yourself.** In a terminal in the project folder: `pip install numpy scipy pandas matplotlib pyyaml` then `python tests/run_tests.py`. The last line should read `ALL TESTS PASSED`. ___
- [ ] **Option B, on GitHub.** After upload, open the **Actions** tab. The "Tests" run should show a green tick. ___

Then open `tests/fixture.py` and read its top paragraph: four fake walls, each with a planted answer. Confirm with me that those four cases are the ones you would want any screening method tested on, or tell me what to add (for example, a toppling failure, or a wall being actively mined). ___

## Part 2: Check the sources (15 min, can do now)

- [ ] Open https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1. It loads, says 30 m posting, North America coverage, Sentinel-1 from mid-2016. ___
- [ ] Open https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-static-v1-1. It loads. ___
- [ ] Licenses: OPERA data is NASA open data with no restrictions; MSHA data is US government public domain. Confirm nothing you add (wall outlines, event notes) comes from your employer's confidential records. ___

## Part 3a: Check the automatic wall outlines (10 min, after the first run)

- [ ] Open `paper/figures/continental_auto_walls.png`. The blue ring should follow the Continental Pit's walls, and the section labelled `W_E = D_East` should be the east highwall that failed in November 2022. Compare with Google Maps satellite view of Butte. ___
- [ ] The orange "stable" area should avoid the East Dump Complex, tailings and the Berkeley Pit lake. If it does not, tell me where it is wrong and I will cut those areas out. ___

## Part 3: Check the real results by hand (60 to 90 min, after the real run)

*To be filled with exact files and rows after the GitHub run. It will include:*
- [ ] `data/processed/granule_layers.txt` matches the layer names in `code/pitwall/disp_io.py` (I will compare them for you first). ___
- [ ] OPERA's sign convention (positive = toward or away from the satellite) confirmed from the product documentation. ___
- [ ] Each event in `config/events.csv`: date and wall checked against its source link. ___
- [ ] Each "warned" event: open the timeline figure and confirm the alert band sits before the failure line. ___
- [ ] Three alerts without a reported event: you judge from your knowledge whether each wall section was active, being mined, or genuinely moving. ___
- [ ] Wall visibility for each pit matches your understanding of the pit's orientation relative to the satellite. ___

## Part 4: Your decisions (10 min, can do now)

Each is set in `config/params.yaml`. Reply with your choice, or "defaults".
- [ ] **Pixel quality cut (coherence_min).** 0.6 (recommended): fewer, cleaner wall pixels. 0.4: more wall coverage, more noise and more alerts without events. Your choice: ___
- [ ] **Use OPERA's own "trust this pixel" mask?** Yes (recommended for the main result), and report "No" as a sensitivity check, because the mask may hide the fastest-moving rock. Your choice: ___
- [ ] **Alert threshold (k_sigma).** 3 (recommended): an alert means movement clearly above noise. 2: earlier warnings, many more alerts without events. Your choice: ___
- [ ] **Smallest patch that counts (min_cluster_pixels).** 3 pixels, about 2,700 m2 (recommended). 1 pixel: catches small failures but single noisy squares too. Your choice: ___
- [ ] **How early can an alert count as a warning (lead_window_days)?** 180 days (recommended): matches the slow creep often seen before large slope failures. 90 days: stricter, fewer warned events. Your choice: ___

## Part 5: Before it goes public (15 to 30 min, after the real run)

- [ ] README summary and paper abstract rewritten in your own words. ___
- [ ] Name, ORCID, affiliation, email correct in `AUTHORS.json`. ___
- [ ] You have read `docs/LIMITATIONS.md` and agree with it. ___
- [ ] No pit in `config/sites.yaml` is operated by your employer, and the employer appears in `exclude_operators`. ___
- [ ] Draft stamps removed (`python code/04_figures.py --final`) and `python scripts/publish_gate.py .` passes. ___
- [ ] Evidence log row written on release day. ___

**When every box is ticked, reply in your own words that you have checked the package and approve publishing.**

---

## Approval record

- **2026-10-13, v0.1.0 (software release):** Lukman Alabede confirmed in his own words that he had read and verified the package, and approved publishing. This covers the method, the code, the synthetic tests, the documentation and the default decisions in Part 4. It does not cover real-data results, which did not exist at the time.
- **Next approval needed:** after the first real-data run, Parts 3 and 3a and the manuscript need a second verification before any results, the preprint, or a results release go out.
