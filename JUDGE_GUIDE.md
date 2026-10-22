# Try Water Diagnostics

Water Diagnostics investigates a suspicious turbidity signal, gathers five
read-only checks, compares explanations and requests the next operator check.
NVIDIA Nemotron runs through the Nebius Token Factory API. Python executes the
checks and enforces evidence citations, report constraints and spending limits.

## Start on Windows

Requires Python 3.11 or newer. Extract the test build, then open PowerShell in
the extracted `water-diagnostics` folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m water_diagnostics serve
```

Open the local URL printed by the server. Activation is optional when using
these full Python paths. No Conda, model download, GPU or VM is required.
On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` instead.
Dependency installation needs an internet connection; the free walkthrough
itself does not. The build contains sample data, not the original research ZIPs.

## Free walkthrough, about two minutes

1. Open **River replay → After visit**. Inspect the original April 2024 signal
   and recorded cleaning visit. The saved Nemotron result remains unresolved:
   the association is visible, but independent confirmation is missing.
2. Use **Play signal** or select a recorded sample. Playback changes the chart
   only. Open an evidence check or report citation to inspect its actual result.
3. Choose **Simulated cases → Held sensor reading**, then **Corroborating
   process change** and **Ambiguous evidence**. These load saved hosted results
   with their provenance. They demonstrate contrasting designed fixtures.
4. Press **Run local checks** to execute a fresh, free Python reference
   investigation. This is not a Nemotron API request.
5. In **Recovery simulation**, run **Collector recovers**, then **Collector
   stays offline**. Both permit one simulated reconnect. Only independently
   verified new packets count as recovered; the failure records an escalation.
   No equipment operates and no notification is sent. Download either report.

Opening the app or selecting a case does not call a paid API. Saved reports are
prior inference, with no new inference or latency measurement. The recovery
action is selected by a local policy, not a fresh model planner.

## Optional fresh hosted investigation

Copy `.env.example` to `.env`, set your own `NEBIUS_API_KEY`, restart the server,
then explicitly press **Run with Nemotron**. Never publish `.env`. The configured
model is `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, through Nebius Token Factory's
OpenAI-compatible API. The local per-investigation reservation cap is $0.02 and
the development cap is $5; reservations are conservative estimates, not billing.
Actual billing and balance are shown by Nebius. No automatic retries occur.

Tavily's **Look up guidance** is a separate optional runtime request requiring a
`TAVILY_API_KEY`. Current reference guidance does not become historical evidence
or change the diagnosis. Its cache and credit guard are separate from Nebius.

For submission, the entrant must provide judges free access to demonstrated
functionality through the end of judging. Bundled replay and local checks need
no account. Entrant-funded live API access has not been deployed in this build;
do not put a shared secret in the public repository or ask judges to fund it.

## Evidence and limits

```powershell
.\.venv\Scripts\python.exe -m water_diagnostics validate-demo --mode saved
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-judge
```

Saved validation audits three designed synthetic fixtures (seed 0), not an
independent benchmark or field accuracy. They exercise the guarded
model-plus-Python workflow. They include earlier report-protocol versions; the
three cases were not all rerun under a single identical protocol.

Real river replay and simulated filter-outlet cases remain separate. Runtime
does not read retrospective QC answers. Raspberry Pi collection is future work;
physical repair, treatment control and nuclear qualification are not implemented.

See `THIRD_PARTY.md` for the distributed public-data attribution and font license.
