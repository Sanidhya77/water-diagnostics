"""Meaningful edge checks for stale, invalid and ambiguous sensor evidence."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from water_diagnostics.diagnostic_tools.checks import DiagnosticTools, TOOL_DESCRIPTIONS
from water_diagnostics.evaluation import evaluate
from water_diagnostics.incident_reports.reporting import render_markdown
from water_diagnostics.incident_reports.schema import Cause
from water_diagnostics.investigator import investigate_offline
from water_diagnostics.simulator import Sample, make_replay


def test_synthetic_suite_and_ambiguous_cases():
    summary = evaluate(investigate_offline)
    assert summary["passed"] == summary["total"] == 18
    assert summary["insufficient_evidence_passed"] == 3


def test_signal_numbers_and_plateau_are_computed_not_generated_by_model():
    replay = make_replay("frozen")
    checks = DiagnosticTools(replay)
    variation = checks.execute("check_variation", {})["data"]
    assert variation["trailing_identical_count"] == 9
    assert variation["trailing_identical_minutes"] == 8
    assert variation["latest_ntu"] == 0.72
    assert variation["recent_above_threshold_count"] == 9
    assert checks.execute("check_freshness", {})["data"]["fresh"] is True


def test_communication_loss_uses_replay_clock_not_wall_clock():
    replay = make_replay("communication_loss")
    data = DiagnosticTools(replay).execute("check_freshness", {})["data"]
    assert data["latest_age_seconds"] == 12 * 60
    assert not data["fresh"]
    report = investigate_offline(replay)
    assert report.conclusion == Cause.COMMUNICATION
    # The next check depends on stale data, rather than fixture labels.
    assert report.checks_performed[:2] == ["check_freshness", "check_device_status"]


@pytest.mark.parametrize("change", ["empty", "future", "duplicate", "invalid_latest", "null_latest"])
def test_bad_timestamps_or_quality_cannot_be_reported_as_normal(change):
    replay = make_replay("normal")
    samples = list(replay.samples)
    if change == "empty":
        samples = []
    elif change == "future":
        samples[-1] = samples[-1].model_copy(update={"timestamp": replay.observed_at + timedelta(minutes=1)})
    elif change == "duplicate":
        samples[-1] = samples[-2]
    elif change == "invalid_latest":
        samples[-1] = samples[-1].model_copy(update={"quality": "invalid"})
    else:
        samples[-1] = samples[-1].model_copy(update={"value": None})
    changed = replay.model_copy(update={"samples": tuple(samples)})
    assert not DiagnosticTools(changed).execute("check_freshness", {})["data"]["fresh"]
    assert investigate_offline(changed).conclusion == Cause.INSUFFICIENT


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -0.1])
def test_invalid_numeric_inputs_are_rejected(number):
    with pytest.raises(ValidationError):
        Sample(timestamp=make_replay("normal").observed_at, value=number)


def test_frozen_signal_without_fault_confirmation_is_ambiguous():
    replay = make_replay("frozen")
    changed = replay.model_copy(update={"device": replay.device.model_copy(update={"fault_codes": ()})})
    report = investigate_offline(changed)
    assert report.conclusion == Cause.INSUFFICIENT
    assert Cause.SENSOR in [cause.cause for cause in report.possible_causes]


def test_stale_reference_cannot_corroborate_process_change():
    replay = make_replay("process_change")
    ref = replay.related_signals[0]
    stale = tuple(s.model_copy(update={"timestamp": s.timestamp - timedelta(minutes=12)}) for s in ref.samples)
    changed = replay.model_copy(update={"related_signals": (ref.model_copy(update={"samples": stale}),
                                                            replay.related_signals[1])})
    assert investigate_offline(changed).conclusion == Cause.INSUFFICIENT


def test_missing_device_or_maintenance_is_not_assumed_normal():
    replay = make_replay("normal")
    assert investigate_offline(replay.model_copy(update={"device": None})).conclusion == Cause.INSUFFICIENT
    assert investigate_offline(replay.model_copy(update={"maintenance_log_available": False})).conclusion == Cause.INSUFFICIENT


def test_read_only_allowlist_and_bound_arguments():
    checks = DiagnosticTools(make_replay("normal"))
    with pytest.raises(ValueError, match="allowlist"):
        checks.execute("clear_alarm", {})
    with pytest.raises(ValueError, match="no arguments"):
        checks.execute("check_freshness", {"file": ".env"})


def test_report_preserves_conflicting_evidence_and_requested_actions():
    report = investigate_offline(make_replay("frozen"))
    assert report.source == "SIMULATED"
    assert set(report.checks_performed) == set(TOOL_DESCRIPTIONS)
    evidence_ids = {e.evidence_id for e in report.observations}
    process = next(c for c in report.possible_causes if c.cause == Cause.PROCESS)
    assert process.conflicting_evidence_ids
    assert set(process.supporting_evidence_ids + process.conflicting_evidence_ids) <= evidence_ids
    assert all(a.status == "requested_not_performed" for a in report.suggested_operator_actions)
    markdown = render_markdown(report)
    assert "Requested, not performed" in markdown
    assert "does not determine whether water is safe" in markdown
    assert "offline_reference_policy" in markdown


def test_reproducible_replays_have_no_truth_field():
    replay = make_replay("insufficient", 17)
    assert replay == make_replay("insufficient", 17)
    assert not {"case", "expected", "label", "scenario", "ground_truth"} & replay.model_dump().keys()
    assert set(replay.incident_context()) == {
        "source", "incident_id", "observed_at", "sensor_id", "alarm_description", "demonstration_alarm_threshold_ntu",
    }
