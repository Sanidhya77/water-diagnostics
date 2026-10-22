"""Evidence rules for demo fixtures, report validation and readable rendering.

These deliberately conservative rules are demonstration assumptions, not
validated water-treatment diagnostics or plant/regulatory thresholds.
"""

import json
from datetime import datetime
from pathlib import Path

from water_diagnostics.diagnostic_tools.checks import TOOL_DESCRIPTIONS
from water_diagnostics.incident_reports.schema import (
    Cause, CauseDraft, Evidence, IncidentReport, OperatorAction, PossibleCause,
    ReportDraft, ToolAttempt,
)
from water_diagnostics.simulator import Replay


INTERPRETATIONS = {
    Cause.NORMAL: "Current fresh signals are below the demonstration threshold after a brief historical crossing.",
    Cause.SENSOR: "The local elevated signal may reflect an instrument problem; a long exact plateau and recorded fault strengthen this explanation.",
    Cause.COMMUNICATION: "Stale samples and an offline device record suggest loss of communication; the last value cannot describe current water conditions.",
    Cause.MAINTENANCE: "A recorded sensor activity overlaps the excursion, followed by a return below the demonstration threshold. Timing supports an association, not proof of causation.",
    Cause.PROCESS: "Sustained elevated local and independent outlet readings support a real process change. Its root cause is unconfirmed.",
    Cause.INSUFFICIENT: "The completed checks do not establish a sufficiently supported final explanation for this investigation.",
}


def interpretation_for(cause: Cause, evidence: list[Evidence]) -> str:
    """Describe the evidence actually present, including weaker alternatives."""
    by_tool = {e.tool: e.data for e in evidence}
    variation = by_tool.get("check_variation", {})
    device = by_tool.get("check_device_status", {})
    freshness = by_tool.get("check_freshness", {})
    related = by_tool.get("check_related_measurements", {})
    reference = next((s for s in related.get("signals", [])
                      if s["role"] == "independent_outlet_turbidity" and s["fresh"]), {})
    if cause == Cause.SENSOR:
        parts = ["A sensor problem remains a possible explanation for the local signal."]
        if variation.get("trailing_identical_count", 0) >= 8:
            parts.append(f"The last {variation['trailing_identical_count']} readings are exactly identical.")
        if device.get("fault_codes"):
            parts.append("The device record contains fault codes: " + ", ".join(device["fault_codes"]) + ".")
        if reference.get("latest_above_threshold") is True:
            parts.append("An elevated independent outlet reading conflicts with a sensor-only explanation.")
        elif reference.get("latest_above_threshold") is False:
            parts.append("The independent outlet instrument is below the demonstration threshold.")
        else:
            parts.append("No fresh independent outlet result is available to distinguish a sensor problem from a process change.")
        return " ".join(parts)
    if cause == Cause.PROCESS:
        parts = ["An elevated local reading keeps a process change among the possible causes."]
        if not freshness.get("fresh"):
            parts.append("The local data failed freshness or timestamp checks and cannot establish current conditions.")
        if reference.get("latest_above_threshold") is True:
            parts.append("A fresh independent outlet instrument also reports elevated turbidity.")
        elif reference.get("latest_above_threshold") is False:
            parts.append("The independent outlet instrument is below the demonstration threshold, conflicting with an outlet-wide change.")
        else:
            parts.append("No fresh independent outlet result is available to corroborate this explanation.")
        parts.append("The underlying process cause is unconfirmed.")
        return " ".join(parts)
    if cause == Cause.COMMUNICATION:
        parts = ["The local data failed freshness or timestamp checks."]
        if device.get("online") is False:
            parts.append("An offline device record supports a communication problem.")
        elif device.get("status_fresh") and device.get("online"):
            parts.append("A fresh online device record conflicts with a simple communication-loss explanation.")
        parts.append("These records cannot establish current water conditions.")
        return " ".join(parts)
    if cause == Cause.NORMAL:
        return "The fresh local reading is now below the demonstration threshold. This does not resolve the alarm or establish water safety."
    return INTERPRETATIONS[cause]


