# Start Here: OPERA Pit-Wall Screen

*Read this first. It explains your project in plain language. Words in bold are explained in [GLOSSARY.md](GLOSSARY.md).*

## What you are building

A free, repeatable test of whether NASA's public satellite ground-movement maps can spot open-pit mine walls that are starting to move before they fail.

## Why it matters

Open-pit walls sometimes slide or collapse. Big operators pay for private radar and survey systems to watch their walls, but those results are never public. Regulators, smaller mines, nearby communities, and researchers have no shared, public answer to a simple question: can the free federal data see this movement at all, and where does it go blind?

Since 2025, NASA's OPERA project has published ready-made ground-movement maps covering the United States and much of North America, updated every 6 to 12 days (depending on how many satellites are flying), back to mid-2016. We have not yet found a published, repeatable check of how well it works on mine walls (the literature search is part of the build). This project does that check, and it shares every step so anyone can repeat it on any pit.

Think of it like testing a free smoke detector against a list of real past fires. You want to know how many fires it caught, how many false alarms it gave, how early it warned, and which rooms it cannot see into.

## Where the information comes from

All sources are free and public. One needs a free NASA login.

| Source | In plain terms | What one piece looks like | Link |
|---|---|---|---|
| OPERA DISP-S1 (NASA / JPL) | Satellite radar maps of how much the ground moved toward or away from the satellite, every 6 to 12 days, 30 m squares, mid-2016 to now | One map of one area for one date, saying "this 30 m square moved 1.2 cm since the starting date" | https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1 |
| OPERA DISP-S1-STATIC | The fixed viewing-angle file that goes with each map, showing which squares the satellite cannot see (hidden behind a slope, or squashed) | One map of viewing angles and a "cannot see here" mask | https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-static-v1-1 |
| Pit wall outlines (PitGeom, your companion project) | Drawn outlines of each pit wall | One wall: its outline and which way it faces | Your PitGeom output, or hand-drawn for the pilot |
| Wall failure dates (GroundFall-US, your companion project) | A list of reported wall failures with a date and place | One event: mine, date, location, size if known | Your GroundFall-US output, or MSHA records for the pilot |
| MSHA open data (fallback for the pilot) | The federal mine-safety agency's public accident and mine lists, updated weekly | One reported accident: mine ID, date, type | https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp |

## What you will have at the end

- [ ] **A public project page** on GitHub with the full pipeline anyone can run on any pit
- [ ] **A permanent citation number (DOI)** from Zenodo for the code and the pilot results
- [ ] **A validation preprint**: did the free data see wall movement before reported failures, how often did it raise false alarms, and where it cannot see
- [ ] **A coverage map per pit**: which wall sections the satellite can and cannot watch
- [ ] Later: the same test with NISAR (a newer NASA radar satellite that sees through more surface change)

## How it connects to your work

It turns your mining ground-control expertise into a public method that any US regulator, operator, or researcher can use to screen pit walls nationwide for free, and it states plainly where the free data is not good enough.

## What you need to do

| Your task | When | Time |
|---|---|---|
| Create accounts (ORCID, GitHub, Zenodo, NASA Earthdata) | Now | 20 min |
| Answer four setup questions | Now | 10 min |
| Start the real-data download with one button on GitHub (guided) | When the code is ready | 15 min plus waiting |
| Check the results using the checklist | When the draft is ready | 2 to 3 hours |
| Approve publishing | After checking | 5 min |
| Submit the preprint yourself, using the guide | After publishing | 20 min |

## The steps ahead

1. **Pipeline built and tested.** The code is written and proven on a made-up pit where we already know the right answer.
2. **Real data collected.** The NASA maps for your two pilot pits are downloaded, with a record of exactly what came from where.
3. **Maps stitched and cleaned.** Each pit becomes one movement history per 30 m square, with unreliable squares removed.
4. **Movement detected and compared to failures.** Hits, misses, false alarms, warning time, and blind spots.
5. **Figures and draft preprint.** Every number in the text comes straight from the data.
6. **Ready for your check.** You verify, then we publish.

*You are here: step 1.*
