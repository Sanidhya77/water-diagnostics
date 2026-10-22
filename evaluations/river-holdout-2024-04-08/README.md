# Additional week: local evaluation record

The next calendar week at Udall, April 8–14, 2024 UTC, was selected before its
checks or retrospective QC were inspected. `selection.json` pins the period
and all three replay clocks. The original April 1–7 dashboard demo remains the
separate development example. No training or diagnostic-policy change used the
new week.

The existing uploaded archives were sufficient. The prepared subset has 5,376
original records across eight parameters. Of 672 turbidity time slots, 510
have numeric values and 162 are null. The null period runs from April 10 at
00:15 through April 11 at 16:30 UTC inclusive. The source also records two
technician visits whose comments describe battery/logging problems. Those are
historical observations available under the replay-note timing assumption;
they are not a live fault log or proof of every gap's cause.

**Results:** [reviewed-checks/comparison.md](reviewed-checks/comparison.md), with
full evidence in the companion per-clock reports. All three local workflow
integrity checks passed. At the April 12 clock, all 162 missing turbidity
entries remain visible in the 48-hour history, even though the latest sample
is fresh. No independent turbidity reference is supplied, so all three reports
remain inconclusive. No diagnostic-accuracy score is claimed.

The first [local-checks/comparison.md](local-checks/comparison.md) is retained.
The reviewed run repeats the same fixed clocks after adding explicit missing
value counts to the summary table. Both runs are local; no outcome was dropped
and there were no paid retries. Network calls and unexpected `Path.read_text`
access were blocked during each investigation. Only observations/context were
read, and their before/after SHA-256 hashes match.

Reproduce from the project folder, after installing dependencies:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_river_holdout.py
```

Results are written to a new timestamped `reports/river-holdout-*` directory.
No new download, API key, model call or training job is required. Retrospective
QC remains local and excluded from investigation inputs and distribution.

The full local suite passed 155 tests, including checks that forbidden QC reads
and attempted HTTP calls are recorded as failures without a fallback result.

This adds a real missing-data case to the workflow evidence. It is not an
independent benchmark, field accuracy measurement or fresh hosted-model test.
See the root `THIRD_PARTY.md` for source attribution and CC BY 4.0 terms.
