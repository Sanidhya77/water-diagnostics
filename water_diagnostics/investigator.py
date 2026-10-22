"""Bounded model -> tool -> evidence loop, with an explicit offline baseline."""

import json
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from water_diagnostics.diagnostic_tools.checks import DiagnosticTools, TOOL_DESCRIPTIONS, tool_schemas
from water_diagnostics.incident_reports.reporting import assess, draft_for_conclusion, make_report
from water_diagnostics.incident_reports.schema import Cause, ConclusionSubmission, Evidence, IncidentReport, ToolAttempt
from water_diagnostics.model_client.nebius import ModelClientError
from water_diagnostics.simulator import Replay


class ChatClient(Protocol):
    model: str

    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 max_tokens: int = 4096) -> dict: ...


class FunctionCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=100)
    arguments: str = Field(max_length=12000)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=200)
    type: Literal["function"]
    function: FunctionCall


SYSTEM_PROMPT = """You investigate simulated filter outlet turbidity alarms for a human operator.
Use the five approved read-only diagnostic tools. Python does all numerical checks.
Select tools, read their results, then select the next check. All five checks must
be attempted successfully before a final report, even when records are unavailable.
Never invent a tool result, a physical test, water-safety finding or equipment action.
The replay clock and demonstration threshold are not real plant or regulatory limits.
Recorded maintenance is context; a requested physical test has not been performed.
Existing alarms remain independent. You cannot control equipment or clear alarms.
Tool results include evidence IDs and conservative demo report constraints. Read
every reportable hypothesis, including its supporting and conflicting evidence.
Choose a conclusion from allowed_conclusions; choose insufficient_evidence if the
evidence does not distinguish causes. These constraints are derived from executed
checks, not from hidden scenario labels. Never assume missing context is normal.
Once the evidence is complete, call submit_report on a separate turn, without any
other tool calls. It accepts only {"conclusion": "an allowed conclusion"}. The
application preserves every evidence-derived alternative and its exact citations,
then adds observations, uncertainty and requested operator actions. Do not copy,
filter or rewrite alternatives in submit_report. Do not write
a free-text report. Do not repeat completed checks. Use no diagnostic tool arguments.
"""


def report_tool_schema(evidence: list[Evidence] | None = None) -> dict:
    parameters = ConclusionSubmission.model_json_schema()
    if evidence is not None:
        parameters["properties"]["conclusion"] = {
            "type": "string", "enum": _report_constraints(evidence)["allowed_conclusions"],
        }
    return {"type": "function", "function": {
        "name": "submit_report", "description": "Select the conclusion supported by the completed evidence. Python preserves all alternatives and citations.",
        "parameters": parameters,
    }}


def _report_constraints(evidence: list[Evidence]) -> dict:
    supported, candidates = assess(evidence)
    return {
        "checks_still_required": [n for n in TOOL_DESCRIPTIONS if n not in {e.tool for e in evidence}],
        "allowed_conclusions": [c.value for c in supported] + [Cause.INSUFFICIENT.value],
        "reportable_hypotheses": [c.model_dump(mode="json") for c in candidates.values()
                                 if c.cause != Cause.INSUFFICIENT],
    }


def _validate_resume(replay: Replay, report: IncidentReport) -> None:
    """Recheck saved evidence locally before spending credits on a report retry."""
    if (report.investigation_mode != "nebius_model" or report.investigation_status != "incomplete"
            or report.incident != replay.incident_context()):
        raise ModelClientError("Report retry requires an incomplete hosted report matching this simulated case and seed.")
    evidence = report.observations
    if (len(evidence) != len(TOOL_DESCRIPTIONS)
            or {e.tool for e in evidence} != set(TOOL_DESCRIPTIONS)
            or [e.evidence_id for e in evidence] != [f"E{i + 1:02d}" for i in range(len(evidence))]
            or report.checks_performed != [e.tool for e in evidence]):
        raise ModelClientError("Report retry requires all five saved checks with unique, consistent evidence IDs.")
    tools = DiagnosticTools(replay)
    performed = [(a.tool, a.evidence_id) for a in report.tool_attempts if a.status == "performed"]
    if performed != [(e.tool, e.evidence_id) for e in evidence]:
        raise ModelClientError("Saved evidence does not match the recorded tool executions; no request sent.")
    for item in evidence:
        if item.data != tools.execute(item.tool, {})["data"]:
            raise ModelClientError("Saved evidence differs from this local replay; no request sent.")


def _record(tools: DiagnosticTools, name: str, evidence: list[Evidence],
            attempts: list[ToolAttempt], progress: Callable[[str], None] | None = None) -> Evidence:
    result = tools.execute(name, {})
    item = Evidence(evidence_id=f"E{len(evidence) + 1:02d}", tool=name, data=result["data"])
    evidence.append(item)
    attempts.append(ToolAttempt(tool=name, status="performed", evidence_id=item.evidence_id))
    if progress:
        progress(f"{item.evidence_id}: {name} performed on simulated records")
    return item


