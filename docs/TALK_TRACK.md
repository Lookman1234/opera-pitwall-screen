# Talking about OPERA Pit-Wall Screen

*Plain-language header: what to say when someone asks about this project. It claims only what v0.1.0 supports: a tested method, no real results yet.*

## 60-second version
**The problem:** open-pit mine walls sometimes slide or collapse. Big operators watch their walls with private radar and survey systems, but none of that is public. Regulators, smaller mines and researchers have no shared answer to a basic question: can free government satellite data see walls starting to move?

**What I built:** a free, open pipeline that takes NASA's new nationwide ground-movement product, called OPERA DISP-S1, and tests it against documented wall failures. It works out which walls the satellite can see, raises an alert when a wall moves clearly faster than the background noise, and checks whether those alerts came before real failures.

**What it shows or makes possible:** version 0.1 is the method and software, tested on a synthetic pit where the right answer is known. The pilot on two US pits, the Continental Pit in Montana and the Saga Pit in Nevada, is next. The project reports where the free data fails as carefully as where it works.

**Who can use it:** state and federal mine regulators, smaller operators without monitoring budgets, and researchers. Anyone can rerun it on any pit.

**Where it is:** github.com/Lookman1234/opera-pitwall-screen, with a permanent Zenodo DOI once archived.

## Two-sentence version
I built an open, reproducible pipeline that tests whether NASA's free nationwide satellite ground-movement data can screen open-pit mine walls for movement before they fail. It reports both detections and blind spots, so regulators and smaller operators know when the free data can be trusted.

## Questions you may be asked
1. **Where does the data come from?** NASA's OPERA project, which processes European Sentinel-1 radar satellite images into ground-movement maps, free, every 6 to 12 days since 2016. Wall outlines come from a free European elevation model, and the failure dates come from public regulator and research records.
2. **What are its limits?** The satellite sees movement along one slanted line only. Steep walls can be hidden, very fast movement breaks the measurement, and maps arrive days apart, so this is screening, not a real-time alarm. Public failure lists are incomplete. All 16 limits are written down in the project.
3. **Why does this matter for the United States?** There are hundreds of open pits in the US, and most have no public monitoring record. A free, tested screening method lets regulators and smaller operators prioritise walls for attention, using data taxpayers already fund.
