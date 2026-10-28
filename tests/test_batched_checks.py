"""Independent checks can share one model turn without weakening report constraints."""

import json

import pytest

from test_river_data import prepare
from water_diagnostics.investigator import investigate_nebius
from water_diagnostics.river_investigator import investigate_river
from water_diagnostics.simulator import make_replay


class BatchedClient:
    model = "synthetic-test-model"

    def __init__(self):
        self.requests = 0

    def complete(self, messages, tools, max_tokens):
        self.requests += 1
        if self.requests == 1:
            names = [t["function"]["name"] for t in tools if t["function"]["name"] != "submit_report"]
            assert len(names) == 5
            return {"tool_calls": [{"id": "check-" + str(i), "type": "function",
                "function": {"name": name, "arguments": "{}"}} for i, name in enumerate(names)]}
        assert self.requests == 2 and len(tools) == 1
        evidence = json.loads(messages[-1]["content"])
        assert len(evidence["completed_checks"]) == 5
        constraints = evidence["report_constraints"]
        arguments = {"conclusion": constraints["allowed_conclusions"][0]}
        if "required_possible_causes" in constraints:
            arguments["possible_causes"] = constraints["required_possible_causes"]
        return {"tool_calls": [{"id": "report", "type": "function",
            "function": {"name": "submit_report", "arguments": json.dumps(arguments)}}]}


@pytest.mark.parametrize("source", ["simulated", "river"])
def test_five_checks_and_final_report_can_complete_in_two_model_turns(tmp_path, source):
    client = BatchedClient()
    if source == "simulated":
        report = investigate_nebius(make_replay("frozen"), client)
    else:
        directory, _ = prepare(tmp_path)
        report = investigate_river(directory, "2024-04-03T00:00:00Z", client)
    assert client.requests == 2
    assert report.investigation_status == "complete"
    assert len(report.observations) == len(set(report.checks_performed)) == 5
    ids = {item.evidence_id for item in report.observations}
    assert len(ids) == 5
    for cause in report.possible_causes:
        cited = getattr(cause, "relevant_evidence_ids", getattr(cause, "supporting_evidence_ids", []))
        assert set(cited) <= ids
