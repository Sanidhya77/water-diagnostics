# Try Water Diagnostics

Water Diagnostics investigates a suspicious turbidity signal, gathers five
read-only checks, compares explanations and requests the next operator check.
NVIDIA Nemotron runs through the Nebius Token Factory API. Python executes the
checks and enforces evidence citations, report constraints and spending limits.

**Open the [public replay demo](https://water-diagnostics-demo.onrender.com)**
for saved results, fresh free local checks and recovery simulations. No account
is required. The Free service may need about a minute to wake after inactivity.
Fresh paid inference is available in the local build described below.

## Start on Windows

Requires Python 3.11 or newer. Extract the test build, then open PowerShell in
the extracted project folder (GitHub ZIPs may append the branch or commit ID):

On Windows, use a short extraction location such as `water-demo` in your home
folder; deeply nested OneDrive paths can exceed Windows path-length limits.

```powershell
py run_demo.py
```

This creates the isolated environment, installs the tested dependencies and
starts the app. `py run_demo.py --check` verifies the saved demo without a model
request. If the default port is busy, use `py run_demo.py --port 8766`.

Open the local URL printed by the server. Activation is optional when using
these full Python paths. No Conda, model download, GPU or VM is required.
On macOS/Linux use `python3 run_demo.py` instead. For manual setup, create `.venv`,
install `requirements-tested.txt` and run `python -m water_diagnostics serve`
with that environment's Python interpreter. Python 3.12 is the release-test target.
Dependency installation needs an internet connection; the free walkthrough
itself does not. The build contains sample data, not the original research ZIPs.

## Free walkthrough, about two minutes

1. Open **River replay → After visit**. Inspect the original April 2024 signal
   and recorded cleaning visit. The saved Nemotron result remains unresolved:
   the association is visible, but independent confirmation is missing.
2. Use **Play signal** or select a recorded sample. Playback changes the chart
   only. Open an evidence check or report citation to inspect its actual result.
   Choose **Apr 8–14 · recorded data gap → After gap** for the missing-data case:
   162 missing original readings, available battery/logging notes, and a specific
   operator request to review collector records. **Before gap** excludes the
   later visit notes. This does not prove why every entry is missing.
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
independent benchmark or field accuracy. Current curated reports come from the
October 28 qualification: six fresh synthetic cases and three fresh river clocks
under the same request configuration. All nine passed evidence audits. A separate
browser run exercised fresh inference and report download. Earlier attempts are
preserved in the qualification history and legacy reports. See
`qualification/2026-10-28/README.md` for exact scope, timing and estimated costs.

Real river replay and simulated filter-outlet cases remain separate. Runtime
does not read retrospective QC answers. Raspberry Pi collection is future work;
physical repair, treatment control and nuclear qualification are not implemented.

See `THIRD_PARTY.md` for the distributed public-data attribution and font license.
For a Free Render demonstration with paid APIs blocked, see `HOSTING.md`.
For the documented need and a ten-minute operator review, see
`USEFULNESS_AND_PILOT.md`. A hosted demonstration is not field validation.
