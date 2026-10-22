"""Mocked HTTP and agent loop verification. No live requests or real keys."""

import json

import httpx
import pytest

from water_diagnostics.config import Settings
from water_diagnostics.diagnostic_tools.checks import TOOL_DESCRIPTIONS
from water_diagnostics.incident_reports.reporting import reference_draft, validate_draft
from water_diagnostics.incident_reports.schema import Cause, CauseDraft, ReportDraft
from water_diagnostics.investigator import investigate_nebius, investigate_offline
from water_diagnostics.model_client.nebius import ModelClientError, NebiusClient
from water_diagnostics.simulator import make_replay


def call(name, arguments=None, identifier="test-call"):
    return {"id": identifier, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {}),
    }}


def response(calls):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": calls,
        "reasoning_content": "Do not save this provider reasoning.",
    }}]}


def settings():
    return Settings(nebius_api_key="synthetic-test-key", nebius_base_url="https://unit.test/v1")


def test_hosted_protocol_executes_selected_tools_then_submits_grounded_report():
    requests = []
    # Deliberately a different order from the offline policy.
    order = ["check_related_measurements", "check_maintenance_context", "check_variation",
             "check_freshness", "check_device_status"]

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-test-key"
        assert payload["model"] == settings().nebius_model
        assert "synthetic-test-key" not in request.content.decode()
        index = len(requests) - 1
        if index < len(order):
            return httpx.Response(200, json=response([call(order[index], identifier=f"call-{index}")]))
        result = json.loads(payload["messages"][-1]["content"])
        constraints = result["report_constraints"]
        assert not constraints["checks_still_required"]
        draft = {"conclusion": "process_change"}
        return httpx.Response(200, json=response([call("submit_report", draft, "final")]))

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        report = investigate_nebius(make_replay("process_change"), client)
    finally:
        client.close()
    assert len(requests) == 6
    assert report.conclusion == Cause.PROCESS
    assert report.investigation_status == "complete"
    assert report.investigation_mode == "nebius_model"
    assert report.checks_performed == order
    assert "synthetic-test-key" not in report.model_dump_json()
    assert "provider reasoning" not in report.model_dump_json()
    initial_context = json.loads(requests[0]["messages"][1]["content"])
    assert "case" not in initial_context and "expected" not in initial_context
    assert "samples" not in initial_context
    for payload in requests:
        assert "reasoning_content" not in json.dumps(payload)
    assert all(payload["max_tokens"] == 2048 for payload in requests[:-1])
    final = requests[-1]
    assert final["max_tokens"] == 4096
    assert [t["function"]["name"] for t in final["tools"]] == ["submit_report"]
    assert final["tool_choice"] == {"type": "function", "function": {"name": "submit_report"}}
    assert len(final["messages"]) == 2
    assert len(json.loads(final["messages"][-1]["content"])["completed_checks"]) == 5
    schema = final["tools"][0]["function"]["parameters"]
    assert set(schema["properties"]) == {"conclusion"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["conclusion"]["enum"] == ["process_change", "insufficient_evidence"]
    causes = {c.cause: c for c in report.possible_causes}
    assert set(causes) == {Cause.SENSOR, Cause.PROCESS}
    assert causes[Cause.SENSOR].conflicting_evidence_ids == ["E01"]
    assert causes[Cause.PROCESS].supporting_evidence_ids == ["E03", "E01"]


def test_http_errors_do_not_expose_provider_body_or_keys():
    client = NebiusClient(settings(), httpx.MockTransport(
        lambda request: httpx.Response(401, text="synthetic-test-key echoed by server")))
    try:
        with pytest.raises(ModelClientError) as error:
            client.ping()
        assert "HTTP 401" in str(error.value)
        assert "synthetic" not in str(error.value)
        assert "echoed" not in str(error.value)
    finally:
        client.close()


def test_missing_key_cannot_make_any_request():
    with pytest.raises(ModelClientError, match="key is missing"):
        NebiusClient(Settings())


def test_one_short_connection_request_omits_response_text():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
            "message": {"role": "assistant", "content": "OK"}}]})

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        assert client.ping() is None
    finally:
        client.close()
    assert len(requests) == 1
    assert requests[0]["max_tokens"] == 256


