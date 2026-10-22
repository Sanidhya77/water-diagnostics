"""Spending safeguards must be checked before any paid HTTP request."""

import httpx
import pytest

from water_diagnostics.config import DEFAULT_MODEL, Settings
from water_diagnostics.model_client.budget import BudgetError, CostGuard
from water_diagnostics.model_client.nebius import ModelClientError, NebiusClient


def payload():
    return {"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": "OK?"}], "max_tokens": 256}


def test_tiny_budget_blocks_before_http(tmp_path):
    requests = []
    guard = CostGuard(tmp_path / "usage.json", project_cap=0.000001)
    client = NebiusClient(Settings(nebius_api_key="synthetic"),
                          httpx.MockTransport(lambda request: requests.append(request)), budget=guard)
    try:
        with pytest.raises(ModelClientError, match="spending guard"):
            client.ping()
    finally:
        client.close()
    assert requests == []


def test_reservations_persist_and_missing_usage_is_not_assumed_free(tmp_path):
    path = tmp_path / "usage.json"
    guard = CostGuard(path)
    guard.reserve(DEFAULT_MODEL, payload())
    assert CostGuard(path).summary()["conservative_accounted_usd"] > 0
    assert CostGuard(path).summary()["requests_with_usage"] == 0
    assert CostGuard(path).summary()["reported_cost_estimate_usd"] == 0


def test_token_usage_cost_saved_without_prompt_or_secret(tmp_path):
    path = tmp_path / "usage.json"
    guard = CostGuard(path)
    identifier = guard.reserve(DEFAULT_MODEL, payload())
    guard.record_usage(identifier, {"prompt_tokens": 100, "completion_tokens": 200})
    summary = guard.summary()
    assert summary["reported_cost_estimate_usd"] == pytest.approx(0.000054)
    assert summary["requests_with_usage"] == 1
    assert "OK?" not in path.read_text()
    assert summary["conservative_accounted_usd"] >= summary["reported_cost_estimate_usd"]


def test_price_unknown_model_and_large_request_are_blocked(tmp_path):
    guard = CostGuard(tmp_path / "usage.json")
    with pytest.raises(BudgetError, match="Nano"):
        guard.reserve("another-model", payload())
    with pytest.raises(BudgetError, match="limit"):
        guard.reserve(DEFAULT_MODEL, {**payload(), "max_tokens": 5000})
    with pytest.raises(BudgetError, match="limit"):
        guard.reserve(DEFAULT_MODEL, {**payload(), "messages": [{"role": "user", "content": "x" * 61000}]})


def test_corrupt_ledger_does_not_reset_spending_to_zero(tmp_path):
    path = tmp_path / "usage.json"
    path.write_text("broken")
    with pytest.raises(BudgetError, match="unreadable"):
        CostGuard(path).reserve(DEFAULT_MODEL, payload())


def test_local_run_limit_stops_repeated_calls(tmp_path):
    guard = CostGuard(tmp_path / "usage.json", run_cap=0.0009)
    guard.reserve(DEFAULT_MODEL, payload())
    guard.reserve(DEFAULT_MODEL, payload())
    with pytest.raises(BudgetError, match="spending guard"):
        guard.reserve(DEFAULT_MODEL, payload())


def test_successful_response_records_usage_even_when_output_is_truncated(tmp_path):
    guard = CostGuard(tmp_path / "usage.json")
    body = {"usage": {"prompt_tokens": 12, "completion_tokens": 256},
            "choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": "partial"}}]}
    client = NebiusClient(Settings(nebius_api_key="synthetic"),
                          httpx.MockTransport(lambda request: httpx.Response(200, json=body)), budget=guard)
    try:
        with pytest.raises(ModelClientError, match="token limit"):
            client.ping()
    finally:
        client.close()
    assert guard.summary()["requests_with_usage"] == 1
