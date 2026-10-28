"""A free hosted demo must not reach paid providers or rely on durable disk."""

import json
from threading import Thread
from time import monotonic, sleep

import httpx
import pytest

from test_river_data import prepare
import water_diagnostics.dashboard as dashboard


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    directory, _ = prepare(tmp_path)
    monkeypatch.setattr(dashboard, "load_settings", lambda: pytest.fail("Public demo must not load provider credentials"))
    monkeypatch.setattr(dashboard, "NebiusClient", lambda *a, **k: pytest.fail("No paid client allowed"))
    app = dashboard.Dashboard(tmp_path, public_demo=True)
    app.river_directory = directory
    app.guidance.lookup = lambda *a, **k: pytest.fail("No paid lookup allowed")
    server = dashboard.make_server(0, app, public_origin="https://demo.example")
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
                      headers={"Host": "demo.example", "Origin": "https://demo.example"}) as client:
        yield app, client
    server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_public_host_origin_health_and_paid_guards(hosted):
    app, client = hosted
    assert client.get("/health").json() == {"status": "ready", "public_demo": True}
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/investigate", json={}, headers={"Origin": "http://demo.example"}).status_code == 403
    for path, payload in [("/api/investigate", {"mode": "nebius"}), ("/api/guidance", {})]:
        assert client.post(path, json=payload).status_code == 400
    assert not app.jobs
    assert client.get("/api/budget").json()["requests"] == 0
    assert not (app.root / "reports/nebius-usage.json").exists()
    data = client.get("/api/replay").json()
    assert data["capabilities"] == {"public_demo": True, "live_inference": False, "reference_lookup": False}


def test_public_local_run_and_download_need_no_disk_persistence(hosted):
    app, client = hosted
    started = client.post("/api/investigate", json={"mode": "offline"})
    assert started.status_code == 202
    deadline = monotonic() + 4
    while True:
        job = client.get("/api/job", params={"id": started.json()["id"]}).json()
        if job["status"] != "running": break
        assert monotonic() < deadline
        sleep(0.01)
    assert job["status"] == "finished" and job["result"]["status"] == "complete"
    assert "Nemotron was not called" in client.get("/api/download").text
    assert not (app.root / "reports/ui").exists()
    result = client.post("/api/recovery-demo", json={"case": "collector_recovers"})
    assert result.status_code == 200
    assert "SIMULATED_RECOVERY" in client.get(result.json()["download_url"]).text
    assert not (app.root / "reports/recovery").exists()


def test_external_binding_cannot_expose_local_paid_mode():
    with pytest.raises(ValueError, match="External binding"):
        dashboard.make_server(0, bind_address="0.0.0.0")
