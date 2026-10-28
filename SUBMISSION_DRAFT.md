# Water Diagnostics — submission draft

Prepared October 22, 2026. This is reviewable copy, not a submitted Devpost entry.
The video URL and the arrangement for free judge access to fresh hosted inference
are still pending. Review the text against the final recorded demonstration.

## Project name

Water Diagnostics

## Tagline

Evidence-linked turbidity investigations with NVIDIA Nemotron on Nebius, built
for an operator's next check.

## Recommended track

Best Apps and Agents. This is the closest fit to the current software prototype;
no physical hardware deployment is claimed.

## Links for the form

- Public repository: https://github.com/Sanidhya77/water-diagnostics
- Verified source test build: https://github.com/Sanidhya77/water-diagnostics/archive/576c97fa0457c6c1d564935ca1f13bd3ff6928f0.zip
- Testing instructions: https://github.com/Sanidhya77/water-diagnostics/blob/main/JUDGE_GUIDE.md
- Additional-week evidence: https://github.com/Sanidhya77/water-diagnostics/blob/main/evaluations/river-holdout-2024-04-08/README.md
- Public YouTube video: PENDING — record and upload the actual application.

The test build runs locally; it is not a publicly hosted web application.
Dependency installation needs internet access. The bundled saved/local walkthrough
requires no API key or paid service. The build was checked from extracted source
with credentials and original research ZIPs absent, reusing installed dependencies.

## Inspiration

A suspicious turbidity reading can lead to several different next checks. It may
reflect a sensor problem, missing telemetry, maintenance timing or a change in
the water. A chart alone cannot establish which explanation is supported.

Water Diagnostics explores an evidence-first investigation: show the observations
available at a replay clock, execute the relevant checks, retain competing
explanations and request the measurement that would resolve uncertainty.

## What it does

An operator selects a historical river replay or a labelled synthetic incident.
NVIDIA Nemotron, accessed through Nebius Token Factory, can select from five
approved read-only diagnostic tools. Python computes their results and validates
the structured report. The interface connects each explanation to evidence that
the operator can open, inspect and download.

The five checks cover freshness, variation, device status, maintenance context
and related measurements. The report distinguishes a completed investigation
from an established physical cause. Missing evidence can correctly produce an
inconclusive result.

A separate recovery simulation demonstrates one policy-approved collector
reconnect followed by independent readback. New valid packets are required for
verified telemetry recovery; otherwise an escalation is recorded. This action
selection uses a local policy. It does not involve fresh model planning, real
hardware control or a sent notification.

Optional Tavily lookup retrieves current monitoring references from USGS, EPA and
the sensor manufacturer. Reference guidance remains separate from historical
incident evidence and cannot change the diagnosis or operate equipment.

## How we built it

