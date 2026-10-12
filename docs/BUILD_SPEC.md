# Build spec

*Plain-language header: the one-page plan the whole build follows. The table at the bottom says what each line means for you. If the project changes shape, this file changes first.*

```
PROJECT:        OPERA Pit-Wall Screen. Archetypes: validation study (6) + pipeline/tool (2).
QUESTION:       Can NASA's free OPERA DISP-S1 ground-movement product detect open-pit wall
                movement before reported wall failures, and which walls can it not see?
SOURCES:        OPERA L3 DISP-S1 v1 (NASA JPL / ASF DAAC), 30 m UTM, Sentinel-1 C-band,
                mid-2016 to present, HDF5 granules per frame. Open, no use restrictions;
                download needs a free Earthdata login.
                https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1
                OPERA L3 DISP-S1-STATIC v1 (line-of-sight vectors, layover/shadow mask).
                https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-static-v1-1
                Wall outlines: PitGeom (companion project) or author-drawn GeoJSON.
                Failure events: GroundFall-US (companion project) or author-reviewed MSHA
                accident records (https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp).
UNIT:           Wall x satellite track x acquisition date (detection); reported failure (validation).
MEASURES:       Rolling 72-day LOS velocity per 30 m pixel; stable-ground noise (robust sigma);
                alert = >=3 contiguous wall pixels above max(3 sigma, 2 cm/yr) on >=2 dates in a row;
                outcome per failure = warned / detected after / missed / not observable;
                warning lead time (days); alerts without a reported event per wall-year;
                wall visibility (geometry, coherence, LOS sensitivity to downslope motion);
                C-band phase-aliasing ceiling (lambda/4 per revisit).
OUTPUTS:        code/ pipeline; data/processed/{event_outcomes,alerts,wall_coverage}.csv;
                paper/stats.json; paper/figures/*_coverage.png, *_timelines.png;
                validation preprint (docx, built from stats.json); Zenodo release.
VENUES:         GitHub + Zenodo DOI (code and pilot results) -> EarthArXiv preprint ->
                journal (e.g. an open engineering-geology or remote-sensing journal) ->
                NISAR comparison as v2.
VERIFY POINTS:  pilot pit choice and exclusion of employer pits; wall outlines and stable
                ground; each event's date, wall and source; alert thresholds (params.yaml
                DECISION lines); DISP-S1 layer names and sign convention on first real granule.
LICENSE:        Code MIT; derived data, figures and text CC BY 4.0 (OPERA data credited to
                NASA/JPL-Caltech and ASF DAAC). Pending author confirmation.
ASSUMPTIONS:    Real-data download runs on GitHub Actions (this build workspace cannot reach
                NASA servers). PitGeom and GroundFall-US may not exist yet; inputs are
                generic GeoJSON/CSV so either can be plugged in later. Brief's "January 2027"
                is a plan date, not a reason to wait.
```

## What each line means for you

| Line | In plain words |
|---|---|
| Question | The one thing the paper answers: does the free data see walls moving before they fail, and where is it blind? |
| Sources | Two NASA files (the movement maps, and a file saying where the satellite cannot see), your wall outlines, and your list of failures. |
| Unit | Every row in the main results table is one reported failure. |
| Measures | "Warned" means an alert went up before the failure. "Lead time" is how many days early. "Not observable" means the satellite could not see that wall then, which is itself a key finding. |
| Outputs | Code anyone can rerun, three results tables, two figures per pit, and a short paper. |
| Venues | GitHub and Zenodo first (permanent citation), then a preprint, then a journal. |
| Verify points | The choices only you can make as the mining expert. Each is a plain question in the checklist. |
| License | Anyone may reuse it if they credit you. |
| Assumptions | What I went ahead with without your answer. Correct any of them. |
