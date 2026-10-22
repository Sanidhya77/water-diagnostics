"""Regression check: absent independent evidence must never be described as present."""

from water_diagnostics.incident_reports.schema import Cause
from water_diagnostics.investigator import investigate_offline
from water_diagnostics.simulator import make_replay


def test_ambiguous_report_does_not_invent_independent_corroboration():
    report = investigate_offline(make_replay("insufficient"))
    process = next(c for c in report.possible_causes if c.cause == Cause.PROCESS)
    assert "No fresh independent outlet result" in process.interpretation
    assert "also reports elevated" not in process.interpretation
    sensor = next(c for c in report.possible_causes if c.cause == Cause.SENSOR)
    assert "exactly identical" not in sensor.interpretation
    assert "fault codes:" not in sensor.interpretation


def test_process_report_describes_actual_independent_corroboration():
    report = investigate_offline(make_replay("process_change"))
    process = next(c for c in report.possible_causes if c.cause == Cause.PROCESS)
    assert "also reports elevated" in process.interpretation
