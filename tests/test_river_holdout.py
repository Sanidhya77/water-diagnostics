"""The extra-week evaluator must fail closed on answer reads and outbound calls."""

import json

import httpx
import pytest

from test_river_data import prepare
from scripts import evaluate_river_holdout as holdout
from water_diagnostics.river_data import DatasetError


def selection():
    return {"site": "udall", "start_utc": "2024-04-01T00:00:00Z",
        "end_exclusive_utc": "2024-04-08T00:00:00Z",
        "replay_clocks_utc": ["2024-04-03T00:00:00Z"],
        "selection_basis": "Fixed fixture clock before evaluation."}


@pytest.mark.parametrize("attempt", ["answers", "network"])
def test_forbidden_access_is_recorded_as_failure_without_fallback(tmp_path, monkeypatch, attempt):
    directory, _ = prepare(tmp_path)
    original = (directory / "observations.json").read_bytes()

    def wrong_reader(*args, **kwargs):
        if attempt == "answers":
            (directory / "evaluation.json").read_text(encoding="utf-8")
        else:
            with httpx.Client() as client:
                client.get("https://must-not-send.invalid")
        pytest.fail("The evaluation guard did not reject forbidden access.")

    monkeypatch.setattr(holdout, "investigate_river", wrong_reader)
    result = holdout.run_evaluation(directory, selection(), tmp_path / "out")
    assert result["replays_evaluated"] == 1
    assert result["workflow_integrity_passed"] == 0
    assert result["results"][0]["error_type"] == "PermissionError"
    assert result["inputs_unchanged"]
    assert (directory / "observations.json").read_bytes() == original
    assert "EVALUATOR_SECRET" not in json.dumps(result)
    assert not list((tmp_path / "out").glob("RIVER-*"))


def test_wrong_period_stops_before_creating_outputs(tmp_path, monkeypatch):
    directory, _ = prepare(tmp_path)
    plan = selection() | {"start_utc": "2024-04-08T00:00:00Z"}
    monkeypatch.setattr(holdout, "investigate_river", lambda *a, **k: pytest.fail("No investigation expected"))
    with pytest.raises(DatasetError, match="does not match"):
        holdout.run_evaluation(directory, plan, tmp_path / "out")
    assert not (tmp_path / "out").exists()
