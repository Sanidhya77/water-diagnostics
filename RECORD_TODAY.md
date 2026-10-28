# Record and submit today

October 28, 2026. The code and tested source build are ready for recording.
The video itself and Devpost entry are still yours to review and publish.

## 1. Quick check

From the extracted project folder:

```powershell
py run_demo.py --check
```

On macOS/Linux use `python3 run_demo.py --check`. This installs the tested
dependencies if necessary and audits the three saved demonstration cases.
It makes no new inference request. You do not need to rerun the entire test
suite before each recording; the current suite passed 166 local tests.

## 2. Start the product

```powershell
py run_demo.py
```

Open the local URL printed by the server. If it is busy, use
`py run_demo.py --port 8766`. Your current project already has its local API key.
For another installation, copy `.env.example` to `.env`, add a Nebius key and
restart the server for live inference. Saved reports and local checks need no key.

## 3. Record 2:30–2:45

Follow `DEMO_SCRIPT.md`. Start with the real river replay, show one fresh
Run with Nemotron, open the evidence and report, switch to the contrasting
synthetic cases, then demonstrate collector recovery and recorded escalation.
Finish with **River replay → Apr 8–14 · recorded data gap → After gap**. Show
the gap, the request to review power/logging records and available technician
notes, then download the report. The latest sample being fresh does not erase
the earlier 162 missing entries. Use `USEFULNESS_AND_PILOT.md` for the operator
problem and the next real review step; do not claim a deployed field study.

The fresh browser run completed in 9.3 seconds during qualification, but timing
can vary. If editing out waiting time, label the cut; do not represent a saved
result as fresh inference. Rehearse with saved/local controls to avoid unnecessary
calls. Live results are clearly labelled separately from saved reports.

Voice-over is not listed as a requirement in the rules. Recommended: use your own
voice and add English captions. A screen recording with clear English explanatory
captions is another option. A face camera is not needed to demonstrate the app.
Use the read-aloud text in `DEMO_SCRIPT.md` as a guide, not a claim of field proof.

## 4. Publish the video and finish Devpost

- Upload a publicly visible YouTube video under three minutes.
- Use `SUBMISSION_DRAFT.md` for the project description and tool-feedback draft.
- Add the video URL, repository URL and source test-build URL to the entry.
- Select Best Apps and Agents if that matches your final entry.
- Verify the judge-access instructions and review the complete form before submitting.

Public repository: https://github.com/Sanidhya77/water-diagnostics
Source test build: https://github.com/Sanidhya77/water-diagnostics/archive/refs/heads/main.zip

Public replay demo: https://water-diagnostics-demo.onrender.com

The public service offers saved results, free local checks and recovery
simulations, with paid APIs blocked. It was checked live on October 28. For fresh
Nemotron inference, record the local app with your existing key. Python 3.12 is
the tested release target. No Raspberry Pi or treatment equipment is used.
Entrant-funded public fresh inference is not configured; do not publish a shared
key. See `HOSTING.md` for public-demo scope and Free-service sleep limits.
Confirm free judge access to the demonstrated
functionality using the final testing arrangement.

Official rules checked October 28:
https://nebiusglobalaihackathon.devpost.com/rules
Deadline: **October 30, 2026, 10:30 p.m. India time**. The rules require a public
code repository/license, a demo or test-build link, a public video under three
minutes and tool feedback; access for judges must remain free through judging.
