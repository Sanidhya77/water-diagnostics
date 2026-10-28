# Water Diagnostics interface

This documents the existing local operator UI and its current refinement. The
surface is in Operate mode: a person investigates a replay and decides which
physical verification to request. The system and its evidence are the selling
point. Design should make that work legible and memorable.

The October 28 refinement adds a labelled Recorded week selector for two
prepared Udall weeks. Its presets change between Before/After visit and
Before/After gap, with matching date limits and chart windows. Public-demo mode
shows its scope beside the replay controls and disables paid buttons with an
explanation; enforcement also lives in the backend. The console identity and
existing workflow remain. Gap-related reports lead with the logging/power review.

## Visual direction

Keep the forest-green identity. Give the recorded signal a focused instrument
panel, using the same deep green as the workspace navigation. Keep reports,
controls and uncertainty on light surfaces. The trace shows actual executed
checks; the chart is the single strong visual focal point.

Use IBM Plex Sans, locally hosted, for the complete UI. Use Consolas only for raw
evidence and execution logs. Fixed rem sizes: 12 px metadata, 13–14 px content
and controls, 16 px panel headings, 20 px selected chart measurement, 32 px page
heading. Tabular numerals for measurements, dates, counts and costs. No external
font request, licensing service or animation dependency is needed. Font license:
`water_diagnostics/web/OFL-Plex.txt`.

Core tokens: canvas `#f5f6f3`, surface `#ffffff`, ink `#173b33`, text `#263b34`,
muted `#5f6f66`, action `#174e43`. On deep green, use `#d7e6d9` and `#b5cbbb`
for primary and secondary chart text, `#c3d4c7` for the original signal, and
`#e0bd81` for a recorded visit or demonstration threshold. Amber is evidence
context, not proof of a fault or a real river regulatory threshold.

Use a horizontal application header; there is no permanent side navigation.
Lead with the actual case site and source, followed by the replay controls.
An investigation brief puts the saved or newly returned conclusion and next
requested operator action beside the explicit run controls. Empty and running
states must not display a fabricated conclusion.

The October 22 refinement uses the user's selected instrument-console direction:
minimal composition, tactile controls and restrained depth. Source and replay
selection form a compact control area. On wide screens, the recorded signal
occupies the flexible left region and a 320 px investigation decision area holds
the conclusion, provenance, next requested action and run controls. The signal
and decision are visibly connected, rather than stacked as unrelated sections.

Keep sample inspection, chart window, playback and clock in the instrument;
the four evidence-availability facts belong in its footer. Shallow inset wells
mark editable inputs and segmented controls. Buttons use a 1 px raised edge
with a small offset soft shadow; the chart has a restrained bezel. Do not add
decorative screws, glass layers, fake gauges or equally weighted bento cards.
Flat report text and quiet reference guidance follow the connected evidence rail.

Below 900 px, the signal and decision stack in DOM order. Below 700 px, a visible
Investigation & run controls link skips directly to the decision area. Retain
section navigation; the check rail becomes a vertical list with the same shared
JSON inspector. Preserve all controls and provenance. Motion remains the
recorded-signal playback described below, not an ornamental page animation.

## Motion thesis

- **Focal moment:** a user starts signal playback. A bounded SVG mask reveals the
  recorded line in timestamp order, with a moving time cursor and a sample
  readout. Displayed numeric values always come from original samples. Preserve
  gaps; never animate a fabricated measurement.
- **Continuity:** chart windows and replay selection cancel playback and render
  the selected historical window immediately. Playback changes only the chart,
  never the investigation clock, evidence, report or network state.
- **Feedback:** pause/resume, sample scrubbing, actual check completion, a report
  update get short state transitions. No staged page-load
  choreography, artificial tool delays or ornamental looping dashboards.
- **Budget:** use browser-native SVG, CSS and requestAnimationFrame. The sequence
  lasts 2.4–8 seconds and runs only after a user action. Pause when the chart is
  offscreen, the tab is hidden, the replay changes or an investigation starts.
  Update text only when the selected recorded sample changes.
- **Reduced motion:** replace animated playback with a Next sample action;
  retain range-slider inspection and all evidence. Respect the OS preference
  without hiding data or controls.

## Truth and interaction rules

Do not label historical data as live. No invented users, telemetry, confidence
scores, equipment diagrams or KPI cards. A selected chart sample is distinct
from the latest observation at the investigation clock. Source labels, UTC
times, original values, visible-note assumptions and missing evidence remain
clear. A complete investigation can correctly conclude insufficient evidence.

No automatic inference or search requests. Keep the existing explicit buttons,
spending guards and server-side credentials. Motion must not introduce paid
calls, simulated tool execution or claims that a physical action was performed.
The operator header omits the personal development-budget meter. Spending limits
remain enforced on the server; development accounting is available through the CLI.

The recovery panel appears only under Simulated cases. Its two explicitly named
collector scenarios are separate from the selected diagnostic replay and its
chart. Show the local-policy provenance, simulation label, actual policy verdict,
attempt count, verification evidence and whether escalation was recorded. A
successful acknowledgement alone must not produce a recovered state. Keep the
execution record readable, the download explicit and raw before/after packets in
a disclosure. Do not introduce pretend delays, paid calls or physical-action
claims. At small widths, stack the scenario selector, run control and download.

## References reviewed

- [Impeccable](https://github.com/pbakaus/impeccable): active workflow, Operate
  principles, motion planning, contrast and bounded visual verification.
- [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design):
  subject-specific composition, one strong focal interaction, deliberate type
  and responsive feedback. Reviewed as a reference; not additionally installed.
- [Awesome DESIGN.md](https://github.com/voltagent/awesome-design-md): used the
  idea of durable documented color, type, component and interaction rules. Our
  document describes this product rather than copying another company's brand.
- [Better Design](https://github.com/marvkr/better-design): reviewed its design
  system and transition approach. Its React/shadcn component registry is not
  needed for this existing Python-served HTML/CSS/JS app.
- [Ilm-Alan frontend-design](https://github.com/Ilm-Alan/frontend-design): reviewed
  its anchor system and content discipline. Kept the established visual identity
  and the rule against fabricated telemetry; did not adopt a different preset.
- [Designer Skills](https://github.com/owl-listener/designer-skills): reviewed
  the collection's UX, systems, interaction and critique scope. Selected
  interaction feedback and accessibility as relevant concerns, without
  installing the full overlapping collection.

Research references guide design choices. They are not product dependencies or
evidence supporting a water-quality interpretation.

## Verification notes

The October 22 mechanical scan found low-contrast inactive source labels; these
were darkened to the body-text token. The source switch is an inset segmented
control inside the replay toolbar, not a nested content card. A run-controls
separator uses 16 px top padding where the separator exists. Observation values
have 12–16 px insets; segmented wrappers have 4 px around padded buttons. These
arrangements explain the scan's container warnings. Small labels stay at 12 px.

Screenshots use `reports/console-*.png`. Browser checks cover 1365, 1024, 768 and
390 px, recorded playback, reduced motion, recovery and downloads. Earlier
workbench screenshots preserve the preceding composition and predate removal
of the personal development meter.
