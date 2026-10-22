"""Prevent future observations and evaluator answers leaking into river checks."""

import csv
import io
import json
from zipfile import ZipFile

import pytest

from water_diagnostics.river_data import (
    CLEANED, FLAGS, LOCATIONS, METHODS, NOTES, RAW, DatasetError,
    find_archive, prepare_river_case, river_snapshot,
)


def write_csv(archive, name, fields, rows):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    archive.writestr(name, text.getvalue())


def fixture_archives(directory, mismatch=False, duplicate=False):
    data = directory / "data.zip"
    metadata = directory / "metadata.zip"
    fields = ["DateTime_UTC", "site", "parameter", "units", "value_raw", "qc_status", "user_qc_flag", "modifications"]
    points = [("2024-04-01T00:00:00Z", "Turbidity", "NA"),
              ("2024-04-02T22:00:00Z", "Turbidity", "10"),
              ("2024-04-02T22:15:00Z", "Turbidity", "10.3"),
              ("2024-04-03T00:00:00Z", "Turbidity", "1"),
              ("2024-04-03T00:15:00Z", "Turbidity", "1.2"),
              ("2024-04-03T00:00:00Z", "Temperature", "-0.2")]
    raw = [dict(zip(fields, [t, "udall", p, "NTU" if p == "Turbidity" else "C", v,
                            "FLAGGED", "EVALUATOR_SECRET", "drift correction"])) for t,p,v in points]
    clean = [{k:r[k] for k in ("DateTime_UTC", "site", "parameter", "units", "value_raw")}
             | {"value_final": "0.5"} for r in raw]
    if mismatch:
        clean[1]["value_raw"] = "99"
    if duplicate:
        raw.append(raw[1])
    with ZipFile(data, "w") as archive:
        write_csv(archive, RAW, fields, raw)
        write_csv(archive, CLEANED, list(clean[0]), clean)
        note = {"site":"udall", "DateTime_UTC":"2024-04-02T22:15:00Z",
                "sensors_cleaned":"TRUE", "cals_performed":"None",
                "sensor_malfunction":"Recorded drift before the visit", "visit_comments":"Sensor cleaned."}
        write_csv(archive, NOTES, list(note), [note])
    with ZipFile(metadata, "w") as archive:
        write_csv(archive, LOCATIONS, ["site", "site_description"], [{"site":"udall", "site_description":"River station"}])
        write_csv(archive, METHODS, ["parameter", "units", "sensor", "calibration_method"], [
            {"parameter":"Turbidity", "units":"NTU", "sensor":"Turbidity sensor", "calibration_method":"Two-point standard procedure"}])
        write_csv(archive, FLAGS, ["flags", "definition", "corrections"], [
            {"flags":"frozen", "definition":"Water is likely frozen near sensor heads", "corrections":"Review data"}])
    return data, metadata


def prepare(directory, **kwargs):
    data, metadata = fixture_archives(directory, **kwargs)
    output = directory / "prepared"
    summary = prepare_river_case(data, metadata, output)
    return output, summary


def test_observations_are_original_and_evaluator_answers_stay_separate(tmp_path):
    output, summary = prepare(tmp_path)
    observations = json.loads((output / "observations.json").read_text(encoding="utf-8"))
    context = json.loads((output / "context.json").read_text(encoding="utf-8"))
    evaluation = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert summary["turbidity_readings"] == 5
    assert observations["source"] == "REAL_RIVER_SENSOR_DATA"
    assert "EVALUATOR_SECRET" not in json.dumps(observations) + json.dumps(context)
    assert evaluation["records"][1]["corrected_value"] == 0.5
    assert evaluation["flags_without_definition"] == ["EVALUATOR_SECRET"]
    assert all(not {"qc_status", "user_qc_flag", "value_final"} & r.keys() for r in observations["records"])


def test_missing_values_are_null_and_signed_other_measurements_are_preserved(tmp_path):
    output, _ = prepare(tmp_path)
    records = json.loads((output / "observations.json").read_text(encoding="utf-8"))["records"]
    assert records[0]["value"] is None
    assert next(r for r in records if r["parameter"] == "Temperature")["value"] == -0.2


def test_replay_clock_excludes_future_values_and_delays_notes_explicitly(tmp_path):
    output, _ = prepare(tmp_path)
    before = river_snapshot(output, "2024-04-02T22:15:00Z")
    after = river_snapshot(output, "2024-04-03T00:00:00Z")
    assert before["check_variation"]["latest_ntu"] == 10.3
    assert before["check_maintenance_context"]["recorded_visits_visible_at_replay_clock"] == []
    assert after["check_variation"]["latest_ntu"] == 1.0  # Not the future 1.2 reading.
    assert len(after["check_maintenance_context"]["recorded_visits_visible_at_replay_clock"]) == 1
    assert "assumption" in after["check_maintenance_context"]["availability_assumption"]
    assert after["check_freshness"]["expected_interval_seconds"] == 900


def test_checks_never_open_the_evaluator_file(tmp_path):
    output, _ = prepare(tmp_path)
    (output / "evaluation.json").write_text("not even valid JSON")
    snapshot = river_snapshot(output, "2024-04-03T00:00:00Z")
    assert "EVALUATOR_SECRET" not in json.dumps(snapshot)
    assert snapshot["check_related_measurements"]["independent_turbidity_measurement_available"] is False
    assert snapshot["check_device_status"]["available"] is False


@pytest.mark.parametrize("change, message", [("mismatch", "Original values differ"), ("duplicate", "Duplicate")])
def test_source_inconsistency_stops_preparation(tmp_path, change, message):
    data, metadata = fixture_archives(tmp_path, **{change:True})
    with pytest.raises(DatasetError, match=message):
        prepare_river_case(data, metadata, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_unknown_site_and_bad_replay_clock_are_rejected(tmp_path):
    data, metadata = fixture_archives(tmp_path)
    with pytest.raises(DatasetError, match="site is missing"):
        prepare_river_case(data, metadata, tmp_path / "out", site="invented")
    output, _ = prepare(tmp_path)
    with pytest.raises(DatasetError, match="outside"):
        river_snapshot(output, "2024-04-09T00:00:00Z")
    with pytest.raises(DatasetError, match="timezone"):
        river_snapshot(output, "2024-04-03")


def test_archives_are_identified_by_content_not_uploaded_filename(tmp_path):
    data, metadata = fixture_archives(tmp_path)
    assert find_archive(tmp_path, RAW) == data
    assert find_archive(tmp_path, LOCATIONS) == metadata
