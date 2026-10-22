"""Small synthetic smoke suite. Expected labels never go to the investigator."""

from collections.abc import Callable

from water_diagnostics.incident_reports.schema import Cause, IncidentReport
from water_diagnostics.simulator import make_replay


# Evaluator-only truth. Investigators do not import this module.
EXPECTED = {
    "normal": Cause.NORMAL,
    "frozen": Cause.SENSOR,
    "communication_loss": Cause.COMMUNICATION,
    "maintenance": Cause.MAINTENANCE,
    "process_change": Cause.PROCESS,
    "insufficient": Cause.INSUFFICIENT,
}


def evaluate(investigator: Callable, seeds: tuple[int, ...] = (0, 17, 91)) -> dict:
    rows = []
    for case, expected in EXPECTED.items():
        for seed in seeds:
            # No name or expected label is passed to investigator.
            report: IncidentReport = investigator(make_replay(case, seed))
            rows.append({"incident_id": report.incident["incident_id"], "case": case,
                         "seed": seed, "expected": expected.value,
                         "actual": report.conclusion.value, "status": report.investigation_status,
                         "checks_performed": len(report.checks_performed),
                         "passed": report.conclusion == expected and report.investigation_status == "complete",
                         "mode": report.investigation_mode})
    passed = sum(row["passed"] for row in rows)
    ambiguous = [r for r in rows if r["expected"] == Cause.INSUFFICIENT.value]
    return {"source": "SIMULATED", "passed": passed, "total": len(rows),
            "insufficient_evidence_passed": sum(r["passed"] for r in ambiguous),
            "insufficient_evidence_total": len(ambiguous),
            "limitation": "Designed synthetic fixture smoke checks, not field accuracy, an independent benchmark, or proof of model capability.",
            "results": rows}
