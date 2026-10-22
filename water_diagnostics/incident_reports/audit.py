"""Recompute saved diagnostic evidence without importing evaluator answers."""

from water_diagnostics.diagnostic_tools.checks import DiagnosticTools, TOOL_DESCRIPTIONS
from water_diagnostics.incident_reports.reporting import make_report, validate_draft
from water_diagnostics.incident_reports.schema import IncidentReport, ReportDraft


def audit_report(report, replay):
    """A valid schema alone cannot establish executed, correctly cited evidence."""
    issues = []
    if report.incident != replay.incident_context():
        issues.append("Incident does not match this fixture and replay clock.")
    if report.investigation_status != "complete":
        issues.append("Investigation is incomplete.")
    names = [e.tool for e in report.observations]
    ids = [e.evidence_id for e in report.observations]
    if len(names) != 5 or set(names) != set(TOOL_DESCRIPTIONS) or ids != [f"E{i:02d}" for i in range(1, 6)]:
        issues.append("Five unique executed checks and consistent evidence IDs are required.")
    if report.checks_performed != names:
        issues.append("Check list differs from the evidence ledger.")
    performed = [(a.tool, a.evidence_id) for a in report.tool_attempts if a.status == "performed"]
    if performed != list(zip(names, ids)):
        issues.append("Tool attempts differ from the evidence ledger.")
    tools = DiagnosticTools(replay)
    for item in report.observations:
        if item.tool not in TOOL_DESCRIPTIONS or item.data != tools.execute(item.tool, {})["data"]:
            issues.append("Saved evidence differs from recomputed fixture data.")
            break
    if not issues:
        try:
            draft = ReportDraft(conclusion=report.conclusion, possible_causes=[
                cause.model_dump(exclude={"interpretation"}) for cause in report.possible_causes])
            validate_draft(draft, report.observations)
            rebuilt = make_report(replay, report.observations, report.tool_attempts,
                                  report.investigation_mode, report.model, draft)
            if (report.possible_causes != rebuilt.possible_causes
                    or report.suggested_operator_actions != rebuilt.suggested_operator_actions
                    or report.uncertainty != rebuilt.uncertainty):
                issues.append("Application-owned interpretations, uncertainty or requested actions were changed.")
        except ValueError:
            issues.append("Conclusion, alternatives or citations fail the evidence constraints.")
    if report.boundaries != IncidentReport.model_fields["boundaries"].default:
        issues.append("Application-owned operating boundaries were changed.")
    return issues