The application is a Python service with a local HTML/CSS/JavaScript workbench.
The hosted model is `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, accessed through the
Nebius Token Factory inference API. Model weights are not downloaded, trained or
fine-tuned by this project.

The model selects tools; Python executes numerical checks and constrains the
accepted report. The synthetic reporting path accepts a constrained conclusion
and builds alternatives, citations and operator-request wording from executed
evidence. The river path has its own cautious schema and source-specific rules.
Bounded loops, explicit request buttons, local spending reservations and no
automatic retries keep development predictable. Keys remain server-side.

Historical measurements come from the CSU ROSS / Poudre Water Quality Network
dataset. Original observations and visit context are kept separate from
retrospective QC and corrected values. The replay explicitly assumes notes become
available at the following UTC midnight because actual note-entry times are not
supplied. River data never receives the simulated filter-outlet alarm threshold.

## Challenges

Reliable reporting required more than a fluent model response. Truncated,
malformed or unsupported submissions must not become a confident operator report.
We preserved incomplete attempts, constrained accepted outputs and rebuilt
synthetic report wording from the available evidence.

Historical replay also requires careful timing. Future measurements and notes
must remain hidden, while corrected values and QC labels must not leak into the
investigator's inputs. Recovery acknowledgement must remain distinct from
independently verified packet delivery.

## What we can demonstrate

- 155 passing local tests, including causal visibility, budget controls, report
  validation and blocked unexpected reads/network calls in the extra-week check.
- Three saved hosted synthetic fixtures with matching expected workflow outcomes:
  sensor fault, corroborating process change and insufficient evidence. These are
  designed examples of the guarded model-plus-Python workflow, not independent
  model accuracy. The saved runs span earlier reporting protocols.
- Two real-data weeks. The additional April 8–14 subset contains 672 turbidity
  time slots, including 162 missing entries. Three fixed local replays passed
  workflow-integrity checks while preserving missing values and uncertainty.
  That evaluation made no fresh hosted-model calls.
- Two recovery simulations: verified new packets or recorded escalation.
- A reproducible public source build with attributed data and evidence-linked
  downloadable reports.

No field-accuracy, operator time-saving or deployment-impact percentage has been
measured. The prototype is not connected to a treatment plant and makes no
water-safety determination. It does not clear alarms, perform physical repairs or
establish nuclear-system qualification.

## What we learned

Useful investigations need clear boundaries between a reading, an explanation
and a requested operator action. Fresh recent telemetry does not imply a complete
history: the additional week has a replay with a fresh latest value and 162
missing entries still present in its 48-hour history. Explicit uncertainty and
inspectable evidence are central product behavior.

## What's next

Review a small fixed set of fresh hosted investigations on additional data only
after the free local review. Establish independent measurements and operator
review before making stronger diagnostic claims. A future Raspberry Pi gateway
could collect read-only telemetry and forward it to the hosted workflow. Physical
recovery and process control would require a separate hardware integration and
validation effort.

## Tool feedback draft

Nebius Token Factory supplied hosted access to the NVIDIA model without managing
a GPU VM. Structured tool calls let the application keep numerical work in Python
and make each check inspectable. In development, final-report truncation and
schema failures motivated bounded output handling and retained incomplete runs.
Clear finish-state diagnostics and compact multi-tool examples would help this
workflow. Local token estimates and reservations are kept separate from
authoritative Nebius billing.

The project used NVIDIA Nemotron for inference. It did not evaluate NVIDIA
training tooling, AI Cloud compute or Raspberry Pi inference. The three designed
hosted fixtures do not support general claims about model reliability or speed.

Tavily has a functional explicit runtime lookup with a separate credit guard and
cache. If pursuing its bonus, show the lookup's actual contribution to the
operator workflow and label whether shown results are current, cached or saved.

Review this feedback against your own experience before submitting it as yours.

## Recording and completion checklist

- [ ] Start the app with `.\.venv\Scripts\python.exe -m water_diagnostics serve`.
- [ ] Rehearse the 2:45 sequence in `DEMO_SCRIPT.md` using saved reports and free
  local/recovery controls. Leave saved-result and simulation labels visible.
- [ ] Record the actual application, with its evidence, uncertainty and report
  download. Explain the additional-week result as local validation.
- [ ] Upload a publicly visible YouTube video under three minutes and replace
  the pending video field above with its URL.
- [ ] Confirm free access to all demonstrated functionality through the end of
  judging. The free bundled walkthrough works now; entrant-funded fresh hosted
  access is not deployed and must be addressed before representing it as available.
- [ ] Check the final form's track, links, authorship and required tool feedback.
- [ ] Review the entry and submit it on Devpost before the deadline.

Official requirements checked October 22:
https://nebiusglobalaihackathon.devpost.com/rules
Deadline: October 30, 2026, 10 a.m. PDT / 10:30 p.m. India time. Public code with
an open-source license, a demo/test-build link, a public video under three minutes
and tool feedback are required. Judge access must be free through December 15,
2026. Neither Devpost nor YouTube has been updated by this draft.
