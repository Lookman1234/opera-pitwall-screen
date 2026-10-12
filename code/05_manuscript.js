#!/usr/bin/env node
/*
 Step 5: build the validation preprint (paper/manuscript.docx) from the stats file.

 Plain-language header: this writes the paper. Every number in it is read from
 paper/stats.json and config/params.yaml, which the pipeline writes, so the text
 can never disagree with the data. Rerun it after any data change. Sections that
 need your own words, or results that do not exist yet, are left as bracketed
 [VERIFY ...] notes, and the publish check refuses to go ahead while any remain.
 The DRAFT banner comes off only with --final, after your verification.

 Run: node code/05_manuscript.js [--root .] [--final]
 Needs: npm package "docx" (npm install docx), and js-yaml is NOT required (params are read from stats.json
 when present, else parsed simply from config/params.yaml).
*/
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow,
  TableCell, WidthType, ShadingType, BorderStyle, Footer, PageNumber, ExternalHyperlink,
} = require("docx");

const args = process.argv.slice(2);
const root = args.includes("--root") ? args[args.indexOf("--root") + 1] : ".";
const final = args.includes("--final");
const rd = (p) => path.join(root, p);

const authors = JSON.parse(fs.readFileSync(rd("AUTHORS.json"), "utf8")).authors;
const statsPath = rd("paper/stats.json");
const stats = fs.existsSync(statsPath) ? JSON.parse(fs.readFileSync(statsPath, "utf8")) : null;
function readParams() {
  if (stats) return stats.params;
  const out = {};
  for (const line of fs.readFileSync(rd("config/params.yaml"), "utf8").split("\n")) {
    const m = line.match(/^(\w+):\s*([^#\s]+)/);
    if (m) out[m[1]] = isNaN(Number(m[2])) ? m[2] === "true" ? true : m[2] === "false" ? false : m[2] : Number(m[2]);
  }
  return out;
}
const P = readParams();
const limitations = fs.readFileSync(rd("docs/LIMITATIONS.md"), "utf8").split("\n")
  .filter((l) => /^\d+\.\s/.test(l)).map((l) => l.replace(/^\d+\.\s*/, "").replace(/\*\*/g, "").replace(/`/g, ""));

const FONT = "Arial";
const PENDING = "[VERIFY results pending the real-data run]";
const pct = (x) => (x === null || x === undefined ? PENDING : `${(100 * x).toFixed(0)}%`);
const fmt = (x, d = 0) => (x === null || x === undefined ? PENDING : Number(x).toFixed(d));

function para(text, opts = {}) {
  const runs = (Array.isArray(text) ? text : [text]).map((t) =>
    typeof t === "string" ? new TextRun({ text: t, font: FONT, size: 22, ...(opts.run || {}) }) : t);
  return new Paragraph({ children: runs, spacing: { after: 140, line: 300 }, alignment: opts.align, ...(opts.p || {}) });
}
const h = (text, level = HeadingLevel.HEADING_1) =>
  new Paragraph({ heading: level, children: [new TextRun({ text, font: FONT, bold: true, size: level === HeadingLevel.HEADING_1 ? 28 : 24 })],
                  spacing: { before: 240, after: 120 } });
const bullet = (text) => new Paragraph({ numbering: { reference: "bullets", level: 0 },
  children: [new TextRun({ text, font: FONT, size: 22 })], spacing: { after: 80 } });
const numbered = (text) => new Paragraph({ numbering: { reference: "numbers", level: 0 },
  children: [new TextRun({ text, font: FONT, size: 22 })], spacing: { after: 80 } });

function table(rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB" };
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({ children: r.map((c, j) => new TableCell({
      width: { size: widths[j], type: WidthType.DXA },
      borders: { top: border, bottom: border, left: border, right: border },
      shading: i === 0 ? { type: ShadingType.CLEAR, fill: "EEEEEE", color: "auto" } : undefined,
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({ children: [new TextRun({ text: String(c), font: FONT, size: 18, bold: i === 0 })] })],
    })) })),
  });
}

function figure(file, caption, n) {
  const p = rd(path.join("paper/figures", file));
  if (!fs.existsSync(p)) return [para(`[VERIFY Figure ${n} pending: ${file} is produced by the real-data run]`)];
  const buf = fs.readFileSync(p);
  const w = buf.readUInt32BE(16), hgt = buf.readUInt32BE(20);   // PNG header
  const width = 560, height = Math.round((hgt / w) * width);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: buf,
      transformation: { width, height }, altText: { title: `Figure ${n}`, description: caption, name: file } })] }),
    para([new TextRun({ text: `Figure ${n}. `, bold: true, font: FONT, size: 20 }), new TextRun({ text: caption, font: FONT, size: 20 })]),
  ];
}

// ---------- content ----------
const c = stats ? stats.combined : {};
const cov = stats ? stats.coverage : {};
const tracks = stats ? stats.tracks : [];
const sites = stats ? stats.sites : [];
const alias = tracks.length ? tracks[0].max_unambiguous_los_m_per_yr : null;
const revisit = tracks.length ? tracks[0].median_revisit_days : null;
const firstDate = tracks.length ? tracks.map((t) => t.first_date).sort()[0] : null;
const lastDate = tracks.length ? tracks.map((t) => t.last_date).sort().slice(-1)[0] : null;

const title = "Can NASA's open OPERA DISP-S1 InSAR product screen open-pit walls? A reproducible two-site validation against documented wall failures";
const authorLine = authors.map((a) => a.name).join(", ");
const affLine = authors.map((a) => `${a.name}: ${a.affiliation}; ORCID ${a.orcid}; ${a.email}`).join(" | ");

const children = [];
if (!final) children.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({
  text: "DRAFT - unverified. Do not cite or circulate.", bold: true, color: "B00020", font: FONT, size: 22 })] }));
children.push(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: title, bold: true, font: FONT, size: 32 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: authorLine, font: FONT, size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: affLine, font: FONT, size: 18, color: "52514E" })] }),
);

children.push(h("Abstract"));
children.push(para(stats
  ? `Free, nationwide satellite displacement products could let regulators, smaller operators and researchers screen open-pit walls that are not otherwise monitored in public. We test NASA's OPERA DISP-S1 product (Sentinel-1 C-band, 30 m, ${firstDate} to ${lastDate}) against ${c.n_events} documented wall failures at ${sites.length} US open pits with a reproducible pipeline. ${c.n_events_observable} failures were observable; an alert preceded ${c.n_warned} of them (${pct(c.warning_rate)}, 95% CI ${pct(c.warning_rate_ci95[0])} to ${pct(c.warning_rate_ci95[1])}), with a median lead of ${fmt(c.lead_days_median)} days. The pipeline raised ${c.n_alert_episodes} alert episodes, ${c.n_alerts_without_reported_event} without a reported failure. Across ${cov.n_wall_tracks} wall-track combinations the median usable fraction of wall pixels was ${pct(cov.median_usable_frac)}. [VERIFY author to rewrite the abstract in their own words after checking every number]`
  : `[VERIFY abstract pending the real-data run; it is generated from paper/stats.json and then rewritten by the author]`));

children.push(h("1. Introduction"));
children.push(para("Open-pit wall failures endanger workers and equipment and interrupt production. Large operators watch their walls with ground-based radar, prisms and commercial satellite InSAR, but those records are private. Regulators, smaller mines, nearby communities and researchers therefore have no shared, public evidence of whether free satellite data can see wall movement, or where it cannot."));
children.push(para("Retrospective studies show that satellite InSAR can record accelerating movement before large slope failures, including an open-pit slope (Carlà et al., 2019), and long-running weak signals before the 2013 Manefay slide at Bingham Canyon (Gaida et al., 2019). A recent back-analysis of two wall failures at Bald Mountain Mine, Nevada, used commercially processed Sentinel-1 data and found precursory movement months before the 2023 Saga Pit failure (Bourgeois et al., 2024). These studies used custom processing. Since 2025, NASA's OPERA project has distributed a standardized displacement product, DISP-S1, over the United States and much of North America at 30 m posting from mid-2016, free of charge."));
children.push(para("We ask whether that free, standardized product can serve as a first-pass screen for pit walls: does it show movement before documented failures, how often does it raise alerts without a reported failure, and which walls can it not see at all? We answer with a fully reproducible pipeline and report the failure modes as carefully as the successes."));

children.push(h("2. Data"));
children.push(bullet("OPERA L3 DISP-S1 v1 (NASA JPL; distributed by the ASF DAAC): line-of-sight (LOS) displacement from Sentinel-1 interferometric wide-swath data, HDF5 granules per frame on a 30 m UTM grid, each relative to a reference date that resets periodically [VERIFY dataset DOI and version from the ASF landing page]."));
children.push(bullet("OPERA L3 DISP-S1-STATIC v1: per-frame LOS unit vectors and a layover/shadow mask."));
children.push(bullet("Copernicus DEM GLO-30 (ESA/Airbus; AWS Open Data): 30 m elevation used to outline walls and candidate stable ground automatically. Its acquisitions date from about 2011 to 2015."));
children.push(bullet("Failure events: dated wall failures from public records, each with a source link (Table 1). Pits operated by the author's employer are excluded by a private filter enforced on every run."));
if (stats || fs.existsSync(rd("config/events.csv"))) {
  const lines = fs.readFileSync(rd("config/events.csv"), "utf8").trim().split("\n").slice(1);
  const rows = [["Event", "Site", "Wall (reported)", "Date", "Size", "Source"]];
  for (const l of lines) {
    const f = l.match(/("([^"]|"")*"|[^,]*)(,|$)/g).map((s) => s.replace(/,$/, "").replace(/^"|"$/g, ""));
    rows.push([f[0], f[1], f[2], f[3], f[6], f[7]]);
  }
  children.push(para([new TextRun({ text: "Table 1. ", bold: true, font: FONT, size: 20 }), new TextRun({ text: "Documented wall failures used for validation.", font: FONT, size: 20 })]));
  children.push(table(rows, [1500, 1100, 1200, 1100, 1300, 3160]));
  children.push(para(""));
}

children.push(h("3. Methods"));
children.push(h("3.1 Time series", HeadingLevel.HEADING_2));
children.push(para(`For each site and frame, granules are cropped to the site box and chained into one cumulative LOS series per pixel: a granule giving displacement from its reference date r to secondary date s is placed at D(s) = D(r) + d, with D at the earliest reference set to zero. A missing link starts a new segment, and velocities are never fitted across segments. Pixels are kept when temporal coherence is at least ${P.coherence_min}${P.use_recommended_mask ? " and OPERA's recommended mask is set" : ""}. Each date is referenced to the median of valid stable-ground pixels; dates with fewer than ${P.stable_min_pixels} such pixels are dropped. Automatic stable ground is gently sloping ground (at most ${P.auto_stable_slope_max_deg} degrees) in a ring outside the pit, reduced to the ${pct(P.auto_stable_keep_frac)} of candidates with the smallest whole-record trend.`));
children.push(h("3.2 Walls", HeadingLevel.HEADING_2));
children.push(para(`Wall pixels are DEM pixels steeper than ${P.auto_wall_slope_min_deg} degrees within a search radius of the pit centre, grouped by facing direction (8 sectors) and by side of the pit. Where no pit centre is known, closed depressions more than 40 m below a 2.5 km median-smoothed surface are taken as pits. Reported walls are mapped to these sections by name (for example, the D East highwall of the Continental Pit is the west-facing section on the east side). Wall pixels in layover or shadow are removed.`));
children.push(h("3.3 Alert rule", HeadingLevel.HEADING_2));
children.push(para(`For every date, LOS velocity is fitted by least squares over the trailing ${P.window_days} days (at least ${P.min_obs_in_window} dates). Noise is the robust standard deviation (1.4826 x median absolute deviation) of stable-ground velocities on the same date. A wall pixel exceeds the threshold when its speed is above the larger of ${P.k_sigma} x noise and ${fmt(P.velocity_floor_m_per_yr * 100, 0)} cm/yr. An alert is raised when a connected patch of at least ${P.min_cluster_pixels} such pixels appears on ${P.persistence_epochs} consecutive dates.`));
children.push(h("3.4 Validation", HeadingLevel.HEADING_2));
children.push(para(`Each failure is classed as warned (an alert raised within ${P.lead_window_days} days before it), detected after (raised up to ${P.late_grace_days} days after), missed (wall observable, no alert), or not observable (fewer than ${P.min_obs_in_window} usable dates on that wall in the ${P.lead_window_days} days before). With two satellite tracks, the better outcome counts. Warning rates carry Wilson 95% intervals. Alerts with no failure on record are reported as "alerts without a reported event", not false alarms, because public failure records are incomplete. Wall visibility is reported as the fraction of wall pixels that are geometrically visible and coherent on at least ${pct(P.coherent_epoch_frac)} of dates, and as the sensitivity of the LOS to downslope motion. The fastest LOS motion one revisit can record without phase ambiguity, one quarter wavelength per interval, is reported per track.`));

children.push(h("4. Results"));
if (stats) {
  children.push(para(`Data spanned ${firstDate} to ${lastDate} with a median revisit of ${fmt(revisit)} days, giving an aliasing ceiling of about ${fmt(alias * 100, 0)} cm/yr of LOS motion. Of ${c.n_events} failures, ${c.n_warned} were warned, ${c.n_detected_after} detected after, ${c.n_missed} missed and ${c.n_not_observable} not observable${c.n_unlocated ? `; ${c.n_unlocated} could not yet be placed on a wall and are excluded` : ""}. Lead times (days): ${c.lead_days.length ? c.lead_days.join(", ") : "none"}.`));
  const rows = [["Site", "Track", "Dates", "Revisit (d)", "Alert episodes", "Without event", "Warned / observable"]];
  for (const t of tracks) rows.push([t.site_id, t.frame, `${t.first_date} to ${t.last_date}`, fmt(t.median_revisit_days), t.n_alert_episodes, t.n_alerts_without_reported_event, `${t.n_warned} / ${t.n_events_observable}`]);
  children.push(para([new TextRun({ text: "Table 2. ", bold: true, font: FONT, size: 20 }), new TextRun({ text: "Results by site and satellite track.", font: FONT, size: 20 })]));
  children.push(table(rows, [1300, 900, 2400, 1000, 1300, 1200, 1260]));
  children.push(para(""));
  let n = 1;
  for (const t of tracks) {
    children.push(...figure(`${t.site_id}_${t.frame}_coverage.png`, `Wall visibility, ${t.site_id}, track ${t.frame}: watched, seen but noisy, and not visible (layover or shadow); dashed line, stable reference ground.`, n++));
    children.push(...figure(`${t.site_id}_${t.frame}_timelines.png`, `Fastest wall patch against the alert threshold, ${t.site_id}, track ${t.frame}; shading, alerts; vertical lines, documented failures.`, n++));
  }
  children.push(para("[VERIFY author to describe each event in words, checked against the figures]"));
} else {
  children.push(para(PENDING));
}

children.push(h("5. Discussion"));
children.push(para("[VERIFY author to write: what the results mean for screening pit walls with free data; how they compare with the commercial back-analysis at Bald Mountain; where the free product fails and why; what a regulator or smaller operator could do with it]"));

children.push(h("6. Limitations"));
for (const l of limitations) children.push(numbered(l));

children.push(h("Data and code availability"));
children.push(para("All code, configuration, processed outputs and provenance records are in the project repository [VERIFY repository URL] and archived with a DOI [DOI pending first release]. Code: MIT licence. Derived data and text: CC BY 4.0. OPERA data courtesy of NASA/JPL-Caltech, distributed by the ASF DAAC. Contains modified Copernicus DEM data."));
children.push(h("Use of AI assistance"));
children.push(para("Software engineering, data handling and drafting mechanics were assisted by an AI model (Claude, Anthropic). The author made every analytic decision, checked every number against the pipeline outputs and sources, and takes responsibility for the content."));
children.push(h("Competing interests"));
children.push(para("[VERIFY author to write the competing-interests statement; the venue's policy decides whether employment must be declared]"));

children.push(h("References"));
const refs = [
  ["Bourgeois, J., Lasich, T., Meda, A., Salzer, J., Sbai, S., Warren, S. (2024). Applications of InSAR for early indication of mine slope instability: back analysis of satellite displacement data. Slope Stability 2024, Belo Horizonte, Brazil. ", "https://stacks.cdc.gov/view/cdc/215697"],
  ["Carlà, T., Intrieri, E., Raspini, F., Bardi, F., Farina, P., Ferretti, A., Colombo, D., Novali, F., Casagli, N. (2019). Perspectives on the prediction of catastrophic slope failures from satellite InSAR. Scientific Reports, 9. ", "https://doi.org/10.1038/s41598-019-50792-y"],
  ["Gaida, M., Morkeh, J., Robotham, M.E., Ross, B., Williams, C., Zebker, M. (2019). Assessment of historic InSAR monitoring data prior to the Manefay slide at the Bingham Canyon Mine using the latest analytical techniques. 53rd US Rock Mechanics/Geomechanics Symposium, ARMA 19-2881. ", "https://stacks.cdc.gov/view/cdc/225985"],
  ["Montana Department of Environmental Quality, Hard Rock Mining Bureau (2022). Field inspection report, Montana Resources Operating Permit 00030, inspected 22 November 2022. ", "https://montanaresources.com/wp-content/uploads/2024/11/Field-Inspection-Report-11-22-2022.pdf"],
  ["OPERA Project, NASA Jet Propulsion Laboratory. OPERA L3 Surface Displacement from Sentinel-1 (DISP-S1), version 1. ASF DAAC. ", "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1"],
  ["European Space Agency, Airbus (2022). Copernicus DEM GLO-30. AWS Open Data. ", "https://registry.opendata.aws/copernicus-dem/"],
];
for (const [t, u] of refs) children.push(new Paragraph({ spacing: { after: 100 }, indent: { left: 360, hanging: 360 }, children: [
  new TextRun({ text: t, font: FONT, size: 20 }),
  new ExternalHyperlink({ link: u, children: [new TextRun({ text: u, style: "Hyperlink", font: FONT, size: 20 })] })] }));

const doc = new Document({
  creator: authorLine, title,
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: "bullet", text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: "decimal", text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: final ? "" : "DRAFT  |  ", font: FONT, size: 16, color: "B00020" }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16 })] })] }) },
    children,
  }],
});
fs.mkdirSync(rd("paper"), { recursive: true });
Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(rd("paper/manuscript.docx"), b);
  console.log(`paper/manuscript.docx written (${stats ? "with results" : "results pending"}${final ? ", final" : ", DRAFT"})`);
});
