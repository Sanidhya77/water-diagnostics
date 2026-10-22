"""River tool protocol, causal visibility and report validation; no paid calls."""

import json

import httpx
import pytest

from test_river_data import prepare
from water_diagnostics.config import Settings
from water_diagnostics.model_client.nebius import NebiusClient
from water_diagnostics.river_data import DatasetError
from water_diagnostics.river_investigator import (
    RIVER_TOOLS, investigate_river, render_river_report, save_river_report,
)


def call(name, arguments=None, identifier="test-call"):
    return {"id": identifier, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}


def response(calls):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": calls}}]}


def client_for(handler):
    return NebiusClient(Settings(nebius_api_key="synthetic-test-key",
        nebius_base_url="https://unit.test/v1"), httpx.MockTransport(handler))


def test_offline_before_and_after_notes_have_real_labels_and_cautious_interpretation(tmp_path):
    directory, _ = prepare(tmp_path)
    before = investigate_river(directory, "2024-04-02T22:15:00Z")
    after = investigate_river(directory, "2024-04-03T00:00:00Z")
    assert before.investigation_status == after.investigation_status == "complete"
    assert before.conclusion == after.conclusion == "insufficient_evidence"
    assert "maintenance_association" not in [c.cause for c in before.possible_causes]
    assert "maintenance_association" in [c.cause for c in after.possible_causes]
    assert after.source == "REAL_RIVER_SENSOR_DATA"
    assert all(e.source == after.source for e in after.observations)
    assert after.model is None
    assert after.investigation_mode == "offline_reference_policy"
    text = render_river_report(after)
    assert "Nemotron was not called" in text
    assert "does not prove" in text
    assert "SIMULATED" not in text
    variation = next(e for e in after.observations if e.tool == "check_variation")
    assert variation.data["regulatory_alarm_threshold_applied"] is False
    assert "demonstration_threshold_ntu" not in variation.data
    assert "Requested, not performed" in text


def test_model_selects_river_tool_order_and_only_receives_causal_original_evidence(tmp_path):
    directory, _ = prepare(tmp_path)
    (directory / "evaluation.json").write_text("EVALUATOR_SECRET NOT JSON")
    order = list(reversed(RIVER_TOOLS))
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        text = request.content.decode()
        assert "EVALUATOR_SECRET" not in text
        assert "qc_status" not in text and "corrected_value" not in text
        assert "2024-04-03T00:15:00Z" not in text
        assert "synthetic-test-key" not in text
        assert payload["max_tokens"] == 2048
        index = len(requests) - 1
        if index < 5:
            return httpx.Response(200, json=response([call(order[index], identifier=f"c-{index}")]))
        final = json.loads(payload["messages"][-1]["content"])
        assert len(payload["messages"]) == 2
        assert len(final["completed_checks"]) == 5
        assert payload["tool_choice"]["function"]["name"] == "submit_report"
        assert len(payload["tools"]) == 1
        draft = {"conclusion": "insufficient_evidence",
                 "possible_causes": final["report_constraints"]["required_possible_causes"]}
        return httpx.Response(200, json=response([call("submit_report", draft, "final")]))

    client = client_for(handler)
    try:
        report = investigate_river(directory, "2024-04-03T00:00:00Z", client)
    finally:
        client.close()
    assert len(requests) == 6
    assert "completed_checks" not in requests[0]["messages"][-1]["content"]
    assert report.investigation_status == "complete"
    assert report.investigation_mode == "nebius_model"
    assert report.checks_performed == order
    assert all(a.status == "performed" for a in report.tool_attempts)
    assert "offline reference policy" not in " ".join(report.uncertainty)


def test_before_visit_requests_do_not_leak_future_notes_or_calibration_events(tmp_path):
    directory, _ = prepare(tmp_path)
    requests = []

    def handler(request):
        requests.append(request.content.decode())
        return httpx.Response(200, json=response([call(name, identifier=name) for name in RIVER_TOOLS]))

    client = client_for(handler)
    try:
        report = investigate_river(directory, "2024-04-02T22:15:00Z", client, max_rounds=2)
    finally:
        client.close()
    combined = " ".join(requests)
    assert "Recorded drift before the visit" not in combined
    assert "Sensor cleaned." not in combined
    assert "2024-04-03T00:00:00Z" not in combined
    assert "Two-point standard procedure" in combined
    assert report.investigation_status == "incomplete"


