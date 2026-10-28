"""Local HTTP interface isolation and free investigation flow; no inference requests."""

import json
from threading import Event, Thread
from time import monotonic, sleep

import httpx
import pytest

from test_river_data import prepare
import water_diagnostics.dashboard as dashboard
from water_diagnostics.config import Settings
from water_diagnostics.guidance import GuidanceService
from water_diagnostics.model_client.nebius import NebiusClient
from water_diagnostics.river_investigator import RIVER_TOOLS


@pytest.fixture
def interface(tmp_path, monkeypatch):
    directory, _ = prepare(tmp_path)
    (directory / "evaluation.json").write_text("EVALUATOR_SECRET")
    (tmp_path / ".env").write_text("NEBIUS_API_KEY=do-not-expose-this-sentinel")
    app = dashboard.Dashboard(tmp_path)
    app.river_directory = directory
    monkeypatch.setattr(dashboard, "NebiusClient", lambda *args, **kwargs: pytest.fail("No paid client should be created by this test"))
    server = dashboard.make_server(0, app)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=address, trust_env=False) as client:
        yield app, server, client, address
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_replay_reading_excludes_future_notes_points_and_evaluator_answers(interface):
    _, _, client, _ = interface
    before = client.get("/api/replay", params={"source": "river", "at": "2024-04-02T22:00:00Z"})
    assert before.status_code == 200
    assert before.json()["summary"]["latest"] == 10.0
    assert before.json()["events"] == []
    assert len(before.json()["points"]) == 2
    after = client.get("/api/replay", params={"source": "river", "at": "2024-04-03T00:00:00Z"})
    assert len(after.json()["events"]) == 1
    assert after.json()["summary"]["latest"] == 1.0
    assert "2024-04-03T00:15:00Z" not in after.text
    assert "EVALUATOR_SECRET" not in after.text
    assert "do-not-expose" not in after.text
    assert "data_archive" not in after.text


