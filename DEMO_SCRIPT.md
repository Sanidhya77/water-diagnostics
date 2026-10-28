# Submission video: 2 minutes 45 seconds

Record the actual application. Show the saved-result provenance and simulation
labels. Avoid spending calls while rehearsing; the supplied walkthrough is free.

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:20 | River replay and the instrument console | “When a turbidity reading changes, an operator needs to know what to check next. Water Diagnostics gathers evidence, compares explanations and records a traceable investigation.” |
| 0:20–0:45 | Show the recorded visit, then click Run with Nemotron and let the fresh investigation complete | “This is historical Poudre River data. The drop follows a recorded cleaning visit, but timing alone does not prove the cause. I’m starting a fresh Nemotron investigation through the Nebius API.” |
| 0:45–1:15 | Open an evidence check, report alternatives and citation | “Nemotron selects from five read-only tools. Python performs the checks and constrains conclusions, citations and report wording. The result remains uncertain and requests an independent measurement.” |
| 1:15–1:40 | Switch through held sensor reading, process change and ambiguous evidence | “Three designed synthetic fixtures exercise different outcomes. These are saved hosted runs, not new inference or an accuracy benchmark. The local validation audits their evidence.” |
| 1:40–2:10 | Recovery succeeds, then stays offline | “A separate local policy permits one simulated collector reconnect. The success needs new verified packets. The failure records an escalation. No real hardware operates and no alert is sent.” |
| 2:10–2:30 | Download report; show the published additional-week comparison | “A second week includes 162 missing turbidity entries. Three fixed local replays preserve those gaps and uncertainty. These checks evaluate the workflow, not model accuracy.” |
| 2:30–2:45 | Finish on signal and decision | “The prototype combines a hosted NVIDIA model with deterministic checks and an auditable report. The next field step is a read-only collector pilot, with Raspberry Pi as a possible gateway.” |

Before recording, confirm every shown report matches its visible provenance.

Voice-over is not listed as mandatory. Recommended: speak the short lines above
in your own voice and add English captions. Clear English explanatory captions
can also carry the demonstration. No face camera is required to show the product.
The October 28 fresh browser run took 9.3 seconds, but provider timing can vary.
If cutting waiting time, label the cut. Keep the saved labels visible for the
later fixture switches; those are distinct from the fresh call shown earlier.

Start the existing local app with
`.\.venv\Scripts\python.exe -m water_diagnostics serve`, then open the address
printed by the server. Rehearse with saved results, Run local checks and the
recovery controls; none of those actions needs new inference. Have the actual
additional-week comparison open for the 2:10 segment:
https://github.com/Sanidhya77/water-diagnostics/blob/main/evaluations/river-holdout-2024-04-08/reviewed-checks/comparison.md

If showing fresh hosted inference, record an actual successful explicit run and
identify it as fresh; do not relabel a saved run. If Tavily is not demonstrated,
describe it as optional and do not imply that a runtime lookup happened on camera.

Submission positioning: **Best Apps and Agents** is the closest fit to the
current prototype. Raspberry Pi hardware and physical AI remain future work.
