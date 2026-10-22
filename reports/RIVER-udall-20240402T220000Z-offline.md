# Historical river turbidity investigation

Source: **REAL_RIVER_SENSOR_DATA**  
Site: udall  
Replay time: 2024-04-02T22:00:00+00:00  
Mode: `offline_reference_policy`  
Model: `none`  
Investigation status: `complete`

Conclusion: **insufficient_evidence**

A complete investigation means the workflow finished; the physical cause remains unresolved.

Dataset: [HydroShare source](https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/), CC BY 4.0.

## Checks performed

- **R01 — check_freshness:** Received samples: 185; interval: 900 seconds; freshness: True.
- **R02 — check_variation:** Latest usable turbidity: 10.714 NTU; six-hour range: 7.84–11.684 NTU.
- **R03 — check_device_status:** Live heartbeat/fault records unavailable. Sensor method metadata describes a standard procedure.
- **R04 — check_maintenance_context:** Visible historical visits: 0.
- **R05 — check_related_measurements:** Other river parameters: 7; independent turbidity reference unavailable.

## Unresolved alternatives

- **sensor_artifact_possible:** A sensor artifact remains possible. The same-station signals do not independently verify turbidity, and no live fault record is supplied. Relevant checks: R02, R05.
- **river_change_possible:** A change in river conditions remains possible. The available measurements cannot establish or exclude that explanation. Relevant checks: R02, R05.

## Uncertainty

- The cause remains unresolved: no independent turbidity reference or live device fault log is supplied.
- A recorded cleaning and a change in readings do not establish causation.
- Sensor methods describe standard procedures, not proof of calibration at the replay time.
- No physical confirmation test was performed by the agent.
- Retrospective QC flags and corrected values were not read by the investigator.
- Historical replay assumption: visit notes become available at the next UTC midnight. The source provides visit times, not the actual times when notes were entered.
- An offline reference policy selected the checks and alternatives; Nemotron was not called.

## Requested operator actions

- **Requested, not performed:** Ask a qualified operator for a time-matched independent turbidity measurement using the site's approved procedure.
- **Requested, not performed:** Request device fault records and review the original technician notes and readings around the visit.

## Tool attempts

- check_freshness: performed (R01)
- check_variation: performed (R02)
- check_device_status: performed (R03)
- check_maintenance_context: performed (R04)
- check_related_measurements: performed (R05)

## Boundaries

- Historical river observations do not validate a treatment-plant diagnosis.
- No regulatory alarm threshold or simulated filter threshold is applied.
- This report does not determine whether water is safe.
- The agent cannot operate equipment, alter readings or clear alarms.

The companion JSON contains the complete executed check results.