def test_only_explicit_static_files_are_served_without_credentials(interface):
    _, server, client, _ = interface
    assert server.server_address[0] == "127.0.0.1"
    for path in ("/", "/style.css", "/app.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert "do-not-expose" not in response.text
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    for path in ("/.env", "/reports/", "/data/river/observations.json", "/api/settings"):
        assert client.get(path).status_code == 404
    for path in ("/plex-regular.ttf", "/plex-semibold.ttf"):
        response = client.get(path)
        assert response.status_code == 200 and response.headers["Content-Type"] == "font/ttf"
        assert response.content[:4] == b"\x00\x01\x00\x00"
    assert "SIL OPEN FONT LICENSE" in client.get("/OFL-Plex.txt").text
    assert client.get("/api/replay", params={"path": ".env"}).status_code == 400


def test_host_and_origin_checks_prevent_unintended_paid_requests(interface):
    app, _, client, _ = interface
    payload = {"source": "river", "mode": "nebius"}
    assert client.get("/", headers={"Host": "other.example"}).status_code == 403
    assert client.post("/api/investigate", json=payload).status_code == 403
    assert client.post("/api/investigate", json=payload, headers={"Origin": "https://other.example"}).status_code == 403
    assert not app.jobs


def test_free_local_run_has_trace_report_and_download_without_overwriting_saved_files(interface):
    app, _, client, address = interface
    payload = {"source": "river", "at": "2024-04-03T00:00:00Z", "mode": "offline"}
    started = client.post("/api/investigate", json=payload, headers={"Origin": address})
    assert started.status_code == 202
    identifier = started.json()["id"]
    deadline = monotonic() + 4
    while True:
        job = client.get("/api/job", params={"id": identifier}).json()
        if job["status"] != "running":
            break
        assert monotonic() < deadline
        sleep(0.01)
    assert job["status"] == "finished"
    assert len(job["events"]) == 5
    assert job["result"]["mode"] == "offline_reference_policy"
    assert job["result"]["status"] == "complete"
    assert job["result"]["conclusion"] == "insufficient_evidence"
    assert len(job["result"]["observations"]) == 5
    downloaded = client.get("/api/download", params=payload)
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers["Content-Disposition"]
    assert "REAL_RIVER_SENSOR_DATA" in downloaded.text
    assert "Nemotron was not called" in downloaded.text
    assert "EVALUATOR_SECRET" not in downloaded.text
    assert list((app.root / "reports" / "ui" / identifier).glob("*.json"))
    assert not list((app.root / "reports").glob("RIVER-*.json"))
    assert client.get("/api/budget").json()["requests"] == 0


def test_simulated_data_has_distinct_source_and_demonstration_threshold(interface):
    _, _, client, _ = interface
    data = client.get("/api/replay", params={"source": "simulated", "case": "frozen"}).json()
    assert data["summary"]["source_label"] == "Simulated filter outlet"
    assert data["summary"]["threshold"] == 0.3
    assert len(data["points"]) == 31


def test_curated_demo_report_is_preferred_to_legacy_saved_copy(interface):
    app, _, _, _ = interface
    from water_diagnostics.river_investigator import investigate_river, save_river_report
    original = investigate_river(app.river_directory, "2024-04-03T00:00:00Z")
    save_river_report(original, app.root / "reports")
    curated = original.model_copy(update={"uncertainty": ["Curated source copy"]})
    save_river_report(curated, app.root / "demo_reports")
    selected = app.cached_report(dashboard.selection({"mode": "offline"}))
    assert selected.uncertainty == ["Curated source copy"]


def test_replay_and_mode_validation_rejects_unsupported_inputs(interface):
    _, _, client, address = interface
    for payload in ({"source": "other"}, {"mode": "no-guard"}, {"case": "other"},
                    {"at": "2025-01-01T00:00:00Z"}, {"path": ".env"}, []):
        response = client.post("/api/investigate", json=payload, headers={"Origin": address})
        assert response.status_code == 400
    assert client.get("/api/download", params={"source": "river", "mode": "nebius"}).status_code == 404


def test_additional_week_uses_its_own_inputs_and_rejects_paths(interface):
    app, _, client, _ = interface
    from datetime import timedelta
    from water_diagnostics.river_data import utc_time
    target = app.root / "data/river/udall-2024-04-08"
    target.mkdir(parents=True)
    for name in ("observations.json", "context.json"):
        data = json.loads((app.river_directory / name).read_text(encoding="utf-8"))
        if name == "observations.json":
            for key in ("start_utc", "end_exclusive_utc"):
                data[key] = (utc_time(data[key]) + timedelta(days=7)).isoformat()
            for row in data["records"]:
                row["timestamp"] = (utc_time(row["timestamp"]) + timedelta(days=7)).isoformat()
        else:
            for row in data["visit_records"]:
                for key in ("visit_time_utc", "assumed_available_at_utc"):
                    row[key] = (utc_time(row[key]) + timedelta(days=7)).isoformat()
        (target / name).write_text(json.dumps(data), encoding="utf-8")
    (target / "evaluation.json").write_text("SECOND_WEEK_EVALUATOR_SECRET")
    response = client.get("/api/replay", params={"dataset": "udall-2024-04-08", "at": "2024-04-10T00:00:00Z"})
    assert response.status_code == 200
    assert response.json()["summary"]["latest"] == 1.0
    assert "SECOND_WEEK_EVALUATOR_SECRET" not in response.text
    assert client.get("/api/replay", params={"dataset": "../../.env"}).status_code == 400
    assert client.get("/api/replay", params={"dataset": "udall-2024-04-08", "at": "2024-04-03T00:00:00Z"}).status_code == 400


def test_guidance_requires_explicit_same_origin_request_and_valid_replay(interface):
    app, _, client, address = interface
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"usage": {"credits": 1}, "results": [
            {"title": "Monitoring guidance", "url": "https://www.usgs.gov/monitoring", "content": "Public background."}]})

    app.guidance = GuidanceService(app.root / "reports" / "tavily-guidance.json",
        Settings(tavily_api_key="synthetic-tavily-key"), httpx.MockTransport(handler))
    payload = {"source": "river", "at": "2024-04-03T00:00:00Z"}
    assert client.get("/api/replay", params=payload).json()["guidance"] is None
    assert client.post("/api/guidance", json=payload).status_code == 403
    assert client.post("/api/guidance", json=payload, headers={"Origin": "https://other.example"}).status_code == 403
    assert client.post("/api/guidance", json={**payload, "at": "2025-01-01T00:00:00Z"}, headers={"Origin": address}).status_code == 400
    assert not sent
    result = client.post("/api/guidance", json=payload, headers={"Origin": address})
    assert result.status_code == 200 and result.json()["reported_credits"] == 1
    replay = client.get("/api/replay", params=payload).json()
    assert replay["guidance"]["cached"]
    assert replay["guidance"]["documents"][0]["reference_id"] == "D01"
    assert "synthetic-tavily-key" not in json.dumps(replay)
    assert len(sent) == 1 and app.budget()["requests"] == 0


def test_concurrent_investigations_are_blocked(interface, monkeypatch):
    app, _, client, address = interface
    entered, release = Event(), Event()

    def blocked_run(*args):
        entered.set()
        release.wait(3)

    monkeypatch.setattr(app, "_run", blocked_run)
    payload = {"source": "simulated", "mode": "offline"}
    try:
        assert client.post("/api/investigate", json=payload, headers={"Origin": address}).status_code == 202
        assert entered.wait(1)
        second = client.post("/api/investigate", json=payload, headers={"Origin": address})
        assert second.status_code == 400
        assert "already running" in second.json()["error"]
    finally:
        release.set()


