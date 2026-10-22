# Data and evaluation before submission

## Decision

Keep the current hosted NVIDIA Nemotron model. There is no training or
fine-tuning pipeline in this prototype. Do not start a GPU VM, fine-tuning job
or model download for this submission. More records alone do not supply the
verified diagnostic labels that supervised training would need.

## What the current evidence establishes

- Three saved hosted synthetic cases (seed 0) exercise sensor fault, corroborating
  process change and insufficient evidence. Python guards the model's conclusions
  and report. The saved runs span earlier reporting protocols.
- The free reference evaluation covers all six designed fixtures at seeds 0,
  17 and 91. This tests deterministic local behavior, not hosted model accuracy.
- The historical Udall replay uses one selected week and one recorded visit.
  It demonstrates a workflow, not representative performance in the field.

Do not turn these checks into a field-accuracy percentage or describe the model
as trained on the river dataset.

## Next useful data step

Select one additional site or nonoverlapping week from the already downloaded,
pinned CSU ROSS / Poudre Water Quality Network archives. No new dataset purchase
is needed. Keep the week separate from workflow development. Choose it for
coverage and availability of visit context before looking at model outcomes;
record every attempted case and incomplete result.

Source and license: https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/
CC BY 4.0; attribution and transformations belong in `THIRD_PARTY.md`.

1. Prepare original observations and timestamped context locally. Do not pass
   corrected values, retrospective QC flags, future readings or future notes to
   the investigator. Preserve the explicit note-availability assumption.
2. Run the five free checks and inspect missing/stale values, visit timing,
   correlated measurements and conflicting evidence. Include ambiguous cases.
3. Review what the source actually verifies. QC flags concern data quality;
   they are not independent labels for all six diagnostic causes. Same-station
   measurements do not independently verify turbidity.
4. Only after the local review, select a small, fixed set of hosted runs under
   the existing budget guard. Record costs, status, evidence validity, conclusion
   support and requested operator verification. No automatic retries.

Assess whether the report stays within its evidence. Add a new fixture or test
only when an observed failure exposes behavior the current checks miss. Training
can be reconsidered after collecting enough independently reviewed examples and
holding out a separate evaluation set. Raspberry Pi collection remains a later
read-only pilot, independent of this evaluation step.