def observation_summary(item: Evidence) -> str:
    data = item.data
    if item.tool == "check_freshness":
        return (f"{data['sample_count']} samples; latest usable age: {data['latest_usable_age_seconds']} seconds. "
                f"Freshness check: {'passed' if data['fresh'] else 'failed'}.")
    if item.tool == "check_variation":
        return (f"Last usable reading: {data['latest_ntu']} NTU; demonstration threshold: {data['demonstration_threshold_ntu']} NTU. "
                f"{data['recent_above_threshold_count']} of {data['usable_recent_count']} recent readings exceed it.")
    if item.tool == "check_device_status":
        if not data["available"]:
            return "Device status is unavailable."
        return (f"Recorded device state: {'online' if data['online'] else 'offline'}; "
                f"status record {'fresh' if data['status_fresh'] else 'stale or invalid'}. "
                f"Fault codes: {', '.join(data['fault_codes']) or 'none recorded'}.")
    if item.tool == "check_maintenance_context":
        return (f"{len(data['events'])} maintenance events recorded in the 30-minute window."
                if data["log_available"] else "The maintenance log is unavailable.")
    return f"{len(data['signals'])} related instrument signals available; {sum(s['fresh'] for s in data['signals'])} are fresh."


def assess(evidence: list[Evidence]) -> tuple[list[Cause], dict[Cause, CauseDraft]]:
    """Assess only executed tool results. Never read fixture names or truth labels."""
    by_tool = {e.tool: e for e in evidence}

    def data(tool: str) -> dict:
        return by_tool[tool].data if tool in by_tool else {}

    def ids(*names: str) -> list[str]:
        return [by_tool[n].evidence_id for n in names if n in by_tool]

    freshness = data("check_freshness")
    variation = data("check_variation")
    device = data("check_device_status")
    maintenance = data("check_maintenance_context")
    related = data("check_related_measurements")
    reference = next((s for s in related.get("signals", [])
                      if s["role"] == "independent_outlet_turbidity"), {})
    ref_fresh = reference.get("fresh", False)
    ref_normal = ref_fresh and reference.get("latest_above_threshold") is False
    ref_high = (ref_fresh and reference.get("latest_above_threshold") is True
                and reference.get("recent_above_threshold_count", 0) >= 5
                and reference.get("usable_recent_count", 0) >= 8)
    high = variation.get("latest_above_threshold") is True
    sustained = high and variation.get("recent_above_threshold_count", 0) >= 5
    local_normal = (variation.get("latest_above_threshold") is False
                    and variation.get("usable_recent_count", 0) >= 8)
    fresh = freshness.get("fresh", False)
    device_good = (device.get("available", False) and device.get("status_fresh", False)
                   and device.get("online") is True and not device.get("fault_codes"))
    overlap = maintenance.get("elevated_samples_during_recorded_event") or 0
    log_available = maintenance.get("log_available", False)
    events = maintenance.get("events", [])
    complete = set(TOOL_DESCRIPTIONS) <= by_tool.keys()
    candidates: dict[Cause, CauseDraft] = {}

    def add(cause: Cause, support: list[str], conflict: list[str] | None = None) -> None:
        if support:
            candidates[cause] = CauseDraft(cause=cause, supporting_evidence_ids=support,
                                           conflicting_evidence_ids=conflict or [])

    # Alternative hypotheses may remain possible without enough evidence to
    # make them a conclusion. Conflicting evidence is preserved alongside them.
    if high or device.get("fault_codes"):
        sensor_support = ids("check_variation")
        if device.get("fault_codes"):
            sensor_support += ids("check_device_status")
        if ref_normal:
            sensor_support += ids("check_related_measurements")
        add(Cause.SENSOR, sensor_support,
            ids("check_related_measurements") if ref_high else [])
    if high:
        process_support = ids("check_variation")
        if ref_high:
            process_support += ids("check_related_measurements")
        if not fresh:
            process_conflicts = ids("check_freshness")
        else:
            process_conflicts = ids("check_related_measurements") if ref_normal else []
        add(Cause.PROCESS, process_support, process_conflicts)
    if freshness and not fresh:
        add(Cause.COMMUNICATION, ids("check_freshness", "check_device_status"),
            ids("check_device_status") if device_good else [])
    if log_available and overlap:
        add(Cause.MAINTENANCE, ids("check_maintenance_context", "check_variation"),
            ids("check_related_measurements") if ref_high else [])
    if fresh and local_normal:
        add(Cause.NORMAL, ids("check_freshness", "check_variation"),
            ids("check_maintenance_context") if overlap else [])
    add(Cause.INSUFFICIENT, [e.evidence_id for e in evidence])

    supported = []
    if complete:
        if (not fresh and freshness.get("usable_sample_count", 0) > 0
                and not freshness.get("future_timestamps")
                and not freshness.get("timestamps_out_of_order_or_duplicate")
                and device.get("online") is False
                and device.get("record_age_seconds", 0) > freshness.get("freshness_limit_seconds", 120)):
            supported.append(Cause.COMMUNICATION)
        if (fresh and high and variation.get("trailing_identical_count", 0) >= 8
                and device.get("status_fresh") and "SAMPLE_AND_HOLD" in device.get("fault_codes", [])
                and ref_normal and log_available and not events):
            supported.append(Cause.SENSOR)
        if (fresh and local_normal and device_good and ref_normal and overlap
                and all(datetime.fromisoformat(e["end"]) <= datetime.fromisoformat(freshness["latest_timestamp"])
                        for e in events)):
            supported.append(Cause.MAINTENANCE)
        if (fresh and sustained and variation.get("usable_recent_count", 0) >= 8
                and device_good and ref_high and log_available and not events):
            supported.append(Cause.PROCESS)
        if fresh and local_normal and device_good and ref_normal and log_available and not events:
            supported.append(Cause.NORMAL)
    return supported, candidates


