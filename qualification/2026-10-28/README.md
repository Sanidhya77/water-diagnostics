# October 28 release qualification

This qualification used fresh NVIDIA Nemotron inference through Nebius Token
Factory. It is separate from the earlier saved fixture comparison and the
additional-week offline evaluation.

## What was fixed

The original request path allowed the model's hidden reasoning to consume the
small output budget. One river attempt stopped after four checks with a token
limit; it remained incomplete and was preserved under `history/`. A synthetic
normal-case run also took 242.5 seconds. These attempts were not silently retried
or converted into successful reports.

NVIDIA documents a direct tool-calling mode with `enable_thinking=false`. The
Nebius endpoint accepted `chat_template_kwargs: {enable_thinking: false}` in an
explicit probe. That setting is now used for the configured Nano model. The
model still selects approved tools and a constrained conclusion; all original
evidence checks, report validation, output caps and spending guards remain.
Independent checks may be requested in one turn, but actual request counts are
recorded rather than assuming a batch occurred.

Sources:
- NVIDIA model documentation: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
- Nebius current model/rate catalog: https://tokenfactory.nebius.com/api/public/models_info

## Final fresh runs

All nine current-setting investigations completed five checks and passed their
evidence audits. The six synthetic conclusions matched their designed fixture
expectations. The three river reports stayed inconclusive as required by their
available evidence. Each run had six API requests; observed investigation times
were 6.7–12.1 seconds. Full results and usage are in `fresh-results.json`.

The curated copies under `demo_reports/` are the versions shown by a newly opened
workbench. They are labelled as saved; loading them makes no new inference call.

This is a selected development check of the guarded model-plus-Python workflow,
not independent model accuracy or proof of field reliability. Timing is an
observation from this session, not a latency guarantee. Prompt history and both
the incomplete and successful attempts remain documented.

## Product and portability checks

- 159 current local tests passed, including budget enforcement, evidence
  constraints, batched tool responses, report lookup and source isolation.
- A fresh Windows environment installed the tested dependencies from scratch and
  passed `run_demo.py --check` without credentials or the original environment.
- Offline CI installed and tested the preceding setup snapshot on Windows,
  Ubuntu and macOS. The workflow also runs on each current source push:
  https://github.com/Sanidhya77/water-diagnostics/actions/workflows/verify.yml
- A separate browser test clicked Run with Nemotron, completed a fresh river
  investigation, opened/downloaded the report and checked four viewport widths,
  playback, reduced motion and both simulated recovery outcomes. It completed
  the fresh investigation in 9.3 seconds, with no browser errors or mobile overflow.
- No credentials, usage ledger or retrospective QC answers are distributed.

The final check files distinguish current-code local tests from each exact CI
commit. These are Python 3.12 source-build checks; no unsupported claim that the
application runs on every device is made. Live mode needs internet access and
a valid provider key. No public live inference service has been deployed.

## Costs

The user authorized up to $10 for qualification. The initial local session guard
was $0.25, and the existing stricter $5 project/$0.02-per-investigation guards
remained active. All attempts, the parameter probe and the browser API test used
102 requests: **$0.01547628** in reported-token estimates and **$0.211689** in
conservative reservations. All 102 requests returned usage counters.

These are local estimates/reservations, not an invoice or account balance.
Nebius billing is authoritative. No training or paid GPU VM was used. The old
project ledger retains its earlier unknown-usage reservations; it was not reset.
