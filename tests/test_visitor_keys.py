"""Visitor keys are isolated, temporary and never a route to owner credentials."""

from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from time import monotonic, sleep

import httpx
import pytest

import water_diagnostics.dashboard as dashboard
from test_river_data import prepare
from water_diagnostics.config import DEFAULT_BASE_URL, DEFAULT_MODEL
from water_diagnostics.model_client.budget import BudgetError
from water_diagnostics.model_client.nebius import NebiusClient
from water_diagnostics.visitor_keys import COOKIE_NAME, SESSION_SECONDS, VisitorSessions


FAKE_KEY = "visitor-test-key-not-a-real-credential"
PAYLOAD = {"max_tokens": 4096, "messages": []}


def test_expiry_disconnect_replacement_and_capacity():
    now = [0]
    sessions = VisitorSessions(clock=lambda: now[0], maximum=2)
    token = sessions.connect({"nebius_api_key": FAKE_KEY})
    session = sessions.get(token)
    assert FAKE_KEY not in repr(session)
    replacement = sessions.connect({"nebius_api_key": FAKE_KEY}, token)
    assert sessions.get(token) is None and session.revoked
    assert not session.settings.nebius_api_key.get_secret_value()
    sessions.connect({"nebius_api_key": FAKE_KEY})
    with pytest.raises(ValueError, match="full"):
        sessions.connect({"nebius_api_key": FAKE_KEY})
    sessions.disconnect(replacement)
    assert sessions.get(replacement) is None
    token = sessions.connect({"nebius_api_key": FAKE_KEY})
    expired = sessions.get(token)
    now[0] = SESSION_SECONDS
    sessions.expire()
    assert not sessions.sessions and expired.revoked
    assert not expired.settings.nebius_api_key.get_secret_value()
    with pytest.raises(BudgetError, match="expired"):
        expired.guard().reserve(DEFAULT_MODEL, PAYLOAD)


@pytest.mark.parametrize("values", [{}, [], {"nebius_api_key": "short"},
    {"nebius_api_key": FAKE_KEY + "\r\n"}, {"nebius_api_key": "a" * 513},
    {"nebius_api_key": FAKE_KEY, "endpoint": "https://other.example"}])
def test_invalid_keys_and_custom_endpoints_rejected(values):
    with pytest.raises(ValueError):
        VisitorSessions().connect(values)


def test_guard_keeps_unknown_usage_and_serializes_shared_connection():
    sessions = VisitorSessions()
    session = sessions.get(sessions.connect({"nebius_api_key": FAKE_KEY}))
    first = session.guard()
    identifier = first.reserve(DEFAULT_MODEL, PAYLOAD)
    reserved = first.summary()["conservative_accounted_usd"]
    first.record_usage(identifier, None)
    first.record_usage(identifier, {"prompt_tokens": True, "completion_tokens": 1})
    assert first.summary()["conservative_accounted_usd"] == reserved
    first.record_usage(identifier, {"prompt_tokens": 1, "completion_tokens": 1})
    assert first.summary()["conservative_accounted_usd"] == reserved
    assert first.summary()["requests_with_usage"] == 1
    with pytest.raises(BudgetError):
        first.reserve("other-model", PAYLOAD)
    with pytest.raises(BudgetError):
        first.reserve(DEFAULT_MODEL, {"max_tokens": True})

    def reserve_one(_):
        try:
            session.guard().reserve(DEFAULT_MODEL, PAYLOAD)
            return 1
        except BudgetError:
            return 0

    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = sum(pool.map(reserve_one, range(160)))
    summary = session.summary()
    assert 0 < allowed < 160
    assert summary["requests"] == allowed + 1
    assert summary["conservative_accounted_usd"] <= 0.25
    with pytest.raises(BudgetError, match="guard reached"):
        session.guard().reserve(DEFAULT_MODEL, PAYLOAD)


def test_run_cap_and_reported_overage_block_further_calls():
    sessions = VisitorSessions()
    session = sessions.get(sessions.connect({"nebius_api_key": FAKE_KEY}))
    guard = session.guard()
    for _ in range(9):
        guard.reserve(DEFAULT_MODEL, PAYLOAD)
    with pytest.raises(BudgetError, match="guard reached"):
        guard.reserve(DEFAULT_MODEL, PAYLOAD)
    other = session.guard()
    identifier = other.reserve(DEFAULT_MODEL, PAYLOAD)
    other.record_usage(identifier, {"prompt_tokens": 10_000_000, "completion_tokens": 0})
    assert other.summary()["conservative_accounted_usd"] > 0.25
    with pytest.raises(BudgetError):
        session.guard().reserve(DEFAULT_MODEL, PAYLOAD)


