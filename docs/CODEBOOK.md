# Codebook

*Plain-language header: what every column in the results tables means. Open it when you check a table.*

All speeds are line-of-sight (LOS), metres per year unless the name says cm. Dates are YYYY-MM-DD.

## data/processed/event_outcomes.csv (one row per reported failure; best result across satellite tracks)

| Column | Meaning | Source / how computed |
|---|---|---|
| event_id, site_id, wall_id, date, lon, lat, size_class, source, source_url, confidence, notes | Copied from config/events.csv | Author-curated event list |
| assigned_wall | Wall the event was matched to | wall_id if given, else nearest wall within event_buffer_m |
| dist_to_wall_m | Distance from event point to that wall (0 if wall_id given) | Pixel-centre distance |
| outcome | warned / detected_after / missed / not_observable / unlocated (reported wall not yet identified on this site; excluded from all rates) | See validate.py |
| lead_days | Days between the alert being raised and the failure (warned only) | Capped at lead_window_days |
| reason | Why not observable, or why detected after | Text |
| frame | Satellite track giving the best outcome | OPERA frame id |

## data/processed/event_outcomes_by_track.csv
Same columns, one row per event per track.

## data/processed/alerts.csv (one row per alert episode)

| Column | Meaning |
|---|---|
| wall_id, site_id, frame | Where |
| first_flag_date | First date the wall exceeded the threshold in this run |
| raised_date | Date the persistence rule was first met (the alert "goes up") |
| end_date | Last flagged date in the run |
| n_epochs | Flagged dates in the run |
| peak_abs_vel_m_per_yr | Fastest pixel speed during the episode |
| max_alert_px | Largest alerting patch (pixels, 900 m2 each) |
| matched_event | event_id that followed (or preceded within late_grace_days); blank = alert without a reported event |

## data/processed/wall_coverage.csv (one row per wall per track)

| Column | Meaning |
|---|---|
| n_pixels, area_m2 | Wall size on the 30 m grid |
| geometry_visible_frac | Share of wall pixels not in layover or shadow |
| coherent_frac | Share valid on at least coherent_epoch_frac of dates |
| usable_frac | Both of the above |
| median_coherence | Median temporal coherence over all dates and wall pixels |
| los_sensitivity | Mean abs(downslope unit vector . LOS unit vector); needs aspect_deg and slope_deg |
| expected_los_sign | Sign a downslope slide should show (+1 toward satellite) [VERIFY OPERA sign convention] |

## data/processed/<site>/F<frame>_epochs.csv (one row per wall per date)

| Column | Meaning |
|---|---|
| n_valid_px | Visible, valid wall pixels with a velocity that date |
| noise_sigma_m_per_yr | 1.4826 x MAD of stable-ground velocities that date |
| threshold_m_per_yr | max(k_sigma x noise, velocity_floor) |
| alert_px | Wall pixels in patches of at least min_cluster_pixels above threshold |
| max_abs_vel_m_per_yr | Fastest valid wall pixel |
| alert_x, alert_y | Centroid of alerting pixels (UTM metres) |

## Wall names
Automatic wall sections are named `faces_<direction>_<side>`: the compass direction the face looks toward, then the side of the pit it sits on. `faces_W_E` is on the east side, facing west (the usual east wall). `wall_aliases` in config/sites.yaml maps reported names such as `D_East` onto these. `wall_id_reported` in the outcome tables keeps the name as reported.

## paper/stats.json
Every number quoted anywhere, plus the exact parameters used. `combined` holds the headline counts; `tracks` holds per-track counts, the revisit interval and the C-band aliasing ceiling; `coverage` summarises wall visibility.
