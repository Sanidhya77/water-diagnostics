"""Prioritize a useful operator check without claiming a physical diagnosis."""

from water_diagnostics.river_investigator import RiverEvidence, operator_actions


def test_fresh_latest_value_does_not_hide_an_earlier_gap_or_citation():
    evidence = [RiverEvidence(evidence_id="R03", tool="check_freshness",
        data={"fresh": True, "missing_value_count": 162}),
        RiverEvidence(evidence_id="R05", tool="check_maintenance_context",
        data={"recorded_visits_visible_at_replay_clock": [{"source": "historical_technician_record"}]})]
    actions = operator_actions(evidence)
    assert "162" in actions[0].action and "R03" in actions[0].action
    assert "latest received sample is fresh" in actions[0].action
    assert "R05" in actions[1].action and "do not establish" in actions[1].action
    assert all(action.status == "requested_not_performed" for action in actions)
    assert "independent turbidity" in actions[2].action


def test_stale_received_data_prioritizes_heartbeat_and_power_check():
    actions = operator_actions([RiverEvidence(evidence_id="R01", tool="check_freshness",
        data={"fresh": False, "missing_value_count": 0})])
    assert "heartbeat and power" in actions[0].action
    assert "do not interpret it as current water conditions" in actions[0].action


def test_complete_fresh_data_keeps_independent_measurement_first():
    actions = operator_actions([RiverEvidence(evidence_id="R01", tool="check_freshness",
        data={"fresh": True, "missing_value_count": 0})])
    assert len(actions) == 2 and "independent turbidity" in actions[0].action
