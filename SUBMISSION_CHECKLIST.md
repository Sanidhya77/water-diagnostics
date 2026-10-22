# Submission preparation

Checked October 22, 2026 against the [official hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules).

The deadline is October 30, 2026 at 10 a.m. PDT (10:30 p.m. India time). The
current project fits the Best Apps and Agents track; that
is our project-fit judgment, not an eligibility guarantee.

## Working now

- Hosted NVIDIA Nemotron through Nebius Token Factory, with five approved checks.
- Separate simulated incidents and historical river replay.
- Three saved synthetic workflow cases pass; the current suite has 152 passing
  local tests, including recovery gates and verification. The samples are
  development checks, not field accuracy.
- Saved reports, evidence citations and operator requests in the local dashboard.
- Functional Tavily lookup with caching and a separate development-credit guard.
- Two free recovery simulations: one verified collector reconnect, or one failed
  verification followed by recorded escalation. The local policy selects the
  action; no fresh model call, hardware action or actual notification occurs.
- Personal budget meter removed from the operator UI; server spending controls
  and `python -m water_diagnostics budget-status` remain available. The 16
  dashboard/budget tests pass after this UI change.

## Runnable judge package

- [x] Prepare an allowlisted build script: `python scripts/build_demo.py`.
  `JUDGE_GUIDE.md` gives setup and the free walkthrough.
- [x] Include the attributed river observations/context and five saved reports
  used by the walkthrough. `.gitignore` now allows only these curated sample
  files; generated reports, usage ledgers and retrospective QC remain ignored.
- [x] Keep historical/simulated labels, prior-inference provenance and limits.
  `THIRD_PARTY.md` records the pinned source and its CC BY 4.0 license.
- [x] Verify extracted source with no credentials, original ZIPs, retrospective
  QC or local virtual environment. Reused installed dependency packages; this
  was not a fresh dependency installation. Verified both river presets, three
  saved reports, three fresh local checks, 3/3 saved evidence audits and both
  recovery outcomes with outbound requests blocked. Archive hashes matched.
- [x] Run the 152-test suite and desktop/tablet/phone browser checks after the
  console refinement. No new paid model or Tavily requests were made.
- [x] Explain cached replay, free local checks and live hosted inference
  separately in `JUDGE_GUIDE.md`. Saved and local functionality needs no key.
- [ ] Confirm the judge-access arrangement for fresh hosted inference if it is
  part of the submitted demo. Entrant-funded hosted access is not deployed;
  never publish a shared API key or expect judges to fund API calls.

## Repository and submission materials

- [x] Add an MIT source license; data and fonts retain their separate licenses.
- [x] Prepare a public GitHub/GitLab/Bitbucket repository with README, source,
  assets, setup instructions and a clear Nebius/NVIDIA architecture explanation.
  Published: https://github.com/Sanidhya77/water-diagnostics
- [x] Exclude credentials, local usage ledgers, browser profiles, virtual
  environments and private files from the release.
- [ ] Record a public YouTube video under three minutes, showing the actual
  application. Identify saved results clearly and show the read-only checks,
  competing explanations and requested operator verification.
  `DEMO_SCRIPT.md` supplies a 2:45 walkthrough outline.
- [ ] Complete the Devpost description, track selection, demo/test-build URL,
  repository/video URLs and required feedback on the tools used.
- [ ] Keep judge access available through the judging period ending December 15,
  2026. The official rules accept a working demo, hosted application or test
  build; a public cloud VM is not required for the Apps and Agents track.

Optional: pursue the Tavily bonus if the lookup is a useful part of the recorded
workflow. Its prerequisite is a functional runtime Tavily call; a static list of
links alone does not establish that integration.

The repository is public. Video and Devpost publication are still outstanding.
Public source test build:
https://github.com/Sanidhya77/water-diagnostics/archive/refs/heads/main.zip
