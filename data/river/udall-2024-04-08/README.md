# Udall additional evaluation week

April 8–14, 2024 UTC, immediately after the original April 1–7 demo. This period
was selected as the next nonoverlapping calendar week before running local
checks or reading this week's retrospective QC. It was not used for training
or for changing the river diagnostic policy.

Source: CSU ROSS / Poudre Water Quality Network, **CSU ROSS High-Frequency Water
Quality Sensor Dataset**, CC BY 4.0.
https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/
Full attribution and transformations: project `THIRD_PARTY.md`.

- 5,376 original records across eight parameters.
- 672 turbidity time slots: 510 numeric values and 162 null values.
- Null turbidity spans April 10 at 00:15 through April 11 at 16:30 UTC inclusive.
  Missing entries were not replaced with zero or interpolated. The cause of
  the data gap is not established by this preparation.
- Two recorded technician visits. Notes become visible at the following UTC
  midnight under the same explicit replay assumption as the original demo.

`observations.json` contains original values, units and public provenance with
archive basenames and SHA-256 hashes. `context.json` contains site/sensor metadata
and visit records. Original CSV records were selected and converted to JSON;
measurement values were not corrected or synthesized.

Preparation also writes evaluator-only QC and a preparation summary locally.
Those files are not distributed and are not investigator inputs. The source
archives remain unchanged.

From the project folder, reproduce the free checks with:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_river_holdout.py
```

The evaluator uses the committed selection plan and only this subset's original
observations/context. New results go to a new timestamped folder under `reports/`;
existing results are not overwritten. It blocks unexpected text-file reads and
HTTP requests during each investigation. It does not evaluate fresh Nemotron
inference or train a model. The dashboard's original demo remains unchanged.
