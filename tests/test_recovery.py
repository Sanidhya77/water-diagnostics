"""Recovery must be bounded, verified, source-labelled and entirely offline."""

from dataclasses import replace
from datetime import timedelta
import json

import httpx
import pytest

import water_diagnostics.recovery as recovery
from water_diagnostics.config import DEFAULT_MODEL
from water_diagnostics.incident_reports.reporting import make_report, save_report
from water_diagnostics.investigator import investigate_offline


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("Recovery simulation must not send HTTP requests"))


@pytest.mark.parametrize("case,outcome,verification", [
    ("collector_recovers", "telemetry_restored", "passed"),
    ("collector_stays_offline", "escalated", "failed"),
])
def test_one_acknowledged_attempt_requires_independent_readback(case, outcome, verification, tmp_path):
    fixture = recovery.make_fixture(case)
    original = fixture.replay.model_dump_json()
    driver = recovery.SimulatedCollector(fixture)
    report = recovery.run_recovery(fixture, root=tmp_path, driver=driver)
    assert report.outcome == outcome and report.verification.status == verification
    assert report.source == "SIMULATED_RECOVERY" and report.diagnostic_origin == "offline_reference_policy"
    assert report.policy.verdict == "approved" and report.action_status == "simulated_executed"
    assert report.action_acknowledged is True and report.attempts == driver.attempts == 1
    assert len(report.investigation.observations) == 5
    assert fixture.replay.model_dump_json() == original
    if outcome == "telemetry_restored":
        assert report.verification.new_valid_packets == 2 and report.escalation is None
        assert all(p.value > fixture.replay.alarm_threshold_ntu for p in report.after.packets)
        assert report.investigation.conclusion.value == "communication_loss"
        assert "Elevated readings" in report.events[-1]
    else:
        assert report.escalation.delivery_status == "recorded_not_sent"
        assert report.escalation.priority == "operator_attention"
        assert report.verification.new_valid_packets == 0


@pytest.mark.parametrize("change", ["old_packets", "future_packet", "duplicate_sequence", "out_of_order", "foreign_target",
                                   "invalid_quality", "missing_value", "no_heartbeat", "offline", "new_hazard", "late_window"])
def test_bad_readback_cannot_become_verified_recovery(change, tmp_path):
    fixture = recovery.make_fixture("collector_recovers")
    after = fixture.after
    packets = list(after.packets)
    if change == "old_packets":
        after = after.model_copy(update={"packets": fixture.before.packets})
    elif change == "future_packet":
        packets[0] = packets[0].model_copy(update={"timestamp": after.observed_at + timedelta(seconds=1)})
    elif change == "duplicate_sequence":
        packets[1] = packets[1].model_copy(update={"sequence": packets[0].sequence})
    elif change == "out_of_order":
        packets.reverse()
    elif change == "foreign_target":
        packets[0] = packets[0].model_copy(update={"collector_id": "OTHER-COLLECTOR"})
    elif change == "invalid_quality":
        packets[0] = packets[0].model_copy(update={"quality": "invalid"})
    elif change == "missing_value":
        packets[0] = packets[0].model_copy(update={"value": None})
    elif change == "no_heartbeat":
        after = after.model_copy(update={"heartbeat_at": fixture.before.heartbeat_at})
    elif change == "offline":
        after = after.model_copy(update={"connected": False})
    elif change == "new_hazard":
        after = after.model_copy(update={"safety_state": "hazard"})
    else:
        after = after.model_copy(update={"observed_at": after.observed_at + timedelta(seconds=1)})
    if change not in ("old_packets",):
        after = after.model_copy(update={"packets": tuple(packets)})
    report = recovery.run_recovery(replace(fixture, after=after), root=tmp_path)
    assert report.outcome == "escalated" and report.verification.status == "failed"
    assert report.attempts == 1 and report.escalation.delivery_status == "recorded_not_sent"
    if change == "new_hazard":
        assert report.escalation.priority == "immediate"


@pytest.mark.parametrize("location,risk", [("context", "hazard"), ("context", "unknown"), ("before", "hazard"), ("before", "unknown")])
def test_hazard_or_unknown_risk_escalates_before_any_investigation_or_action(location, risk, tmp_path, monkeypatch):
    fixture = recovery.make_fixture("collector_recovers")
    fixture = replace(fixture, **{location: getattr(fixture, location).model_copy(update={"safety_state": risk})})
    monkeypatch.setattr(recovery, "load_investigation", lambda *a, **k: pytest.fail("Escalation must precede model/diagnostic work"))
    driver = recovery.SimulatedCollector(fixture)
    report = recovery.run_recovery(fixture, root=tmp_path, driver=driver)
    assert report.attempts == driver.attempts == 0 and report.action_status == "not_executed"
    assert report.policy.verdict == "blocked" and report.verification.status == "not_run"
    assert report.investigation is None and report.diagnostic_origin == "not_run"
    assert report.escalation.priority == "immediate" and report.escalation.delivery_status == "recorded_not_sent"


