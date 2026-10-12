# OPERA Pit-Wall Screen

**Status:** DRAFT v0.1 (pipeline built and tested on synthetic data; no real-data results yet) | **Maintainer:** Lukman Alabede (Independent Researcher), ORCID [0009-0008-7769-7455](https://orcid.org/0009-0008-7769-7455) | **License:** code MIT, results CC BY 4.0

**In plain terms:** NASA now publishes free satellite maps of ground movement across the United States every 6 to 12 days, back to 2016. This project tests whether those free maps can spot open-pit mine walls starting to move before they fail, and shows exactly which walls the satellite cannot see. Anyone can rerun it on any pit.

New here? Read [docs/START_HERE.md](docs/START_HERE.md) first. Terms are explained in [docs/GLOSSARY.md](docs/GLOSSARY.md).

A reproducible pipeline over OPERA L3 DISP-S1 (Sentinel-1 C-band InSAR, 30 m, mid-2016 onward) that rebases each frame's moving-reference granules into one line-of-sight time series per pixel, references it to author-defined stable ground, raises wall alerts from rolling velocities against stable-ground noise, and scores those alerts against reported wall failures (warned, detected after, missed, not observable), with per-wall visibility from OPERA's STATIC layover/shadow mask and line-of-sight geometry. Pilot: two non-employer US open pits. Planned: NISAR L-band comparison.

## What is here

```
code/01_fetch.py             download DISP-S1 + STATIC for each site (needs Earthdata login)
code/01b_auto_walls.py       wall outlines and stable ground from the Copernicus 30 m elevation model
code/02_stack.py             rebase granules, apply quality masks, stable-ground reference
code/03_detect_validate.py   alerts, wall visibility, event outcomes, paper/stats.json
code/04_figures.py           coverage maps and wall timelines
code/05_manuscript.js        the preprint (paper/manuscript.docx), every number read from paper/stats.json
code/00_events_from_msha.py  optional: candidate events from MSHA accident records
code/pitwall/                the library the scripts use
config/                      sites.yaml, params.yaml (all thresholds), events.csv, wall GeoJSON
tests/                       synthetic pit with a known answer; run_tests.py
docs/                        START_HERE, GLOSSARY, BUILD_SPEC, CODEBOOK, LIMITATIONS,
                             VERIFY_CHECKLIST, NEXT_STEPS, DRAW_WALLS, RUN_ON_GITHUB
.github/workflows/           one-button real-data run; tests on every change
```

## Run it

Easiest: on GitHub, follow [docs/RUN_ON_GITHUB.md](docs/RUN_ON_GITHUB.md) (Actions > Run pipeline).

Locally (Python 3.10+, free Earthdata login in `~/.netrc` or `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`):

```
pip install -r requirements.txt
python tests/run_tests.py              # expect: ALL TESTS PASSED
python code/01_fetch.py
python code/01b_auto_walls.py         # then check paper/figures/<site>_auto_walls.png
python code/02_stack.py --inspect data/raw/<site>/disp/<any file>   # check layer names once
python code/02_stack.py
python code/03_detect_validate.py
python code/04_figures.py
npm install && node code/05_manuscript.js
```

## Sources

| Source | Vintage | License | Accessed |
|---|---|---|---|
| OPERA L3 DISP-S1 v1, NASA JPL / ASF DAAC, https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1 | mid-2016 to download date | NASA open data, no restrictions | see data/raw/PROVENANCE.txt |
| OPERA L3 DISP-S1-STATIC v1, https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-static-v1-1 | per frame | NASA open data | see PROVENANCE.txt |
| Copernicus DEM GLO-30 (AWS Open Data, https://registry.opendata.aws/copernicus-dem/) for automatic wall outlines | acquired about 2011-2015 | free use with attribution (Copernicus DEM licence) | see PROVENANCE.txt |
| Wall outlines override (PitGeom or author-drawn), optional | | CC BY 4.0 | |
| Failure events (GroundFall-US or reviewed MSHA records, https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp) | [pending] | US public domain | |

## Headline numbers

None yet. Real-data results will be written here from `paper/stats.json` after verification.

## Limitations

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) before using or citing anything here.

## Citation

See `CITATION.cff`. DOI: [DOI pending first release]
