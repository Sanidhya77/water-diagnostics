# Udall historical river replay

Prepared from the two uploaded ZIPs: April 1-7, 2024, in UTC.

Distributed subset of CSU ROSS / Poudre Water Quality Network's **CSU ROSS
High-Frequency Water Quality Sensor Dataset**, under CC BY 4.0. Pinned source:
https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/
See the project `THIRD_PARTY.md` for attribution and transformation details.
Local archive-directory paths were removed from distributed provenance;
archive basenames and the public source remain. Measurement values are unchanged.

- 672 original turbidity readings, sampled every 15 minutes.
- 5376 measurements across eight parameters, with no missing values in this selected week.
- One historical technician visit, kept separate from retrospective review annotations.

## Files

`observations.json` contains original readings and units.
`context.json` contains site metadata, sensor methods and recorded visit notes.
The local preparation may also create `evaluation.json` with corrected values
and review annotations for later comparison. It is excluded from the judge
build. The local diagnostic checks never read this file.

## Verified local replay

At April 2, 22:00 UTC: the latest reading is 10.714 NTU and the April 2 visit note is hidden.
At April 3, 00:00 UTC: the latest reading is 0.918 NTU and the recorded visit note is visible.

For this demonstration, notes become available at the next UTC midnight after the visit. Actual note-entry times were not supplied, so this is an explicit replay assumption. The drop supports review of the cleaning association, not proof of cause or water safety.

The metadata's frozen flag describes water freezing near the sensor. It must not be used as a label for unchanged numeric readings. The repeated value annotation lacks a definition in this metadata release.

The local reader and five checks are connected to a separate Nemotron workflow and a report labelled `REAL_RIVER_SENSOR_DATA`. Preparation itself uses no model/API requests.

From the project folder, use `python -m water_diagnostics run-river --mode offline` for a local reference report, or `python -m water_diagnostics run-river --mode nebius` for one guarded hosted investigation. The hosted model selects checks and submits a constrained interpretation. Reports go to `reports/RIVER-udall-<UTC timestamp>-<mode>.json` and `.md`.

A successful workflow can have `status=complete` and `conclusion=insufficient_evidence`: no independent turbidity reference or live fault log is supplied. The report preserves unresolved alternatives and requests operator confirmation. It applies no filter-outlet alarm threshold and does not determine water safety.