def test_missing_preapproval_requires_operator_and_executes_nothing(tmp_path):
    fixture = recovery.make_fixture("collector_recovers")
    fixture = replace(fixture, context=fixture.context.model_copy(update={"preapproved_actions": ()}))
    report = recovery.run_recovery(fixture, root=tmp_path)
    assert report.policy.verdict == report.outcome == "approval_required"
    assert report.attempts == 0 and report.after is None


@pytest.mark.parametrize("action_request,context_change,attempts", [
    (recovery.ActionRequest(action="clear_alarm", target=recovery.TARGET), {}, 0),
    (recovery.ActionRequest(action=recovery.ACTION, target="PLANT-PUMP"), {}, 0),
    (recovery.ActionRequest(action=recovery.ACTION, target=recovery.TARGET), {"capabilities": ()}, 0),
    (recovery.ActionRequest(action=recovery.ACTION, target=recovery.TARGET), {"telemetry_only": False}, 0),
    (recovery.ActionRequest(action=recovery.ACTION, target=recovery.TARGET), {}, 1),
])
def test_action_gate_rejects_other_actions_targets_missing_capability_and_retries(action_request, context_change, attempts):
    fixture = recovery.make_fixture("collector_recovers")
    decision = recovery.authorize(action_request, fixture.context.model_copy(update=context_change), attempts,
                                  investigate_offline(fixture.replay), fixture.before)
    assert decision.verdict == "blocked"


@pytest.mark.parametrize("error,status", [(TimeoutError, "simulated_timeout"), (RuntimeError, "simulated_failed")])
def test_failure_consumes_attempt_and_does_not_leak_driver_error_or_retry(error, status, tmp_path):
    fixture = recovery.make_fixture("collector_recovers")

    class Failing(recovery.SimulatedCollector):
        calls = 0

        def reconnect(self):
            self.calls += 1
            raise error("SECRET_DRIVER_DETAILS")

    driver = Failing(fixture)
    report = recovery.run_recovery(fixture, root=tmp_path, driver=driver)
    assert report.action_status == status and report.outcome == "escalated"
    assert report.attempts == driver.attempts == driver.calls == 1
    assert "SECRET_DRIVER_DETAILS" not in report.model_dump_json()
    again = recovery.run_recovery(fixture, root=tmp_path, driver=driver)
    assert again.policy.verdict == "blocked" and driver.calls == 1


def hosted_diagnosis(directory, fixture):
    baseline = investigate_offline(fixture.replay)
    report = make_report(fixture.replay, baseline.observations, baseline.tool_attempts, "nebius_model", DEFAULT_MODEL)
    path, _ = save_report(report, directory / "reports", fixture.replay.incident_id + "-nebius")
    return path, report


def test_saved_hosted_investigation_is_recomputed_and_reused_without_new_model_request(tmp_path):
    fixture = recovery.make_fixture("collector_recovers")
    path, diagnosis = hosted_diagnosis(tmp_path, fixture)
    before = path.read_bytes()
    report = recovery.run_recovery(fixture, root=tmp_path)
    assert report.diagnostic_origin == "saved_nebius_investigation" and report.investigation == diagnosis
    assert report.outcome == "telemetry_restored" and path.read_bytes() == before


@pytest.mark.parametrize("corruption", ["evidence", "incomplete", "physical_claim", "context"])
def test_invalid_saved_diagnosis_blocks_before_driver(corruption, tmp_path):
    fixture = recovery.make_fixture("collector_recovers")
    path, diagnosis = hosted_diagnosis(tmp_path, fixture)
    if corruption == "evidence":
        diagnosis.observations[0].data["fresh"] = True
    elif corruption == "incomplete":
        diagnosis.investigation_status = "incomplete"
    elif corruption == "physical_claim":
        diagnosis.suggested_operator_actions[0].action = "The sensor has been physically repaired."
    else:
        diagnosis.incident["sensor_id"] = "OTHER"
    path.write_text(diagnosis.model_dump_json(), encoding="utf-8")
    driver = recovery.SimulatedCollector(fixture)
    with pytest.raises(recovery.RecoveryError, match="failed the evidence audit"):
        recovery.run_recovery(fixture, root=tmp_path, driver=driver)
    assert driver.attempts == 0


def test_case_name_is_only_a_label_and_reports_preserve_history(tmp_path):
    fixture = replace(recovery.make_fixture("collector_recovers"), case="different human label")
    report = recovery.run_recovery(fixture, root=tmp_path)
    assert report.outcome == "telemetry_restored"
    json_path, markdown_path = recovery.save_recovery(report, tmp_path / "output")
    before = json_path.read_bytes()
    assert recovery.RecoveryReport.model_validate_json(json_path.read_text(encoding="utf-8")) == report
    assert "SIMULATED_RECOVERY" in markdown_path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        recovery.save_recovery(report, tmp_path / "output")
    assert json_path.read_bytes() == before