def reference_draft(evidence: list[Evidence]) -> ReportDraft | None:
    """Offline deterministic baseline, explicitly not hosted model inference."""
    supported, candidates = assess(evidence)
    if not candidates:
        return None
    conclusion = supported[0] if len(supported) == 1 else Cause.INSUFFICIENT
    possible = [c for code, c in candidates.items() if code != Cause.INSUFFICIENT]
    if not possible:
        possible = [candidates[Cause.INSUFFICIENT]]
    return ReportDraft(conclusion=conclusion, possible_causes=possible)


def validate_draft(draft: ReportDraft, evidence: list[Evidence]) -> None:
    supported, candidates = assess(evidence)
    if draft.conclusion != Cause.INSUFFICIENT and draft.conclusion not in supported:
        raise ValueError("Conclusion lacks required fresh, corroborating evidence or completed checks.")
    if draft.conclusion != Cause.INSUFFICIENT and draft.conclusion not in [c.cause for c in draft.possible_causes]:
        raise ValueError("The concluded cause must be included among possible causes.")
    codes = [c.cause for c in draft.possible_causes]
    if len(set(codes)) != len(codes):
        raise ValueError("Possible causes must not repeat.")
    # Keep all evidence-supported alternatives, including contradictory evidence.
    required = set(candidates) - {Cause.INSUFFICIENT}
    if not required <= set(codes):
        raise ValueError("Include all hypotheses suggested by the executed evidence, even conflicting ones.")
    for proposed in draft.possible_causes:
        expected = candidates.get(proposed.cause)
        if expected is None:
            raise ValueError("A possible cause lacks evidence from the executed checks.")
        if (set(proposed.supporting_evidence_ids) != set(expected.supporting_evidence_ids)
                or set(proposed.conflicting_evidence_ids) != set(expected.conflicting_evidence_ids)):
            raise ValueError("Evidence citations must match the supporting and conflicting executed checks.")


def draft_for_conclusion(conclusion: Cause, evidence: list[Evidence]) -> ReportDraft:
    """Preserve every computed alternative without asking a model to copy it.

    The conclusion remains the submitted model judgment, subject to the same
    evidence validation as a full draft. This never substitutes a policy answer.
    """
    _, candidates = assess(evidence)
    possible = [c for code, c in candidates.items() if code != Cause.INSUFFICIENT]
    if not possible and Cause.INSUFFICIENT in candidates:
        possible = [candidates[Cause.INSUFFICIENT]]
    draft = ReportDraft(conclusion=conclusion, possible_causes=possible)
    validate_draft(draft, evidence)
    return draft


