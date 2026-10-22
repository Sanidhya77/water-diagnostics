# Design references and submission priorities

Reviewed October 15, 2026. These are preparation priorities, not a prediction of
prize eligibility or judging results.

## The product story

Water Diagnostics helps an operator investigate a suspicious turbidity signal:
inspect what was available at a replay clock, follow executed diagnostic checks,
compare explanations, and request the measurement that would resolve uncertainty.
The saved Nemotron investigation shows NVIDIA inference through Nebius. The new
Tavily feature helps the operator find monitoring references for that next check.

The historical river case is the demonstration's strongest opening. Compare
before and after the technician visit, show why timing alone cannot establish a
cause, inspect the missing independent reference, then open the guidance sources.
Use the simulated held-reading case to demonstrate the separate device-fault
workflow. Label every source and mode clearly.

## Prize focus

**Recommended main track: Best Apps and Agents.** This is an interpretation of
the current project's strengths: a functioning investigation workflow, bounded
model tool use, evidence citations and a usable operator interface.

The official rules require runtime use of Nebius Token Factory or AI Cloud and
at least one NVIDIA open model. Design is one of four equally weighted judging
criteria. The **Best Use of Tavily bonus is $3,000** and requires a functional
runtime Tavily API call. Submission materials include an open-source repository,
license and README, a working demo or test build, and a public demonstration video
under three minutes. The listed deadline is October 30, 2026 at 10 a.m. PDT.
Check the [official rules](https://nebiusglobalaihackathon.devpost.com/rules)
again before submitting, including personal/team eligibility and prize limits.

The reference lookup now performs a real runtime Tavily request. One Basic
search was verified on October 15: three USGS references, one reported credit.
This satisfies a technical prerequisite for pursuing that bonus; usefulness,
quality and the rest of the submission still matter. No physical device or live
plant integration is claimed.

## Design choices and references

The existing forest-green identity is retained. The refinement prioritizes
readable labels, stable spacing, stronger contrast, coherent SVG icons and
clear separation between evidence, interpretation and requested actions. The
six-hour default makes the technician-visit change visible; 24- and 48-hour
views retain access to the broader original history. Mobile stacks the same
working controls and evidence rather than hiding the investigation.

- [Impeccable](https://github.com/pbakaus/impeccable): installed locally; used its
  Operate guidance and a bounded polish/visual review pass for the existing UI.
- [Linear's interface redesign](https://linear.app/now/how-we-redesigned-the-linear-ui):
  reference for clearer hierarchy, navigation and contrast. No assets copied.
- [Carbon dashboard guidance](https://www.carbondesignsystem.com/building-blocks/data-visualization/dashboards):
  reference for task-focused data display and consistent information hierarchy.

## Budget and remaining preparation

The total available project budget remains $25, with $5 reserved for development
and $20 for demonstration. This pass made no Nebius inference requests and used
one Tavily credit. The Nebius guard remains $0.02 per investigation / $5
cumulative; Tavily has a separate persistent three-credit development limit.
Basic Search costs one API credit; actual dollar billing depends on the user's
Tavily plan. See [Tavily credit costs](https://docs.tavily.com/documentation/api-credits)
and [the Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search).
The service caches references for 24 hours and sends no search on page load.

1. Rehearse a single coherent demonstration using saved reports and cached
   guidance. Use the free local policy for repeated testing.
2. Prepare a public repository with an appropriate license, dependency setup,
   dataset attribution and reproduction instructions. Exclude `.env`, local
   usage records, virtual environments and private files.
3. Provide a reproducible test build or working demo. The current interface is
   laptop-only; hosting is a separate decision requiring server-side credentials
   and spending controls.
4. Record a public video under three minutes: problem, river replay, five actual
   checks, evidence-linked report, requested verification, Tavily guidance and
   the Nebius/NVIDIA architecture. Show cached and live behavior honestly.
5. Complete the Devpost entry and verify the relevant track and bonus selections.
