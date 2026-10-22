# Additional river-week local checks

Additional nonoverlapping week of local workflow checks; not diagnostic accuracy, an independent benchmark or a fresh hosted-model evaluation. The river policy permits only insufficient_evidence because independent turbidity and live fault logs are unavailable.

Site: udall. Period: 2024-04-08T00:00:00Z to 2024-04-15T00:00:00Z (end exclusive).

The next nonoverlapping calendar week after the existing April 1-7 demo. Dates and replay clocks fixed before running checks or reading retrospective QC for this week.

Turbidity time slots: 672; missing values: 162. Missing values stay null, not zero or interpolated.

| Replay clock UTC | Latest NTU | Six-hour range NTU | Fresh | Missing in 48h | Visible visits | Integrity |
| --- | ---: | --- | --- | ---: | ---: | --- |
| 2024-04-10T00:00:00Z | 5.185 | 3.865–7.612 | True | 0 | 0 | Pass |
| 2024-04-12T00:00:00Z | 1.703 | 0.778–31.053 | True | 162 | 2 | Pass |
| 2024-04-15T00:00:00Z | 1.316 | 1.316–46.287 | True | 0 | 0 | Pass |

Workflow integrity: 3/3 replay checks passed.
Every attempted clock is retained, including errors or incomplete investigations.

No model called, no training performed, no new Nebius or Tavily requests.
The investigator read only observations.json and context.json. Retrospective QC was excluded.
Observation/context input hashes unchanged: True.

Complete per-clock evidence, uncertainty and requested operator actions are in the companion JSON/Markdown reports.
Source: CSU ROSS / Poudre Water Quality Network, CC BY 4.0. See THIRD_PARTY.md.