def test_hosted_button_uses_existing_cost_guard_and_returns_model_report_without_live_api(interface, monkeypatch):
    app, _, client, address = interface
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            calls = [{"id": name, "type": "function", "function": {"name": name, "arguments": "{}"}}
                     for name in RIVER_TOOLS]
        else:
            constraints = json.loads(payload["messages"][-1]["content"])["report_constraints"]
            draft = {"conclusion": "insufficient_evidence", "possible_causes": constraints["required_possible_causes"]}
            calls = [{"id": "final", "type": "function", "function": {"name": "submit_report", "arguments": json.dumps(draft)}}]
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": calls}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}})

    def mocked_client(settings, budget):
        assert budget.project_cap == 5.0 and budget.run_cap == 0.02
        assert budget.path == app.root / "reports" / "nebius-usage.json"
        return NebiusClient(settings, transport=httpx.MockTransport(handler), budget=budget)

    monkeypatch.setattr(dashboard, "load_settings", lambda: Settings(nebius_api_key="synthetic-key"))
    monkeypatch.setattr(dashboard, "NebiusClient", mocked_client)
    response = client.post("/api/investigate", json={"source": "river", "mode": "nebius"}, headers={"Origin": address})
    assert response.status_code == 202
    deadline = monotonic() + 4
    while True:
        job = client.get("/api/job", params={"id": response.json()["id"]}).json()
        if job["status"] != "running":
            break
        assert monotonic() < deadline
        sleep(0.01)
    assert job["status"] == "finished"
    assert job["result"]["mode"] == "nebius_model"
    assert job["result"]["status"] == "complete"
    assert "synthetic-key" not in json.dumps(job)
    assert len(requests) == 2
    assert app.budget()["requests_with_usage"] == 2


@pytest.mark.parametrize("case,outcome", [("collector_recovers", "telemetry_restored"), ("collector_stays_offline", "escalated")])
def test_recovery_simulation_has_separate_report_audit_download_and_zero_paid_calls(interface, case, outcome):
    app, _, client, address = interface
    result = client.post("/api/recovery-demo", json={"case": case}, headers={"Origin": address})
    assert result.status_code == 200
    data = result.json()
    report = data["report"]
    assert report["source"] == "SIMULATED_RECOVERY" and report["outcome"] == outcome
    assert report["attempts"] == 1 and report["action_acknowledged"] is True
    assert report["diagnostic_origin"] == "offline_reference_policy"
    assert app.latest == {} and app.jobs == {} and app.active is None
    assert (app.root / "reports" / "recovery" / (report["run_id"] + ".json")).is_file()
    downloaded = client.get(data["download_url"])
    assert downloaded.status_code == 200 and "attachment" in downloaded.headers["Content-Disposition"]
    assert "SIMULATED_RECOVERY" in downloaded.text and "no new" in downloaded.text.lower()
    assert "EVALUATOR_SECRET" not in downloaded.text and "do-not-expose" not in json.dumps(data)
    assert app.budget()["requests"] == 0
    if outcome == "escalated":
        assert report["escalation"]["delivery_status"] == "recorded_not_sent"


@pytest.mark.parametrize("payload", [[], {}, {"case": []}, {"case": "river"},
    {"case": "collector_recovers", "preapproved": True},
    {"case": "collector_recovers", "action": "clear_alarm"},
    {"case": "collector_recovers", "path": ".env"}])
def test_recovery_endpoint_accepts_only_server_owned_simulation_names(interface, payload):
    app, _, client, address = interface
    response = client.post("/api/recovery-demo", json=payload, headers={"Origin": address})
    assert response.status_code == 400 and app.recoveries == {} and app.active is None


def test_recovery_origin_and_concurrent_run_guards_precede_execution(interface):
    app, _, client, address = interface
    payload = {"case": "collector_recovers"}
    assert client.post("/api/recovery-demo", json=payload).status_code == 403
    assert client.post("/api/recovery-demo", json=payload, headers={"Origin": "https://other.example"}).status_code == 403
    app.active = "existing-investigation"
    try:
        assert client.post("/api/recovery-demo", json=payload, headers={"Origin": address}).status_code == 400
        assert app.active == "existing-investigation" and app.recoveries == {}
    finally:
        app.active = None
    assert client.get("/api/recovery-download", params={"id": "../../.env"}).status_code == 404


def test_recovery_save_failure_releases_run_lock_without_exposing_paths(interface, monkeypatch):
    app, _, client, address = interface

    def unavailable(*args):
        raise OSError("SECRET_PRIVATE_PATH")

    monkeypatch.setattr(dashboard, "save_recovery", unavailable)
    result = client.post("/api/recovery-demo", json={"case": "collector_recovers"}, headers={"Origin": address})
    assert result.status_code == 503 and "SECRET_PRIVATE_PATH" not in result.text
    assert app.active is None and app.recoveries == {}
