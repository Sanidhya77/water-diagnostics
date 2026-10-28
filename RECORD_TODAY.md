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
suite before each recording; the release suite already passed 159 local tests.

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
Finish with the report download and additional-week evidence.

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

This is a local test build with a hosted-model option, not a deployed public web
service. Python 3.12 is the tested release target; fresh inference needs internet
and a valid server-side Nebius key. No Raspberry Pi or treatment equipment is used.
Public hosted access funded by the entrant is not configured; do not describe it
as available or publish a shared key. Confirm free judge access to the demonstrated
functionality using the final testing arrangement.

Official rules checked October 28:
https://nebiusglobalaihackathon.devpost.com/rules
Deadline: **October 30, 2026, 10:30 p.m. India time**. The rules require a public
code repository/license, a demo or test-build link, a public video under three
minutes and tool feedback; access for judges must remain free through judging.
