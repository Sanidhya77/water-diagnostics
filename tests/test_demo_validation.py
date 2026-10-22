"""Targeted validation must preserve failures, separate truth and avoid repeat bills."""

import json

import httpx
import pytest

import water_diagnostics.demo_validation as validation
from water_diagnostics.config import DEFAULT_MODEL, Settings
from water_diagnostics.incident_reports.reporting import save_report
from water_diagnostics.incident_reports.schema import IncidentReport
from water_diagnostics.investigator import investigate_offline
from water_diagnostics.model_client.budget import BudgetError
from water_diagnostics.model_client.nebius import NebiusClient
from water_diagnostics.simulator import make_replay


def save_hosted(root, case="frozen", change=None):
    replay = make_replay(case)
    report = investigate_offline(replay)
    report.investigation_mode = "nebius_model"
    report.model = DEFAULT_MODEL
    # Rebuild application-owned fields for hosted mode, without calling a model.
    report.uncertainty = [u for u in report.uncertainty if "offline reference policy" not in u]
    if change:
        change(report)
    path, _ = save_report(report, root / "reports", replay.incident_id + "-nebius")
    return path


def mock_factory(requests, failure=False):
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if failure:
            raise httpx.ReadTimeout("synthetic failure", request=request)
        if len(payload["tools"]) > 1:
            calls = [{"id": name, "type": "function", "function": {"name": name, "arguments": "{}"}}
                     for name in validation.TOOL_DESCRIPTIONS]
        else:
            constraints = json.loads(payload["messages"][-1]["content"])["report_constraints"]
            draft = {"conclusion": constraints["allowed_conclusions"][0]}
            calls = [{"id": "final", "type": "function", "function": {"name": "submit_report", "arguments": json.dumps(draft)}}]
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": calls}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}})

    return lambda settings, guard: NebiusClient(settings, httpx.MockTransport(handler), budget=guard)


def test_saved_mode_scores_available_report_without_loading_key_or_client(tmp_path, monkeypatch):
    save_hosted(tmp_path)
    monkeypatch.setattr(validation, "load_settings", lambda: pytest.fail("Saved mode requires no credentials"))
    summary = validation.validate_demo(tmp_path, progress=None)
    assert summary["baseline_passed"] == 3
    assert summary["hosted_passed"] == summary["hosted_evaluated"] == 1
    assert summary["new_requests"] == 0
    assert summary["results"][0]["hosted"]["elapsed_seconds"] is None
    assert summary["results"][1]["hosted"]["origin"] == "not_run"


def test_only_missing_cases_are_called_and_repeated_validation_reuses_reports(tmp_path):
    original = save_hosted(tmp_path)
    before = original.read_bytes()
    requests = []
    kwargs = dict(settings=Settings(nebius_api_key="synthetic-key"), client_factory=mock_factory(requests), progress=None)
    result = validation.validate_demo(tmp_path, "nebius", **kwargs)
    assert result["hosted_passed"] == result["hosted_evaluated"] == 3
    assert result["new_requests"] == len(requests) == 4  # Two mocked tool rounds per missing case.
    assert [r["hosted"]["origin"] for r in result["results"]] == ["saved", "new", "new"]
    assert original.read_bytes() == before
    assert result["new_conservative_accounted_usd"] <= 0.04
    assert all('"expected"' not in json.dumps(p) and '"case"' not in json.dumps(p) and '"seed"' not in json.dumps(p) for p in requests)
    again = validation.validate_demo(tmp_path, "nebius", **kwargs)
    assert again["new_requests"] == 0 and len(requests) == 4
    snapshots = list((tmp_path / "reports" / "demo-validation" / "history").glob("*.json"))
    assert len(snapshots) == 2
    assert any(json.loads(p.read_text())["new_requests"] == 4 for p in snapshots)


@pytest.mark.parametrize("change", [
    lambda r: r.observations[0].data.update(fresh=False),
    lambda r: r.possible_causes[0].supporting_evidence_ids.append("E99"),
    lambda r: setattr(r.suggested_operator_actions[0], "action", "Calibration has been performed"),
])
def test_tampered_saved_report_blocks_new_spending(tmp_path, change):
    save_hosted(tmp_path, change=change)
    result = validation.validate_demo(tmp_path, "nebius",
        client_factory=lambda *a: pytest.fail("Invalid cache must not trigger paid replacement"), progress=None)
    assert result["new_requests"] == 0
    assert not result["results"][0]["hosted"]["passed"]
    assert result["results"][0]["hosted"]["issues"]


def test_timeout_is_saved_and_never_automatically_retried(tmp_path):
    save_hosted(tmp_path)
    requests = []
    kwargs = dict(settings=Settings(nebius_api_key="synthetic-key"), client_factory=mock_factory(requests, failure=True), progress=None)
    first = validation.validate_demo(tmp_path, "nebius", **kwargs)
    assert first["new_requests"] == 1 and first["new_conservative_accounted_usd"] > 0
    assert first["results"][1]["hosted"]["status"] == "incomplete"
    assert first["results"][2]["hosted"]["origin"] == "not_run"
    again = validation.validate_demo(tmp_path, "nebius", **kwargs)
    assert again["new_requests"] == 0 and len(requests) == 1


def test_session_guard_and_active_run_lock_block_before_http(tmp_path, monkeypatch):
    save_hosted(tmp_path)
    monkeypatch.setattr(validation, "SESSION_CAP_USD", 0.00000001)
    requests = []
    result = validation.validate_demo(tmp_path, "nebius", settings=Settings(nebius_api_key="synthetic"),
        client_factory=mock_factory(requests), progress=None)
    assert result["new_requests"] == 0 and requests == []
    output = tmp_path / "reports" / "demo-validation"
    (output / ".validation.lock").touch()
    with pytest.raises(BudgetError, match="already running"):
        validation.validate_demo(tmp_path, "nebius", progress=None)


def test_latest_explicit_recovery_is_used_even_when_it_failed(tmp_path):
    save_hosted(tmp_path)
    save_hosted(tmp_path, "insufficient")
    original = save_hosted(tmp_path, "process_change")
    original_bytes = original.read_bytes()
    report = IncidentReport.model_validate_json(original.read_text(encoding="utf-8"))
    failed = report.model_copy(update={"investigation_status": "incomplete"})
    output = tmp_path / "reports" / "demo-validation"
    stem = make_replay("process_change").incident_id + "-nebius"
    earlier, _ = save_report(failed, output, stem + "-retry")
    fixed, _ = save_report(report, output, stem + "-retry-retry")
    result = validation.validate_demo(tmp_path, progress=None)
    assert result["hosted_passed"] == 3
    assert result["results"][1]["hosted"]["report"] == str(fixed.resolve())
    assert original.read_bytes() == original_bytes and earlier.exists()

    latest, _ = save_report(failed, output, stem + "-retry-retry-retry")
    save_report(report, output, stem + "-retry-retry-retry-passed-copy")
    result = validation.validate_demo(tmp_path, "nebius", progress=None,
        client_factory=lambda *args: pytest.fail("A saved failure must never trigger an automatic retry"))
    assert result["hosted_passed"] == 2 and result["new_requests"] == 0
    assert result["results"][1]["hosted"]["report"] == str(latest.resolve())
    assert not result["results"][1]["hosted"]["passed"]