@pytest.fixture
def site(tmp_path, monkeypatch):
    directory, _ = prepare(tmp_path)
    monkeypatch.setattr(dashboard, "load_settings", lambda: pytest.fail("Never load owner's provider keys in public mode"))
    requests = []

    def provider(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}],
                                         "usage": {"prompt_tokens": 12, "completion_tokens": 1}})

    def client(settings, budget):
        assert settings.nebius_base_url == DEFAULT_BASE_URL and settings.nebius_model == DEFAULT_MODEL
        return NebiusClient(settings, transport=httpx.MockTransport(provider), budget=budget)

    original = dashboard.investigate_river

    def investigation(directory, at, client, progress):
        client.complete([{"role": "user", "content": "offline test"}], max_tokens=32)
        return original(directory, at, None, progress)

    monkeypatch.setattr(dashboard, "NebiusClient", client)
    monkeypatch.setattr(dashboard, "investigate_river", investigation)
    app = dashboard.Dashboard(tmp_path, public_demo=True)
    app.river_directory = directory
    server = dashboard.make_server(0, app, public_origin="https://demo.example")
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
                      headers={"Host": "demo.example", "Origin": "https://demo.example"}) as browser:
        yield app, browser, requests
    server.shutdown(); server.server_close(); thread.join(timeout=2)
    assert not app.visitors.sessions


def test_key_cookie_is_private_and_required_for_every_paid_run(site):
    app, browser, calls = site
    assert not browser.get("/api/key-session").json()["connected"]
    assert browser.post("/api/investigate", json={"mode": "nebius"}).status_code == 400
    response = browser.post("/api/key-session", json={"nebius_api_key": FAKE_KEY})
    assert response.status_code == 200 and not calls  # Connecting isn't a provider request.
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", "Max-Age=1800"))
    assert FAKE_KEY not in response.text + cookie
    assert response.headers["cache-control"] == "no-store"
    # This test server is HTTP with proxy headers; inject the secure cookie
    # explicitly. Real browsers send it only on the public HTTPS origin.
    browser.headers["Cookie"] = cookie.split(";", 1)[0]
    status = browser.get("/api/key-session")
    assert status.json()["connected"] and FAKE_KEY not in status.text
    assert browser.get("/api/replay").json()["capabilities"]["live_inference"]
    started = browser.post("/api/investigate", json={"mode": "nebius"})
    assert started.status_code == 202
    deadline = monotonic() + 4
    while app.job(started.json()["id"])["status"] == "running":
        assert monotonic() < deadline
        sleep(0.01)
    assert len(calls) == 1 and calls[0].headers["Authorization"] == "Bearer " + FAKE_KEY
    assert not (app.root / "reports/nebius-usage.json").exists()
    assert not (app.root / "reports/ui").exists()
    assert browser.get("/api/budget").json()["requests"] == 1
    assert browser.post("/api/guidance", json={}).status_code == 400
    session = app.visitors.get(browser.headers["Cookie"].split("=", 1)[1])
    disconnected = browser.post("/api/key-disconnect", json={})
    assert disconnected.status_code == 200 and "Max-Age=0" in disconnected.headers["set-cookie"]
    assert not browser.get("/api/key-session").json()["connected"]
    assert not browser.get("/api/replay").json()["capabilities"]["live_inference"]
    assert session.revoked and not session.settings.nebius_api_key.get_secret_value()
    assert browser.post("/api/investigate", json={"mode": "nebius"}).status_code == 400
    assert len(calls) == 1


def test_origin_csrf_and_separate_visitors(site):
    app, browser, calls = site
    assert browser.post("/api/key-session", json={"nebius_api_key": FAKE_KEY},
                        headers={"Origin": "https://evil.example"}).status_code == 403
    assert not app.visitors.sessions
    response = browser.post("/api/key-session", json={"nebius_api_key": FAKE_KEY})
    token = response.headers["set-cookie"].split(";", 1)[0]
    assert browser.get("/api/key-session", headers={"Cookie": token}).json()["connected"]
    assert not browser.get("/api/key-session", headers={"Cookie": COOKIE_NAME + "=different"}).json()["connected"]
    assert browser.post("/api/investigate", json={"mode": "nebius"}, headers={"Cookie": ""}).status_code == 400
    assert not calls


def test_key_entry_requires_public_https_origin(tmp_path):
    app = dashboard.Dashboard(tmp_path, public_demo=True)
    with dashboard.make_server(0, app) as server:
        assert not app.allow_visitor_keys
    app = dashboard.Dashboard(tmp_path)
    with dashboard.make_server(0, app) as server:
        assert not app.allow_visitor_keys
