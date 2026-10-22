# Third-party material

The project code is offered under the root MIT license. The following material
retains its own license and attribution.

## Historical river measurements and context

CSU ROSS / Poudre Water Quality Network, **CSU ROSS High-Frequency Water Quality
Sensor Dataset**, Colorado State University ROSSyndicate, published September 25,
2026. Pinned resource: https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/
DOI: https://doi.org/10.4211/hs.63ede02dd7da44a5a3040fd9ad14ab15

License: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The resource's CC BY 4.0 statement was checked October 22, 2026. This project
retains that pinned version even though HydroShare lists a newer version.

The distributed subset is Udall, April 1–7, 2024 UTC: 672 turbidity readings,
5,376 observations across eight parameters, sensor/site metadata and one visit
record. Original CSV records were selected and converted to JSON; measurements
were not synthesized or replaced with cleaned values. Field names were adapted.
Visit-note availability at the following UTC midnight is our explicit replay
assumption, since actual note-entry times were not supplied. Retrospective QC
and corrected answers are excluded from the judge build and from runtime checks.

The resource describes river water. It does not establish treatment-plant
accuracy or water safety. Its creators do not endorse this application.

## Interface font

IBM Plex Sans regular and semibold, IBM Corp., under the SIL Open Font License
1.1. The full font notice and license travel with the files in
`water_diagnostics/web/OFL-Plex.txt`.

## Dependencies and hosted services

Python dependencies are installed from `requirements.txt` and retain their
respective licenses. NVIDIA Nemotron is accessed through Nebius Token Factory;
model weights and service credentials are not distributed. Tavily is optional
and accessed only by an explicit guidance request. Generated saved reports are
demonstration artifacts, clearly distinguished from fresh inference.
