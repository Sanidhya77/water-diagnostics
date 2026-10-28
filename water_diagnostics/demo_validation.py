"""Three synthetic workflow checks with saved-report reuse and bounded inference."""

import json
import re
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from water_diagnostics.config import DEFAULT_MODEL, PROJECT_ROOT, load_settings
from water_diagnostics.diagnostic_tools.checks import TOOL_DESCRIPTIONS
from water_diagnostics.evaluation import EXPECTED
from water_diagnostics.incident_reports.reporting import save_report
from water_diagnostics.incident_reports.audit import audit_report
from water_diagnostics.incident_reports.schema import IncidentReport
from water_diagnostics.investigator import investigate_nebius, investigate_offline
from water_diagnostics.model_client.budget import BudgetError, CostGuard
from water_diagnostics.model_client.nebius import NebiusClient
from water_diagnostics.simulator import make_replay


CASES = ("frozen", "process_change", "insufficient")
SESSION_CAP_USD = 0.04
LIMITATION = (
    "Three designed synthetic fixtures at seed 0, not field accuracy or an independent benchmark. "
    "Scores describe the guarded model-plus-Python workflow: Python constrains conclusions, "
    "citations and report wording. Saved runs are not fresh inference and have no measured latency. "
    "Costs are local token estimates/reservations; Nebius billing is authoritative."
)


class ValidationGuard(CostGuard):
    """Attribute only this client's requests, even if another app shares the ledger."""

    def __init__(self, path, remaining):
        super().__init__(path, run_cap=min(0.02, remaining))
        self.request_ids = set()

    def reserve(self, model, payload):
        identifier = super().reserve(model, payload)
        self.request_ids.add(identifier)
        return identifier

    def usage(self):
        with self._locked():
            rows = [r for r in self._read()["requests"] if r["id"] in self.request_ids]
        return {"requests": len(rows),
                "requests_with_usage": sum(r["estimated_usd"] is not None for r in rows),
                "reported_cost_estimate_usd": round(sum(r["estimated_usd"] or 0 for r in rows), 8),
                "conservative_accounted_usd": round(sum(r["accounted_usd"] for r in rows), 8)}


def score(report, replay, expected):
    issues = audit_report(report, replay)
    return {"actual": report.conclusion.value, "status": report.investigation_status,
            "checks_performed": len(report.observations), "audit_passed": not issues,
            "expected_match": report.conclusion == expected,
            "passed": not issues and report.conclusion == expected, "issues": issues}


def find_saved(root, output, replay):
    stem = replay.incident_id + "-nebius"
    # Each explicit CLI recovery appends -retry. Inspect the latest attempt,
    # including failures, rather than choosing whichever saved report passed.
    pattern = re.compile(re.escape(stem) + r"(?:-retry)*\.json")
    paths = [path for folder in (output, root / "demo_reports", root / "reports")
             for path in sorted((p for p in folder.glob(stem + "*.json")
                                 if pattern.fullmatch(p.name)),
                                key=lambda p: len(p.name), reverse=True)]
    for path in paths:
        if not path.exists():
            continue
        try:
            report = IncidentReport.model_validate_json(path.read_text(encoding="utf-8"))
            if report.investigation_mode != "nebius_model" or report.model != DEFAULT_MODEL:
                raise ValueError()
        except (OSError, ValueError):
            return path, None, ["Saved hosted report is unreadable or uses another model; review it before spending again."]
        return path, report, audit_report(report, replay)
    return None, None, []


@contextmanager
def validation_lock(output):
    output.mkdir(parents=True, exist_ok=True)
    path = output / ".validation.lock"
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise BudgetError("Demo validation is already running or its interrupted-run lock needs review; no new request sent.") from None
    try:
        with handle:
            yield
    finally:
        path.unlink()


def validate_demo(root=PROJECT_ROOT, mode="saved", output=None, settings=None,
                  client_factory=None, progress=print):
    root = Path(root)
    output = Path(output) if output is not None else root / "reports" / "demo-validation"
    with validation_lock(output):
        return _validate_demo(root, mode, output, settings, client_factory, progress)