@pytest.mark.parametrize("body", [
    {"choices": []},
    {"choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": "partial"}}]},
])
def test_malformed_or_truncated_response_is_not_accepted(body):
    client = NebiusClient(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    try:
        with pytest.raises(ModelClientError):
            client.ping()
    finally:
        client.close()


def test_unapproved_tool_and_arguments_are_rejected_and_budget_is_bounded():
    counter = 0

    class InvalidModel:
        model = "mock-nemotron"

        def complete(self, messages, tools, max_tokens=4096):
            nonlocal counter
            counter += 1
            calls = [call("clear_alarm", identifier=f"bad-{counter}"),
                     call("check_freshness", {"path": ".env"}, f"args-{counter}")]
            return {"role": "assistant", "tool_calls": calls}

    report = investigate_nebius(make_replay("normal"), InvalidModel(), max_rounds=20, max_tool_calls=3)
    assert counter == 2
    assert len(report.tool_attempts) == 3
    assert all(a.status == "rejected" for a in report.tool_attempts)
    assert not report.observations
    assert report.conclusion == Cause.INSUFFICIENT
    assert report.investigation_status == "incomplete"
    assert not report.checks_performed


def test_fabricated_citations_and_unproven_conclusion_are_rejected():
    report = investigate_offline(make_replay("insufficient"))
    draft = reference_draft(report.observations)
    fabricated = draft.model_copy(update={"possible_causes": [CauseDraft(
        cause=Cause.SENSOR, supporting_evidence_ids=["E99"])]})
    with pytest.raises(ValueError):
        validate_draft(fabricated, report.observations)
    unproven = draft.model_copy(update={"conclusion": Cause.PROCESS})
    with pytest.raises(ValueError, match="lacks required"):
        validate_draft(unproven, report.observations)


def test_provider_failure_preserves_executed_evidence_without_offline_success():
    class FailingModel:
        model = "mock-nemotron"

        def complete(self, messages, tools, max_tokens=4096):
            if len(messages) == 2:
                return {"role": "assistant", "tool_calls": [call("check_freshness")]}
            raise ModelClientError("Nebius request failed or timed out.")

    report = investigate_nebius(make_replay("normal"), FailingModel())
    assert report.checks_performed == ["check_freshness"]
    assert report.investigation_status == "incomplete"
    assert report.conclusion == Cause.INSUFFICIENT
    assert report.investigation_mode == "nebius_model"
    assert "timed out" in " ".join(report.uncertainty)


def test_free_text_claims_are_not_accepted_as_a_report():
    class TextModel:
        model = "mock-nemotron"

        def complete(self, messages, tools, max_tokens=4096):
            return {"role": "assistant", "content": "Water is safe. A physical test was completed."}

    report = investigate_nebius(make_replay("normal"), TextModel())
    assert report.investigation_status == "incomplete"
    assert "Water is safe" not in report.model_dump_json()
    assert all(a.status == "requested_not_performed" for a in report.suggested_operator_actions)


@pytest.mark.parametrize("exception,expected", [
    (httpx.ReadTimeout, "timed out"),
    (httpx.ConnectError, "connection failed"),
])
def test_timeout_and_connection_failures_are_distinct_safe_and_never_retried(exception, expected):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.extensions["timeout"]["read"] == 90.0
        assert request.extensions["timeout"]["connect"] == 10.0
        raise exception("synthetic-test-key in unsafe provider details", request=request)

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        with pytest.raises(ModelClientError) as error:
            client.ping()
        assert expected in str(error.value)
        assert "synthetic" not in str(error.value)
        assert "No automatic retry" in str(error.value)
        assert len(requests) == 1
    finally:
        client.close()


def saved_incomplete_report():
    return investigate_offline(make_replay("frozen")).model_copy(update={
        "investigation_mode": "nebius_model", "investigation_status": "incomplete",
        "conclusion": Cause.INSUFFICIENT, "uncertainty": ["Old API failure; not diagnostic evidence."],
    })


def test_resume_reuses_validated_evidence_and_spends_only_one_report_request():
    previous = saved_incomplete_report()
    before = previous.model_dump_json()
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        data = json.loads(payload["messages"][-1]["content"])
        assert data["completed_checks"] == [e.model_dump(mode="json") for e in previous.observations]
        assert "Old API failure" not in request.content.decode()
        assert "offline_reference_policy" not in request.content.decode()
        assert payload["tool_choice"]["function"]["name"] == "submit_report"
        assert payload["max_tokens"] == 4096
        draft = {"conclusion": "sensor_problem"}
        return httpx.Response(200, json=response([call("submit_report", draft)]))

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        report = investigate_nebius(make_replay("frozen"), client, resume_report=previous)
    finally:
        client.close()
    assert len(requests) == 1
    assert report.investigation_status == "complete"
    assert report.conclusion == Cause.SENSOR
    assert report.observations == previous.observations
    assert previous.model_dump_json() == before


@pytest.mark.parametrize("corruption", ["different_case", "changed_value", "missing_check", "forged_execution"])
def test_resume_rejects_mismatched_or_edited_evidence_before_any_request(corruption):
    previous = saved_incomplete_report()
    replay = make_replay("frozen")
    if corruption == "different_case":
        replay = make_replay("normal")
    elif corruption == "changed_value":
        previous.observations[0].data["sample_count"] = 999
    elif corruption == "missing_check":
        previous.observations.pop()
    else:
        previous.tool_attempts.pop()

    class NoRequest:
        model = "not-called"

        def complete(self, *args, **kwargs):
            pytest.fail("Invalid saved evidence must not trigger a paid request")

    with pytest.raises(ModelClientError):
        investigate_nebius(replay, NoRequest(), resume_report=previous)


def test_resume_failure_remains_incomplete_with_one_attempt_and_retained_evidence():
    previous = saved_incomplete_report()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "length",
            "message": {"role": "assistant", "content": "partial"}}]})

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        report = investigate_nebius(make_replay("frozen"), client, resume_report=previous)
    finally:
        client.close()
    assert len(requests) == 1
    assert report.investigation_status == "incomplete"
    assert report.conclusion == Cause.INSUFFICIENT
    assert report.observations == previous.observations
    assert "token limit" in report.uncertainty[-1]


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("case,conclusion", [
    ("process_change", "process_change"),
    ("process_change", "insufficient_evidence"),
    ("insufficient", "insufficient_evidence"),
])
def test_conclusion_only_submission_retains_competing_causes_and_exact_citations(case, conclusion, seed):
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(payload["tools"]) > 1:
            calls = [call(name, identifier=name) for name in TOOL_DESCRIPTIONS]
        else:
            calls = [call("submit_report", {"conclusion": conclusion}, "final")]
        return httpx.Response(200, json=response(calls))

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        report = investigate_nebius(make_replay(case, seed), client, max_rounds=2)
    finally:
        client.close()
    assert len(requests) == 2
    assert report.investigation_status == "complete"
    assert report.conclusion.value == conclusion  # Never replace a cautious model judgment with a policy answer.
    causes = {cause.cause: cause for cause in report.possible_causes}
    assert set(causes) == {Cause.SENSOR, Cause.PROCESS}
    assert causes[Cause.SENSOR].supporting_evidence_ids == ["E02"]
    assert causes[Cause.SENSOR].conflicting_evidence_ids == (["E05"] if case == "process_change" else [])
    assert causes[Cause.PROCESS].supporting_evidence_ids == (["E02", "E05"] if case == "process_change" else ["E02"])
    assert causes[Cause.PROCESS].conflicting_evidence_ids == []
    assert len(report.observations) == len(report.checks_performed) == 5
    assert all(action.status == "requested_not_performed" for action in report.suggested_operator_actions)


