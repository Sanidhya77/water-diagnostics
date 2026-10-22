"""Constrained model interpretation plus an application-owned evidence ledger."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Cause(StrEnum):
    NORMAL = "normal_behaviour"
    SENSOR = "sensor_problem"
    COMMUNICATION = "communication_loss"
    MAINTENANCE = "maintenance_disturbance"
    PROCESS = "process_change"
    INSUFFICIENT = "insufficient_evidence"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CauseDraft(StrictModel):
    cause: Cause
    supporting_evidence_ids: list[str] = Field(min_length=1, max_length=5)
    conflicting_evidence_ids: list[str] = Field(default_factory=list, max_length=5)


class ReportDraft(StrictModel):
    conclusion: Cause
    possible_causes: list[CauseDraft] = Field(min_length=1, max_length=6)


class ConclusionSubmission(StrictModel):
    """Model judgment; evidence alternatives and citations belong to Python."""

    conclusion: Cause


class Evidence(StrictModel):
    evidence_id: str
    tool: str
    source: Literal["SIMULATED"] = "SIMULATED"
    data: dict


class ToolAttempt(StrictModel):
    tool: str
    status: Literal["performed", "rejected"]
    evidence_id: str | None = None
    reason: str | None = None


class PossibleCause(CauseDraft):
    interpretation: str


class OperatorAction(StrictModel):
    action: str
    status: Literal["requested_not_performed"] = "requested_not_performed"


class IncidentReport(StrictModel):
    source: Literal["SIMULATED"] = "SIMULATED"
    incident: dict
    investigation_mode: Literal["offline_reference_policy", "nebius_model"]
    model: str | None = None
    investigation_status: Literal["complete", "incomplete"] = "complete"
    conclusion: Cause
    observations: list[Evidence]
    checks_performed: list[str]
    tool_attempts: list[ToolAttempt]
    possible_causes: list[PossibleCause]
    uncertainty: list[str]
    suggested_operator_actions: list[OperatorAction]
    boundaries: tuple[str, ...] = (
        "Existing plant alarms remain independent and immediate.",
        "This agent cannot operate equipment, change treatment settings, or clear alarms.",
        "This report does not determine whether water is safe.",
        "Simulated results do not establish field accuracy or business savings.",
    )
