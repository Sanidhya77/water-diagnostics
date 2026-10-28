# Usefulness and operator review

## The documented problem

An unusual sensor signal can reflect a real water change, instrument trouble,
maintenance or lost telemetry. Choosing the next check requires both readings
and operational context. EPA's [source-water monitoring guidance, section 7](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P100PHLV.TXT)
describes reviewing maintenance records, equipment diagnostics and data patterns
when investigating alerts. USGS [continuous-monitor guidance](https://pubs.usgs.gov/tm/2006/tm1D3/)
covers inspection, cleaning, calibration checks, troubleshooting and field logs.

Our interpretation: a useful assistant should assemble that evidence, expose
what is missing and request a specific next check. These sources establish the
problem and relevant practices. They do not endorse or validate this prototype.

## What the implemented backend does

| Operator question | Implemented behavior |
| --- | --- |
| Are the received observations current and complete? | Python checks timestamps, expected sampling intervals and missing original values. |
| Did the signal freeze or change? | Numerical checks compute variation from the selected replay. |
| What context was available then? | Replay clocks exclude future readings and unavailable visit notes. The note-availability assumption is explicit. |
| What supports the explanation? | Nemotron selects approved tools; Python validates executed evidence, alternatives and citations before reporting. |
| What should someone check next? | Missing/stale river telemetry prioritizes logging/power records. Independent measurements and device logs remain human requests. |
| Can a reconnect help? | A separate local simulation permits one collector reconnect, checks independent readback, and records verified recovery or escalation. |
| Can I inspect the result? | The HTTP backend provides asynchronous investigation jobs, evidence, saved/fresh provenance and downloadable Markdown reports. |

This is an implemented Python application, not a chart with a chat box attached.
The model does not calculate the observations or control physical equipment.
It is constrained by Python; the evaluation measures that combined workflow.

## A concrete real-data example

In Historical river data, choose **Apr 8–14 · recorded data gap**, then **After
gap** (April 12, 2024, 00:00 UTC). There are 162 missing original turbidity entries
in the preceding 48 hours, although the latest received sample is fresh.
Available technician notes describe a battery change, an instrument that would
not power up, an interruption in logging, and later redeployment.

The report prioritizes reviewing the gap against collector power/logging records
and the technician notes. It does not claim the notes prove the cause of every
missing value or that telemetry recovery establishes water safety. **Before gap**
sets the clock to April 10, 00:00 UTC and excludes the later notes.

The original observations and visit context come from the attributed
[CC BY 4.0 Poudre River dataset](https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/).
Retrospective QC answers and corrected values are excluded. See `THIRD_PARTY.md`.

## What has and has not been validated

We have tested local behavior, evidence consistency, cost controls, selected
fresh hosted investigations and the recorded-data workflow. We have no deployed
operator study, verified time savings, measured reduction in false alarms,
customer adoption or proof of usefulness at a treatment site. Publishing a demo
does not establish any of those outcomes.

## A ten-minute operator review

Ask a water-quality technician, researcher or plant operator to review the
recorded case. They do not need to connect equipment or share site data.

1. Give them the gap case and ask what they would investigate first, before
   showing the report. Record their reasoning and time, with permission.
2. Show the evidence and report. Ask whether the first requested check is
   appropriate, what evidence is missing, and which wording could mislead.
3. Ask them to explain whether the report proves a water change, a device fault
   or water safety. Check that the uncertainty is understood.
4. Show the separate reconnect simulation and ask what permissions, logs and
   verification would be required before any real collector integration.
5. Record their role, date, scenario, suggested changes and whether the report
   added useful information. Keep identifying details private unless approved.

Use a simple record: role/date; initial next check; report next check;
appropriateness (1–5); uncertainty understood (yes/no); missing evidence;
potentially misleading text; suggested change. Report the actual response count.
One review is qualitative feedback, not an efficacy study. Do not invent quotes,
testimonials or performance improvements.

No outreach message has been sent by this project workflow. The next evidence
milestone is a real person's review, followed by a read-only site pilot only if
a site agrees and defines the data interface and evaluation criteria.