@pytest.mark.parametrize("case,submission,reason", [
    ("insufficient", {"conclusion": "process_change"}, "lacks required"),
    ("process_change", {"conclusion": "process_change", "possible_causes": []}, "only one allowed conclusion"),
    ("process_change", {}, "only one allowed conclusion"),
])
def test_invalid_conclusion_or_attempt_to_override_alternatives_remains_incomplete(case, submission, reason):
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        calls = ([call(name, identifier=name) for name in TOOL_DESCRIPTIONS] if len(requests) == 1
                 else [call("submit_report", submission, "bad-final")])
        return httpx.Response(200, json=response(calls))

    client = NebiusClient(settings(), httpx.MockTransport(handler))
    try:
        report = investigate_nebius(make_replay(case), client, max_rounds=2)
    finally:
        client.close()
    assert len(requests) == 2
    assert report.investigation_status == "incomplete"
    assert report.conclusion == Cause.INSUFFICIENT
    assert len(report.observations) == 5
    assert report.tool_attempts[-1].status == "rejected"
    assert reason in report.tool_attempts[-1].reason
    assert reason in report.uncertainty[-1]


def test_cli_resume_preserves_existing_retry_before_loading_credentials(tmp_path, monkeypatch):
    import sys
    import water_diagnostics.__main__ as cli

    source = tmp_path / "saved.json"
    source.write_text(saved_incomplete_report().model_dump_json(), encoding="utf-8")
    existing = tmp_path / "saved-retry.md"
    existing.write_text("Earlier attempt must remain available", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["water_diagnostics", "run", "--case", "frozen", "--mode", "nebius",
                                    "--resume-report", str(source), "--output", str(tmp_path)])
    monkeypatch.setattr(cli, "load_settings", lambda: pytest.fail("Existing retry must block before credentials or inference"))
    assert cli.main() == 2
    assert existing.read_text(encoding="utf-8") == "Earlier attempt must remain available"