def _validate_demo(root, mode, output, settings, client_factory, progress):
    if mode not in ("saved", "nebius"):
        raise ValueError("Choose saved or nebius validation mode.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    history = output / "history"
    history.mkdir(exist_ok=True)
    rows, accounted, stopped = [], 0.0, False
    for case in CASES:
        replay = make_replay(case, 0)
        baseline = investigate_offline(replay)
        baseline_path, _ = save_report(baseline, output, replay.incident_id + "-offline")
        row = {"case": case, "seed": 0, "expected": EXPECTED[case].value,
               "baseline": {**score(baseline, replay, EXPECTED[case]), "report": str(baseline_path.resolve())},
               "hosted": {"origin": "not_run", "passed": None, "elapsed_seconds": None}}
        path, report, issues = find_saved(root, output, replay)
        if path is not None:
            row["hosted"] = {"origin": "saved", "report": str(path.resolve()), "elapsed_seconds": None,
                             **(score(report, replay, EXPECTED[case]) if report else {"passed": False})}
            if issues:
                row["hosted"].update(passed=False, issues=issues)
                stopped = True  # Preserve a failure; never silently retry or cherry-pick it.
            if progress:
                progress(f"{case}: saved hosted report inspected; no API request.")
        elif mode == "nebius" and not stopped:
            remaining = round(SESSION_CAP_USD - accounted, 8)
            if remaining <= 0:
                stopped = True
            else:
                guard = ValidationGuard(root / "reports" / "nebius-usage.json", remaining)
                client = (client_factory or (lambda s, g: NebiusClient(s, budget=g)))(settings or load_settings(), guard)
                if progress:
                    progress(f"{case}: new hosted investigation; case guard ${guard.run_cap:.2f}; session guard ${SESSION_CAP_USD:.2f}.")
                started = perf_counter()
                try:
                    # Evaluator-only case names, expected answers and baseline reports
                    # never enter the investigator or its model messages.
                    report = investigate_nebius(replay, client, progress=progress)
                finally:
                    elapsed = round(perf_counter() - started, 3)
                    client.close()
                path, _ = save_report(report, output, replay.incident_id + "-nebius")
                usage = guard.usage()
                accounted = round(accounted + usage["conservative_accounted_usd"], 8)
                row["hosted"] = {"origin": "new", "report": str(path.resolve()),
                                 "elapsed_seconds": elapsed, "usage": usage,
                                 **score(report, replay, EXPECTED[case])}
                if not row["hosted"]["passed"]:
                    stopped = True
        if stopped and row["hosted"]["origin"] == "not_run":
            row["hosted"]["reason"] = "New inference stopped after a saved/new failure or the session guard; no retry."
        rows.append(row)
        # Save after every completed case so an interruption preserves progress.
        summary = {"source": "SIMULATED", "model": DEFAULT_MODEL, "mode": mode, "run_id": run_id,
                   "created_at": datetime.now(timezone.utc).isoformat(),
                   "baseline_passed": sum(r["baseline"]["passed"] for r in rows),
                   "hosted_passed": sum(r["hosted"]["passed"] is True for r in rows),
                   "hosted_evaluated": sum(r["hosted"]["passed"] is not None for r in rows),
                   "total": len(CASES), "session_conservative_limit_usd": SESSION_CAP_USD,
                   "new_conservative_accounted_usd": accounted,
                   "new_reported_cost_estimate_usd": round(sum(r["hosted"].get("usage", {}).get("reported_cost_estimate_usd", 0) for r in rows), 8),
                   "new_requests": sum(r["hosted"].get("usage", {}).get("requests", 0) for r in rows),
                   "results": rows, "limitation": LIMITATION}
        for folder, stem in ((output, "comparison"), (history, run_id)):
            (folder / (stem + ".json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
            (folder / (stem + ".md")).write_text(render_comparison(summary), encoding="utf-8")
    return summary


def render_comparison(summary):
    lines = ["# Synthetic diagnostic workflow comparison", "", summary["limitation"], "",
             "| Case | Expected | Local policy | Nemotron | Run source | New elapsed time | Evidence audit |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in summary["results"]:
        h = row["hosted"]
        elapsed = f"{h['elapsed_seconds']:.3f}s" if h["elapsed_seconds"] is not None else "Not measured"
        audit = ("Pass" if h.get("audit_passed") else "Fail") if h["passed"] is not None else "Not run"
        lines.append(f"| {row['case']} | {row['expected']} | {row['baseline']['actual']} | {h.get('actual', 'Not run')} | {h['origin']} | {elapsed} | {audit} |")
    lines += ["", f"Local policy: {summary['baseline_passed']}/{summary['total']} matched.",
              f"Hosted workflow: {summary['hosted_passed']}/{summary['hosted_evaluated']} evaluated reports matched; {summary['total']} planned.",
              f"New API requests: {summary['new_requests']}. Local token-cost estimate: ${summary['new_reported_cost_estimate_usd']:.6f}.",
              f"New conservative reservations: ${summary['new_conservative_accounted_usd']:.6f} / ${summary['session_conservative_limit_usd']:.2f} session guard.",
              "Saved reports use no new inference. Their original costs and latency are not included in these new-run totals.", "",
              "## Report files and findings", ""]
    for row in summary["results"]:
        lines += [f"### {row['case']}", "", f"Baseline: `{row['baseline']['report']}`."]
        if row["hosted"].get("report"):
            lines.append(f"Hosted: `{row['hosted']['report']}`.")
        lines += ["- " + issue for issue in row["hosted"].get("issues", [])]
        if row["hosted"].get("reason"):
            lines.append(row["hosted"]["reason"])
        lines.append("")
    return "\n".join(lines)
