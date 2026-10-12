# Limitations

*Plain-language header: what this project cannot tell you. Read it before using or citing anything here. Written before any results, so the paper cannot outrun it; real-data findings will be added, not removed.*

1. **Line-of-sight only.** The satellite measures movement toward or away from itself, along a slanted line. A wall moving sideways to that line shows little or no signal even if it moves fast. `wall_coverage.csv` reports this as `los_sensitivity` (0 = blind to downslope motion, 1 = fully sensitive) when wall aspect and slope are given.
2. **Steep walls can be hidden.** Walls facing away from the satellite at angles steeper than its viewing angle fall in radar shadow; walls facing toward it can be squashed (layover). OPERA's STATIC mask marks these; such walls are "not observable", not "missed".
3. **Fast movement breaks the measurement.** C-band radar can record at most about a quarter wavelength (about 1.4 cm) of motion between two passes before the signal wraps around. At a 12-day revisit that is roughly 42 cm/yr; faster final acceleration usually shows up as lost coherence, not as a bigger number. The pipeline reports this ceiling per track (`max_unambiguous_los_m_per_yr`).
4. **Revisit is days, not minutes.** One map every 6 to 12 days cannot replace on-site radar for imminent-failure warning. This project tests screening (which walls deserve attention), not real-time alarms.
5. **30 m squares.** Failures smaller than a few squares (under about 2,700 m2 with the default rule) cannot be resolved.
6. **Active mining changes the surface.** Benches being blasted, loaded, or backfilled lose coherence and may be masked; the pipeline cannot tell mining from instability.
7. **OPERA's own quality mask may remove the pixels that matter.** `use_recommended_mask` is a decision point for this reason.
8. **Event lists are incomplete.** Public records (MSHA) capture mostly accidents with injuries. An alert with no reported failure is called "alert without a reported event", never a "false alarm", because the failure may simply not be on record.
9. **Event dates and locations are uncertain.** Records may give a date but not a wall. Events without a wall assignment are excluded as not observable, which lowers the observable count.
10. **Small sample.** Two pits give few events. Rates come with 95% confidence intervals (Wilson) that will be wide; the pilot shows feasibility and failure modes, not a national accuracy figure.
11. **Atmospheric delay tied to pit depth.** Radar delay changes with height and season, and pit floors sit hundreds of metres below the stable rim used as reference. This can mimic slow seasonal movement on walls and is a likely source of alerts without events.
12. **Stable reference is a judgment.** If "stable" ground actually moves (dumps, leach pads, subsidence), every wall value shifts. The stable area is chosen automatically (or drawn by the author) and checked on the preview map in the checklist.
13. **Version dependence.** Results apply to OPERA DISP-S1 v1 as downloaded on the dates in `PROVENANCE.txt`; reprocessed versions may differ.
14. **Synthetic tests prove the code, not the method.** The test pit checks that the software finds what was planted. It says nothing about real walls.
15. **Automatic walls come from a 2011 to 2015 elevation model.** Walls cut or pushed back after that are missing or misplaced. Automatic stable ground can include settling dumps or tailings; the pipeline keeps only the quieter half of candidates by long-term trend, which removes most but not all of them. Both are checked on the preview map, and a hand-drawn file always overrides them.
16. **Wall names are assigned by rule.** The reported wall (for example "D East highwall") is matched to the automatic section facing the same way on the same side of the pit (`wall_aliases` in config/sites.yaml). If the failure sat across two sections, the match is partial.
