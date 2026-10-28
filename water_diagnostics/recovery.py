"""Bounded collector-recovery simulations. No hardware, process or network driver.

The diagnostic investigator supplies evidence; a local reference policy proposes
one action. A separate gate authorizes it, a simulated driver executes it, and
post-action packets establish transport recovery. No new model is called here.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from water_diagnostics.config import DEFAULT_MODEL, PROJECT_ROOT
from water_diagnostics.incident_reports.audit import audit_report
from water_diagnostics.incident_reports.schema import Cause, IncidentReport
from water_diagnostics.investigator import investigate_offline
from water_diagnostics.simulator import Replay, make_replay


CASES = {"collector_recovers": "Collector recovers", "collector_stays_offline": "Collector stays offline"}
ACTION = "reconnect_collector"
TARGET = "SIM-COLLECTOR-01"
BOUNDARIES = (
    "All recovery actions, packets and recovery timestamps are simulated.",
    "The policy selects the recovery action; no new Nemotron or Tavily request is made.",
    "Telemetry recovery does not establish a resolved process fault or water safety.",
    "No physical equipment, plant settings, alarms or real collector processes are changed.",
    "Escalations are recorded locally; no notification is sent.",
)


class RecoveryError(ValueError):
    pass


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SafetyContext(Record):
    """Trusted demo configuration, never accepted from browser/model input."""
    environment: Literal["SIMULATED"] = "SIMULATED"
    collector_id: str = TARGET
    telemetry_only: bool = True
    safety_state: Literal["clear", "hazard", "unknown"] = "unknown"
    capabilities: tuple[str, ...] = ()
    preapproved_actions: tuple[str, ...] = ()


class Packet(Record):
    source: Literal["SIMULATED_COLLECTOR"] = "SIMULATED_COLLECTOR"
    collector_id: str = TARGET
    unit: Literal["NTU"] = "NTU"
    sequence: int = Field(ge=0)
    timestamp: AwareDatetime
    value: float | None = Field(default=None, allow_inf_nan=False, ge=0)
    quality: Literal["good", "invalid"] = "good"


class Readback(Record):
    observed_at: AwareDatetime
    connected: bool
    heartbeat_at: AwareDatetime | None = None
    safety_state: Literal["clear", "hazard", "unknown"] = "unknown"
    packets: tuple[Packet, ...] = ()


class ActionRequest(Record):
    action: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)


class PolicyDecision(Record):
    verdict: Literal["approved", "blocked", "approval_required"]
    reason: str


class Verification(Record):
    status: Literal["passed", "failed", "not_run"]
    reasons: tuple[str, ...]
    new_valid_packets: int = 0


class Escalation(Record):
    priority: Literal["immediate", "operator_attention"]
    reason: str
    delivery_status: Literal["recorded_not_sent"] = "recorded_not_sent"
    requested_action: str = "Review collector connectivity and obtain independent current measurements under the site's procedure."


class RecoveryReport(Record):
    source: Literal["SIMULATED_RECOVERY"] = "SIMULATED_RECOVERY"
    run_id: str
    created_at: AwareDatetime
    case: str
    diagnostic_origin: Literal["offline_reference_policy", "saved_nebius_investigation", "not_run"]
    investigation: IncidentReport | None
    context: SafetyContext
    proposed_action: ActionRequest | None
    policy: PolicyDecision
    attempts: int = Field(ge=0, le=1)
    action_status: Literal["not_executed", "simulated_executed", "simulated_failed", "simulated_timeout"]
    action_acknowledged: bool | None = None
    before: Readback
    after: Readback | None
    verification: Verification
    outcome: Literal["telemetry_restored", "escalated", "approval_required"]
    escalation: Escalation | None
    events: tuple[str, ...]
    boundaries: tuple[str, ...] = BOUNDARIES


@dataclass(frozen=True)
class Fixture:
    case: str
    replay: Replay
    context: SafetyContext
    before: Readback
    after: Readback


def make_fixture(case: str) -> Fixture:
    if not isinstance(case, str) or case not in CASES:
        raise RecoveryError("Choose one of the two collector-recovery simulations.")
    replay = make_replay("communication_loss")
    clock = replay.observed_at
    context = SafetyContext(safety_state="clear", capabilities=(ACTION,), preapproved_actions=(ACTION,))
    before = Readback(observed_at=clock, connected=False, safety_state="clear",
        heartbeat_at=replay.device.timestamp,
        packets=(Packet(sequence=100, timestamp=replay.samples[-1].timestamp, value=replay.samples[-1].value),))
    # Future readings are created only inside the separate recovery simulation.
    # They never enter the original replay or the original diagnostic report.
    packets = tuple(Packet(sequence=101 + i, timestamp=clock + timedelta(seconds=60 * (i + 1)),
                           value=value) for i, value in enumerate((0.742, 0.739)))
    after = Readback(observed_at=clock + timedelta(seconds=125), connected=case == "collector_recovers",
        safety_state="clear", heartbeat_at=clock + timedelta(seconds=125) if case == "collector_recovers" else before.heartbeat_at,
        packets=packets if case == "collector_recovers" else before.packets)
    return Fixture(case, replay, context, before, after)


def authorize(request: ActionRequest, context: SafetyContext, attempts: int,
              investigation: IncidentReport | None, before: Readback) -> PolicyDecision:
    if context.safety_state != "clear":
        return PolicyDecision(verdict="blocked", reason="Safety state is hazardous or unknown; escalate immediately.")
    if not context.telemetry_only:
        return PolicyDecision(verdict="blocked", reason="Only the isolated simulated telemetry collector is in scope.")
    if before.connected:
        return PolicyDecision(verdict="blocked", reason="The required disconnected-collector precondition is absent.")
    if request.action != ACTION or request.target != TARGET or request.target != context.collector_id:
        return PolicyDecision(verdict="blocked", reason="Action or target is outside the recovery allowlist.")
    if attempts >= 1:
        return PolicyDecision(verdict="blocked", reason="The one-attempt recovery limit has been reached.")
    if request.action not in context.capabilities:
        return PolicyDecision(verdict="blocked", reason="The simulated collector does not support this action.")
    if (investigation is None or investigation.investigation_status != "complete"
            or investigation.conclusion != Cause.COMMUNICATION):
        return PolicyDecision(verdict="blocked", reason="A completed communication-loss investigation is required.")
    if request.action not in context.preapproved_actions:
        return PolicyDecision(verdict="approval_required", reason="This action is not pre-authorized; operator approval is required.")
    return PolicyDecision(verdict="approved", reason="One reconnect of the telemetry-only demo collector is pre-authorized.")


class SimulatedCollector:
    """An in-memory state transition, with no shell, socket, GPIO or device API."""
    def __init__(self, fixture: Fixture):
        self.before, self.after = fixture.before, fixture.after
        self.attempts = 0

    def reconnect(self) -> bool:
        if self.attempts >= 1:
            raise RecoveryError("The simulated driver permits only one reconnect attempt.")
        self.attempts += 1
        return True  # An acknowledgement is deliberately identical for both outcomes.

    def readback(self) -> Readback:
        return self.after if self.attempts else self.before


def verify(before: Readback, after: Readback, action_at: datetime) -> Verification:
    reasons = []
    if after.safety_state != "clear":
        reasons.append("The post-action safety state is hazardous or unknown.")
    if not after.connected:
        reasons.append("The collector remains disconnected.")
    if after.observed_at < action_at or after.observed_at > action_at + timedelta(seconds=125):
        reasons.append("Readback is outside the bounded simulated verification window.")
    if (after.heartbeat_at is None or not action_at < after.heartbeat_at <= after.observed_at
            or (after.observed_at - after.heartbeat_at).total_seconds() > 120):
        reasons.append("A fresh post-action collector heartbeat was not observed.")
    previous_sequence = max((p.sequence for p in before.packets), default=-1)
    valid = [p for p in after.packets if p.collector_id == TARGET and p.sequence > previous_sequence
             and action_at < p.timestamp <= after.observed_at and p.value is not None and p.quality == "good"
             and (after.observed_at - p.timestamp).total_seconds() <= 120]
    if (len(valid) < 2 or any(a.timestamp >= b.timestamp or a.sequence >= b.sequence
                              for a, b in zip(valid, valid[1:]))):
        reasons.append("Two ordered, fresh post-action packets with new sequence IDs were not observed.")
    if any(p.timestamp > after.observed_at for p in after.packets):
        reasons.append("Readback contains a future packet.")
    return Verification(status="failed" if reasons else "passed", reasons=tuple(reasons) or (
        "Two new ordered packets and a fresh heartbeat verify simulated telemetry recovery only.",),
        new_valid_packets=len(valid))


def load_investigation(replay: Replay, root: Path, explicit: Path | None = None):
    pattern = re.compile(re.escape(replay.incident_id + "-nebius") + r"(?:-retry)*\.json")
    paths = ([explicit] if explicit is not None else [
        path for directory in (root / "reports" / "demo-validation", root / "demo_reports", root / "reports")
        for path in sorted((p for p in directory.glob(replay.incident_id + "-nebius*.json")
                            if pattern.fullmatch(p.name)), key=lambda p: len(p.name), reverse=True)])
    if paths:
        try:
            report = IncidentReport.model_validate_json(paths[0].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise RecoveryError("Saved diagnosis is unreadable; no recovery action executed.") from None
        if (report.investigation_mode != "nebius_model" or report.model != DEFAULT_MODEL
                or audit_report(report, replay)):
            raise RecoveryError("Saved diagnosis failed the evidence audit; no recovery action executed.")
        return report, "saved_nebius_investigation"
    return investigate_offline(replay), "offline_reference_policy"


def run_recovery(fixture: Fixture, root: Path = PROJECT_ROOT, investigation_path: Path | None = None,
                 driver: SimulatedCollector | None = None) -> RecoveryReport:
    driver = driver or SimulatedCollector(fixture)
    context = fixture.context
    # Any risk signal wins; a clear configuration must never override a
    # hazardous/unknown readback or a context from another simulation clock.
    risks = (context.safety_state, fixture.before.safety_state)
    if "hazard" in risks:
        context = context.model_copy(update={"safety_state": "hazard"})
    elif "unknown" in risks or fixture.before.observed_at != fixture.replay.observed_at:
        context = context.model_copy(update={"safety_state": "unknown"})
    events = ["Observed a disconnected simulated collector; existing plant alarms remain independent."]
    request = ActionRequest(action=ACTION, target=TARGET)
    diagnosis, origin = None, "not_run"
    # The trusted safety gate runs before any investigator, including saved AI.
    if context.safety_state == "clear" and context.telemetry_only:
        diagnosis, origin = load_investigation(fixture.replay, Path(root), investigation_path)
        events.append("Recomputed and audited the saved diagnosis." if origin == "saved_nebius_investigation"
                      else "Executed five local diagnostic checks; no model called.")
        if audit_report(diagnosis, fixture.replay):
            raise RecoveryError("Diagnostic evidence failed validation; no recovery action executed.")
        events.append("Local evidence policy proposed one collector reconnect.")
    attempts = driver.attempts
    decision = authorize(request, context, attempts, diagnosis, fixture.before)
    events.append("Policy " + decision.verdict + ": " + decision.reason)
    action_status, acknowledged, after = "not_executed", None, None
    verification = Verification(status="not_run", reasons=("No recovery action was executed.",))
    outcome = "approval_required" if decision.verdict == "approval_required" else "escalated"
    if decision.verdict == "approved":
        attempts += 1  # Consume the attempt before the driver can fail or time out.
        try:
            acknowledged = driver.reconnect()
            action_status = "simulated_executed"
            events.append("Executed one in-memory reconnect attempt; no real process or hardware changed.")
            after = driver.readback()
            verification = verify(fixture.before, after, fixture.replay.observed_at)
            if verification.status == "passed":
                outcome = "telemetry_restored"
            events.append("Verification " + verification.status + ": " + " ".join(verification.reasons))
        except TimeoutError:
            action_status = "simulated_timeout"
            verification = Verification(status="failed", reasons=("The simulated action timed out; outcome is unverified. No retry.",))
        except Exception:
            action_status = "simulated_failed"
            verification = Verification(status="failed", reasons=("The simulated driver failed; outcome is unverified. No retry.",))
        finally:
            driver.attempts = max(driver.attempts, attempts)
    escalation = None
    if outcome != "telemetry_restored":
        immediate = context.safety_state != "clear" or (after is not None and after.safety_state != "clear")
        reason = decision.reason if decision.verdict != "approved" else " ".join(verification.reasons)
        escalation = Escalation(priority="immediate" if immediate else "operator_attention", reason=reason)
        events.append("Escalation recorded for operator review; notification not sent. No further attempt.")
    else:
        events.append("Telemetry recovery verified. Elevated readings still require a separate process/sensor investigation.")
    return RecoveryReport(run_id="REC-" + uuid4().hex, created_at=datetime.now(timezone.utc), case=fixture.case,
        diagnostic_origin=origin, investigation=diagnosis, context=context, proposed_action=request,
        policy=decision, attempts=attempts, action_status=action_status, action_acknowledged=acknowledged,
        before=fixture.before, after=after, verification=verification, outcome=outcome,
        escalation=escalation, events=tuple(events))


def run_recovery_demo(case: str, root: Path = PROJECT_ROOT, investigation_path: Path | None = None):
    return run_recovery(make_fixture(case), root=root, investigation_path=investigation_path)


def render_recovery(report: RecoveryReport) -> str:
    lines = ["# Simulated collector recovery", "", "Source: SIMULATED_RECOVERY", f"Run: {report.run_id}",
             f"Case: {CASES.get(report.case, report.case)}", f"Outcome: **{report.outcome}**", "",
             f"Diagnostic source: {report.diagnostic_origin}. Recovery action selected by the local evidence policy.",
             "No new model/search request or hardware action.", "", "## Action and policy", "",
             f"Proposed: {report.proposed_action.action} on {report.proposed_action.target}.",
             f"Policy: {report.policy.verdict} — {report.policy.reason}",
             f"Execution: {report.action_status}; attempts: {report.attempts}/1; acknowledgement: {report.action_acknowledged}.",
             "", "## Verification", "", f"Result: {report.verification.status}; new valid packets: {report.verification.new_valid_packets}."]
    lines += ["- " + reason for reason in report.verification.reasons]
    lines += ["", "### Before and after (simulated clock)", "", "```json",
              json.dumps({"before": report.before.model_dump(mode="json"),
                          "after": report.after.model_dump(mode="json") if report.after else None}, indent=2), "```", ""]
    if report.escalation:
        lines += ["## Escalation", "", f"Priority: {report.escalation.priority}; delivery: recorded, not sent.",
                  report.escalation.reason, report.escalation.requested_action, ""]
    if report.investigation:
        lines += ["## Diagnostic evidence used", "", f"Conclusion before recovery: {report.investigation.conclusion.value}."]
        lines += [f"- {e.evidence_id}: {e.tool}" for e in report.investigation.observations]
        lines += ["The JSON report contains the complete original diagnosis and executed observations.", ""]
    lines += ["## Execution record", ""] + [f"{i}. {event}" for i, event in enumerate(report.events, 1)]
    lines += ["", "## Boundaries", ""] + ["- " + text for text in report.boundaries]
    return "\n".join(lines) + "\n"


def save_recovery(report: RecoveryReport, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    paths = directory / (report.run_id + ".json"), directory / (report.run_id + ".md")
    # A simulation is a new run; never replace an earlier execution record.
    for path, content in zip(paths, (report.model_dump_json(indent=2), render_recovery(report))):
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    return paths
