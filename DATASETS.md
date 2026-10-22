# Dataset choice for the first real-data check

Research checked on October 14, 2026. No dataset purchase, model training or paid
retrieval service is needed. The uploaded ZIP now contains the 2024 raw and cleaned
readings, technician field notes and file metadata. The archive passed its checksum
check; results are saved in `reports/dataset-inspection.md` and `.json`.

## Recommended: CSU ROSS / Poudre Water Quality Network

[Pinned public dataset and documentation](https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/)

This is the best match found for checking sensor diagnostics: actual river
turbidity measurements, before/after quality-control values, correction flags,
and technician visit notes covering cleaning and calibration. Samples are usually
15 minutes apart. The published resource uses CC BY 4.0 and requires attribution.

**Limitation:** it measures river water, not treated water at a filter outlet.
Quality-control flags are evidence about data quality; they are not verified
labels for all six of our diagnostic causes. It cannot establish plant accuracy.

The complete resource is about 1.4 GB. Start with one site and one week from the
2024 or 2025 data, together with the matching field notes and flag descriptions.
Keep the raw turbidity values and timestamps; retain the cleaned values and QC
annotations separately for review.

## Small alternative: MULTISOURCE Norwegian pilot

[NIVA dataset on Zenodo](https://zenodo.org/records/15374917)

Two JSON files total about 9.6 MB. They contain inlet/outlet readings for a rain
garden treating road runoff, including turbidity and other water measurements.
The provider describes the readings as unreviewed raw data. This offers paired
signals, but lacks confirmed diagnostic labels and is also outside drinking-water
filter treatment. Verify the reuse licence before adding files to a public demo.

The direct Zenodo metadata request timed out during this session. No local data
file is being presented as downloaded or inspected.

## Why we are postponing SWaT

[Official SUTD/iTrust source](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/swat/)

SWaT is relevant to water-treatment systems, but its normal/attack labels concern
cybersecurity. They are not sensor-fault or maintenance diagnoses. Access goes
through a dataset request and separate usage terms. It adds work before it gives
us the specific evidence we currently need.

## Next work, in order

1. Verify one hosted **simulated** case using the working Nano connection.
2. Select the small CSU subset from the uploaded ZIP, without Nebius. The initial
   inspection identified Udall, April 1–7, 2024 (UTC): 672 turbidity readings and a
   recorded April 2 cleaning visit. This was selected for exploration, not as a
   representative accuracy sample.
3. Local preparation is now implemented: `prepare-river` separates original
   observations, technician context and evaluator-only corrected values/flags.
   The second uploaded ZIP supplies site metadata, sensor methods and 18 flag
   definitions. Its `frozen` definition concerns water freezing near the sensor.
4. `inspect-river` now provides five local check results with 15-minute sampling
   and a replay clock. Next, connect them to Nemotron and add a report labelled as
   real river data. The existing model report schema still accepts only `SIMULATED`.
   Do not relabel real records or apply the simulator's filter threshold unchanged.
5. Compare a few investigations with the held-out QC records. Keep evaluator
   annotations and future visits out of the investigator's input. Treat ambiguous
   causes as insufficient evidence rather than inventing ground truth.

Synthetic fault injection can later use real signal shapes, but those incidents
must be labelled as **synthetically modified real measurements**, not real faults.
There is no reason to fine-tune a model for this first backend.
