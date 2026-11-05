# US Soil Explorer v3.2

Point-level, component-level, and horizon-level summaries from USDA-NRCS SSURGO.

## Run (no Python needed)

1. Extract the ZIP.
2. Double-click **`index.html`**. It opens in your web browser (Chrome, Edge or Firefox recommended).
3. Upload a CSV with `Latitude`, `Longitude`, and optionally `Sample_ID` columns, or click a map point.
4. Choose **Fetch USDA data** and export the CSV files and the texture triangle.

The dashboard queries USDA Soil Data Access **directly from the browser**, so there's nothing to install and no server to start. An Internet connection is required for the USDA queries and the map tiles. To share it with colleagues, send the folder, or host `index.html` on any static web host (GitHub Pages, a university web space, SharePoint, etc.).

### Optional fallback: local Python server

Some institutional networks or browser security policies block web pages from calling USDA directly. In that case lookups fail with *"Could not reach USDA Soil Data Access from this browser."* Then:

1. Double-click `START_DASHBOARD.bat` (or run `python server.py` in Anaconda Prompt).
2. Use the dashboard at `http://127.0.0.1:8765`.

When the page is opened through the server, it automatically falls back to it whenever a direct request fails. Results are identical; affected rows note "retrieved via local server.py fallback" in `Supplemental_Warnings`.

## Depth interval

The **Depth interval** selector defaults to **0–15 cm**. You can also choose 0–5, 0–30 or 0–100 cm, the GlobalSoilMap intervals (5–15, 15–30, 30–60, 60–100, 100–200 cm), or a custom top–bottom interval. All horizons are retrieved up front, so changing the interval recalculates the summaries, the table, the texture triangle and the exports instantly, with no new USDA query. Exports record the interval in `Depth_Top_cm` / `Depth_Bottom_cm` and in the file name. Wherever this README says "0–15 cm," read it as "the selected interval." The horizon export always includes `Overlap_0_15_cm` and adds an overlap column for the selected interval when that interval is not 0–15 cm.

## Texture triangle

The **Soil texture triangle (USDA)** panel plots the dominant-component sand/silt/clay for the selected interval, normalized to 100%. Points can be colored by soil order or survey area (colorblind-safe Okabe–Ito palette), and point IDs and the caption are optional.

- **PNG · 1000 dpi**: raster at exactly 1000 dpi, with resolution metadata (pHYs) embedded so Word and journal systems read it as 1000 dpi. Widths: 3.5 in (3500 px), 5 in or 7 in (7000 px).
- **SVG · vector**: same figure, resolution-independent, editable in Illustrator/Inkscape.

The `USDA_Texture_Class` column in the summary and component exports uses the same USDA-NRCS class rules.

## Data model and interpretation

- Point summary: **one row per sampling point**, including unsuccessful/pending lookups. The representative **dominant** component is used for the 0–15 cm summary; it is not necessarily the exact series at the sampling location.
- Component export: one row per SSURGO component of the returned map unit(s), with component-specific 0–15 cm properties.
- Horizon export: one row per original SSURGO horizon, with a calculated 0–15 cm overlap field.
- Numeric SSURGO fields are representative estimates, not measurements at coordinates.
- `0–15 cm` thickness-weighted property is returned **only if that property is present over the entire target depth**. Gaps or null horizons yield empty values; `0` is not treated as null.
- Soil organic carbon (%) is **estimated** from organic matter / 1.724, not observed SOC.
- SOC stock (Mg C/ha) is the sum across horizons of `SOC_pct * BD_g_cm3 * overlap_cm * (1 - coarse_fragments_vol_pct/100)`. The dashboard intentionally leaves this **blank** when coarse fragment information is absent (as it is in the standard query), so it will typically be blank. This avoids claiming an unsupported stock estimate. The status column explains why.
- Soil pH is thickness-weighted for convenience only; due to its logarithmic scale, this is not a chemically rigorous combined pH value.
- Optional hydrological / chemical columns may be unavailable for some map units, in which case the fields are blank and supplementary query warnings are shown.
- Missing values remain blank in CSV; **do not interpret blank as zero**.
- The dashboard provides a link to the Official Soil Series Description, not a copy of the entire narrative taxonomy/pedon text.

## Data provenance

Every exported row includes source and retrieval information. The downloadable `field_dictionary.csv` bundled with the application describes representative, calculated and derived columns. All SSURGO source values should be validated against survey metadata before publication.

## Troubleshooting

Opening `index.html` directly (`file://`) is supported. If every lookup fails with a network/CORS message while other websites work, your network is probably blocking direct calls; use the optional server fallback above. If port 8765 is in use, stop earlier server instances with Ctrl+C. Query results are cached in the browser for 6 hours and cleared when the page is reloaded. Requests can fail when the USDA Soil Data Access service is offline or slow. Do not run large CSVs until several points have succeeded.