def investigate_offline(replay: Replay, progress: Callable[[str], None] | None = None) -> IncidentReport:
    tools = DiagnosticTools(replay)
    evidence: list[Evidence] = []
    attempts: list[ToolAttempt] = []
    freshness = _record(tools, "check_freshness", evidence, attempts, progress)
    # Data loss changes the next check. No hidden scenario name is inspected.
    second = "check_variation" if freshness.data["fresh"] else "check_device_status"
    _record(tools, second, evidence, attempts, progress)
    for name in TOOL_DESCRIPTIONS:
        if name not in {e.tool for e in evidence}:
            _record(tools, name, evidence, attempts, progress)
    return make_report(replay, evidence, attempts, "offline_reference_policy")


def investigate_nebius(replay: Replay, client: ChatClient,
                       progress: Callable[[str], None] | None = None,
                       max_rounds: int = 8, max_tool_calls: int = 12,
                       resume_report: IncidentReport | None = None) -> IncidentReport:
    tools = DiagnosticTools(replay)
    evidence: list[Evidence] = []
    attempts: list[ToolAttempt] = []
    if resume_report is not None:
        _validate_resume(replay, resume_report)
        evidence = list(resume_report.observations)
        attempts = list(resume_report.tool_attempts)
        max_rounds = 1  # One paid report request; never replay the five model turns.
        if progress:
            progress("Revalidated five saved checks locally; retrying only the final report.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(replay.incident_context())}]
    schemas = tool_schemas() + [report_tool_schema()]
    seen_ids: set[str] = set()
    total_calls = 0
    failure = "Investigation budget was reached before the model submitted a valid report."

    for _ in range(max_rounds):
        if total_calls >= max_tool_calls:
            break
        report_ready = not _report_constraints(evidence)["checks_still_required"]
        if report_ready:
            # Keep every executed observation, but omit the growing conversation
            # and its repeated intermediate report constraints.
            request_messages = [messages[0], {"role": "user", "content": json.dumps({
                "incident": replay.incident_context(),
                "completed_checks": [e.model_dump(mode="json") for e in evidence],
                "report_constraints": _report_constraints(evidence),
                "instruction": (
                    "All checks are complete. Call submit_report with only the conclusion field. "
                    "Select from allowed_conclusions using the completed evidence. Python will preserve "
                    "all reportable_hypotheses and their citations, including conflicting alternatives."
                ),
            })}]
            request_schemas = [report_tool_schema(evidence)]
            if progress:
                progress("Submitting compact report to Nebius; output limit: 4096 tokens; response limit: 90 seconds.")
        else:
            request_messages, request_schemas = messages, schemas
        try:
            # The report can include model reasoning before its structured tool
            # arguments. Keep diagnostic selections small, but allow the final
            # report the existing guard's 4096-token ceiling. Usage is still
            # reserved before sending and truncation still fails closed.
            message = client.complete(request_messages, request_schemas,
                                      max_tokens=4096 if report_ready else 2048)
        except ModelClientError as error:
            failure = str(error)
            break
        try:
            calls = TypeAdapter(list[ToolCall]).validate_python(message.get("tool_calls", []))
            if not calls or len(calls) > 6 or len({c.id for c in calls}) != len(calls) or any(c.id in seen_ids for c in calls):
                raise ValueError()
        except (ValidationError, ValueError, TypeError, AttributeError):
            failure = "Model did not return a valid new tool call; no unverified text report was accepted."
            break
        messages.append({"role": "assistant", "content": None,
                         "tool_calls": [c.model_dump() for c in calls]})
        for call in calls:
            if total_calls >= max_tool_calls:
                break
            total_calls += 1
            seen_ids.add(call.id)
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")
            except (json.JSONDecodeError, ValueError):
                arguments = None
            reply: dict
            if arguments is None:
                reply = {"error": "Tool arguments must be a valid JSON object."}
            elif name == "submit_report":
                if len(calls) != 1:
                    reply = {"error": "Submit the report in a separate turn after reading all tool results."}
                elif set(TOOL_DESCRIPTIONS) - {e.tool for e in evidence}:
                    reply = {"error": "Complete all five read-only checks before submitting the report."}
                else:
                    try:
                        decision = ConclusionSubmission.model_validate(arguments)
                        draft = draft_for_conclusion(decision.conclusion, evidence)
                        return make_report(replay, evidence, attempts, "nebius_model", client.model, draft)
                    except ValidationError:
                        reply = {"error": "Report submission must contain only one allowed conclusion; Python owns alternatives and citations."}
                    except ValueError as error:
                        reply = {"error": str(error)}
            elif name not in TOOL_DESCRIPTIONS:
                reply = {"error": "Tool is not in the read-only allowlist."}
            elif arguments != {}:
                reply = {"error": "Diagnostic tools take no arguments; they are bound to this incident."}
            elif name in {e.tool for e in evidence}:
                reply = {"error": "This check was already performed; use its existing evidence ID."}
            else:
                item = _record(tools, name, evidence, attempts, progress)
                reply = item.model_dump(mode="json")
            if "error" in reply:
                failure = "Model submission rejected: " + reply["error"]
                safe_name = name if name in TOOL_DESCRIPTIONS or name == "submit_report" else "unapproved_tool"
                attempts.append(ToolAttempt(tool=safe_name, status="rejected", reason=reply["error"]))
                if progress:
                    progress(f"{safe_name}: rejected ({reply['error']})")
            reply["report_constraints"] = _report_constraints(evidence)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(reply)})
    # Fail closed, retaining only checks actually executed. This is marked
    # incomplete and never silently converted into an offline model success.
    return make_report(replay, evidence, attempts, "nebius_model", client.model, failure_reason=failure)