def make_report(replay: Replay, evidence: list[Evidence], attempts: list[ToolAttempt],
                mode: str, model: str | None = None, draft: ReportDraft | None = None,
                failure_reason: str | None = None) -> IncidentReport:
    if draft is None:
        draft = reference_draft(evidence)
    if draft is not None:
        validate_draft(draft, evidence)
    conclusion = draft.conclusion if draft and failure_reason is None else Cause.INSUFFICIENT
    possible = [PossibleCause(**c.model_dump(), interpretation=interpretation_for(c.cause, evidence))
                for c in draft.possible_causes] if draft else []
    by_tool = {e.tool: e.data for e in evidence}
    uncertainty = ["All inputs are simulated; field accuracy is unknown.",
                   "No physical confirmation test was performed by the agent."]
    if mode == "offline_reference_policy":
        uncertainty.append("An offline reference policy selected the checks and interpretation; Nemotron was not called.")
    missing = set(TOOL_DESCRIPTIONS) - by_tool.keys()
    if missing:
        uncertainty.append("Checks not completed: " + ", ".join(sorted(missing)) + ".")
    related = by_tool.get("check_related_measurements", {})
    if not any(s["role"] == "independent_outlet_turbidity" and s["fresh"]
               for s in related.get("signals", [])):
        uncertainty.append("A fresh independent outlet measurement is missing; a sensor artifact and process change cannot be distinguished.")
    if not by_tool.get("check_maintenance_context", {}).get("log_available", False):
        uncertainty.append("Maintenance context is unavailable; absence of a record is not evidence of no maintenance.")
    if conclusion == Cause.INSUFFICIENT:
        uncertainty.append("The investigation is inconclusive; obtain the missing evidence before assigning a cause.")
    if conclusion == Cause.MAINTENANCE:
        uncertainty.append("Maintenance timing alone does not prove it caused the excursion.")
    if conclusion == Cause.PROCESS:
        uncertainty.append("Corroborating elevated readings do not identify the underlying process fault.")
    if failure_reason:
        uncertainty.append(failure_reason)
    actions = [OperatorAction(action="Follow the site's existing alarm and escalation procedure.")]
    action_by_cause = {
        Cause.NORMAL: "Review the historical crossing and continue observation under the site's procedure.",
        Cause.SENSOR: "Ask an operator to inspect the sensor and verify its calibration and recorded fault.",
        Cause.COMMUNICATION: "Ask an operator to check device power, communication and the last received timestamp.",
        Cause.MAINTENANCE: "Ask an operator to confirm the maintenance record and review readings after the activity.",
        Cause.PROCESS: "Ask an operator to review filter performance and confirm the excursion with an independent outlet sample.",
        Cause.INSUFFICIENT: "Request a time-matched independent outlet turbidity measurement using the site's approved procedure, plus device and maintenance records.",
    }
    actions.append(OperatorAction(action=action_by_cause[conclusion]))
    if conclusion in (Cause.SENSOR, Cause.COMMUNICATION, Cause.MAINTENANCE):
        actions.append(OperatorAction(action="Request a time-matched independent outlet turbidity measurement using the site's approved procedure."))
    return IncidentReport(incident=replay.incident_context(), investigation_mode=mode,
                          model=model, investigation_status="incomplete" if failure_reason else "complete",
                          conclusion=conclusion, observations=evidence,
                          checks_performed=[e.tool for e in evidence], tool_attempts=attempts,
                          possible_causes=possible, uncertainty=uncertainty,
                          suggested_operator_actions=actions)


def render_markdown(report: IncidentReport) -> str:
    lines = ["# SIMULATED incident investigation", "",
             f"Incident: **{report.incident['incident_id']}**  ",
             f"Replay time: {report.incident['observed_at']}  ",
             f"Mode: `{report.investigation_mode}`  ",
             f"Investigation status: `{report.investigation_status}`  ",
             f"Model: `{report.model or 'none — offline reference policy'}`", "",
             f"Conclusion: **{report.conclusion.value}**", "",
             "Demonstration thresholds only. This report does not determine whether water is safe.", "",
             "## Evidence at a glance", ""]
    lines += [f"- **{item.evidence_id}:** {observation_summary(item)}" for item in report.observations]
    lines += ["",
             "## Observations and checks actually performed", ""]
    for item in report.observations:
        lines += [f"### {item.evidence_id}: {item.tool}", "",
                  "Source: SIMULATED; computed/read from replay records.", "", "```json",
                  json.dumps(item.data, indent=2, ensure_ascii=False), "```", ""]
    if not report.observations:
        lines += ["No diagnostic check completed.", ""]
    lines += ["## Possible causes", ""]
    for cause in report.possible_causes:
        support = ", ".join(cause.supporting_evidence_ids)
        conflict = ", ".join(cause.conflicting_evidence_ids) or "none identified by the completed checks"
        lines += [f"- **{cause.cause.value}**: {cause.interpretation}",
                  f"  Supporting checks: {support}. Conflicting checks: {conflict}."]
    lines += ["", "## Uncertainty", ""] + [f"- {u}" for u in report.uncertainty]
    lines += ["", "## Suggested operator actions", ""]
    lines += [f"- **Requested, not performed:** {a.action}" for a in report.suggested_operator_actions]
    lines += ["", "## Tool attempts", ""]
    lines += [f"- {a.tool}: {a.status}" + (f" ({a.evidence_id})" if a.evidence_id else "")
              + (f" — {a.reason}" if a.reason else "") for a in report.tool_attempts]
    lines += ["", "## Operational boundaries", ""] + [f"- {b}" for b in report.boundaries]
    return "\n".join(lines) + "\n"


def save_report(report: IncidentReport, directory: Path, stem: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