def test_provider_timeout_preserves_executed_checks_and_never_falls_back(tmp_path):
    directory, _ = prepare(tmp_path)
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json=response([call("check_freshness")]))
        raise httpx.ReadTimeout("unsafe-provider-detail", request=request)

    client = client_for(handler)
    try:
        report = investigate_river(directory, "2024-04-03T00:00:00Z", client)
    finally:
        client.close()
    assert len(requests) == 2
    assert report.checks_performed == ["check_freshness"]
    assert report.investigation_status == "incomplete"
    assert report.investigation_mode == "nebius_model"
    assert "timed out" in report.uncertainty[-1]
    assert "unsafe-provider-detail" not in report.model_dump_json()


@pytest.mark.parametrize("invalid", ["forged_citation", "proven_cause", "unapproved_tool", "file_arguments"])
def test_invalid_model_actions_remain_incomplete_and_are_recorded(tmp_path, invalid):
    directory, _ = prepare(tmp_path)
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if invalid == "unapproved_tool":
            calls = [call("clear_alarm", identifier=str(len(requests)))]
        elif invalid == "file_arguments":
            calls = [call("check_freshness", {"path": "evaluation.json"}, str(len(requests)))]
        elif len(requests) == 1:
            calls = [call(name, identifier=name) for name in RIVER_TOOLS]
        else:
            draft = {"conclusion": "insufficient_evidence", "possible_causes":
                json.loads(payload["messages"][-1]["content"])["report_constraints"]["required_possible_causes"]}
            if invalid == "forged_citation":
                draft["possible_causes"][0]["relevant_evidence_ids"] = ["R99"]
            else:
                draft["conclusion"] = "sensor_problem"
            calls = [call("submit_report", draft, "bad-final")]
        return httpx.Response(200, json=response(calls))

    client = client_for(handler)
    try:
        report = investigate_river(directory, "2024-04-03T00:00:00Z", client,
                                   max_rounds=2, max_tool_calls=6)
    finally:
        client.close()
    assert report.investigation_status == "incomplete"
    assert report.conclusion == "insufficient_evidence"
    assert any(a.status == "rejected" for a in report.tool_attempts)


def test_report_saving_preserves_real_provenance_and_requested_actions(tmp_path):
    directory, _ = prepare(tmp_path)
    report = investigate_river(directory, "2024-04-03T00:00:00Z")
    json_path, markdown_path = save_river_report(report, tmp_path / "reports")
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_path.name.startswith("RIVER-udall-")
    assert saved["source"] == "REAL_RIVER_SENSOR_DATA"
    assert saved["source_url"].startswith("https://www.hydroshare.org/")
    assert all(a["status"] == "requested_not_performed" for a in saved["suggested_operator_actions"])
    assert "complete executed check results" in markdown_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("change", ["source", "site", "units", "interval"])
def test_bad_prepared_metadata_stops_before_any_model_request(tmp_path, change):
    directory, _ = prepare(tmp_path)
    path = directory / "observations.json"
    observations = json.loads(path.read_text(encoding="utf-8"))
    if change == "source":
        observations["source"] = "SIMULATED"
    elif change == "site":
        observations["site"] = "different-site"
    elif change == "interval":
        observations["expected_interval_seconds"] = 0
    else:
        observations["records"][0]["units"] = "other-units"
    path.write_text(json.dumps(observations), encoding="utf-8")
    with pytest.raises(DatasetError):
        investigate_river(directory, "2024-04-03T00:00:00Z")


def test_cli_offline_river_command_never_constructs_hosted_client(tmp_path, monkeypatch):
    import water_diagnostics.__main__ as cli

    directory, _ = prepare(tmp_path)
    destination = tmp_path / "reports"
    monkeypatch.setattr("sys.argv", ["water_diagnostics", "run-river", "--input", str(directory),
                                     "--output", str(destination)])
    monkeypatch.setattr(cli, "NebiusClient", lambda *args: pytest.fail("Offline mode must not use a client"))
    assert cli.main() == 0
    assert len(list(destination.glob("RIVER-*.json"))) == 1
