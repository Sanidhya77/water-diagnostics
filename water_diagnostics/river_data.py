"""Prepare a small historical river case locally, with evaluator data separate.

This module never imports the hosted client, reads credentials, or calls APIs.
It reads known CSV members inside ZIPs without extracting entire archives.
"""

import csv
import io
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from zipfile import BadZipFile, ZipFile


RAW = "2024/CSU_ROSS_2024_raw.csv"
CLEANED = "2024/CSU_ROSS_2024_cleaned.csv"
NOTES = "2024/CSU_ROSS_sensor_field_notes_2024.csv"
METHODS = "metadata/CSU_ROSS_sensor_methods_metadata.csv"
LOCATIONS = "metadata/CSU_ROSS_sonde_location_metadata.csv"
FLAGS = "metadata/CSU_ROSS_user_qc_flag_metadata.csv"
SOURCE_URL = "https://www.hydroshare.org/resource/63ede02dd7da44a5a3040fd9ad14ab15/"
NOTE_AVAILABILITY = (
    "Historical replay assumption: visit notes become available at the next UTC midnight. "
    "The source provides visit times, not the actual times when notes were entered."
)


class DatasetError(RuntimeError):
    pass


def utc_time(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        raise DatasetError("Use a valid timestamp with a timezone, for example 2024-04-03T00:00:00Z.") from None


def _number(text: str) -> float | None:
    try:
        number = float(text)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def find_archive(directory: Path, required_member: str) -> Path:
    matches = []
    for path in directory.glob("*.zip"):
        try:
            with ZipFile(path) as archive:
                if required_member in archive.namelist():
                    matches.append(path)
        except BadZipFile:
            continue
    if len(matches) != 1:
        raise DatasetError("Could not identify one matching ZIP; supply --data-zip and --metadata-zip explicitly.")
    return matches[0]


def _rows(archive: ZipFile, member: str):
    try:
        handle = archive.open(member)
    except KeyError:
        raise DatasetError(f"Required archive member is missing: {member}.") from None
    with handle, io.TextIOWrapper(handle, encoding="utf-8-sig", newline="") as text:
        yield from csv.DictReader(text)


def _key(row: dict) -> tuple[str, str]:
    return row["DateTime_UTC"], row["parameter"]


def prepare_river_case(data_zip: Path, metadata_zip: Path, output: Path,
                       site: str = "udall", start: str = "2024-04-01T00:00:00Z",
                       days: int = 7) -> dict:
    begin = utc_time(start)
    if not 1 <= days <= 31:
        raise DatasetError("Prepare a small case between 1 and 31 days.")
    end = begin + timedelta(days=days)
    try:
        with ZipFile(metadata_zip) as metadata:
            locations = list(_rows(metadata, LOCATIONS))
            methods = list(_rows(metadata, METHODS))
            definitions = list(_rows(metadata, FLAGS))
        location = next((r for r in locations if r["site"] == site), None)
        if location is None:
            raise DatasetError("The selected site is missing from the location metadata.")
        originals = {}
        with ZipFile(data_zip) as archive:
            for row in _rows(archive, RAW):
                if row["site"] != site or not begin <= utc_time(row["DateTime_UTC"]) < end:
                    continue
                key = _key(row)
                if key in originals:
                    raise DatasetError("Duplicate timestamp/parameter key in the selected raw data.")
                originals[key] = row
            if not originals:
                raise DatasetError("No raw readings were found for this site and period.")
            cleaned = {}
            for row in _rows(archive, CLEANED):
                if row["site"] == site and begin <= utc_time(row["DateTime_UTC"]) < end:
                    key = _key(row)
                    if key in cleaned:
                        raise DatasetError("Duplicate timestamp/parameter key in the selected cleaned data.")
                    cleaned[key] = row
            if originals.keys() != cleaned.keys():
                raise DatasetError("Raw and cleaned records do not match for the selected period.")
            if any(originals[k]["value_raw"] != cleaned[k]["value_raw"] for k in originals):
                raise DatasetError("Original values differ between raw and cleaned files.")
            visit_rows = [r for r in _rows(archive, NOTES)
                          if r["site"] == site and begin <= utc_time(r["DateTime_UTC"]) < end]
    except (BadZipFile, OSError, KeyError, csv.Error) as error:
        raise DatasetError(f"Could not read the dataset ({type(error).__name__}).") from None

    ordered = [originals[k] for k in sorted(originals)]
    points = [{"timestamp": row["DateTime_UTC"], "parameter": row["parameter"],
               "units": row["units"], "value": _number(row["value_raw"])} for row in ordered]
    parameters = sorted({p["parameter"] for p in points})
    selected_methods = {}
    for parameter in parameters:
        # The observations use DO; the method dictionary names the sensor RDO.
        method_name = "RDO" if parameter == "DO" else parameter
        selected_methods[parameter] = next((r for r in methods if r["parameter"] == method_name), None)
    visits = []
    for row in sorted(visit_rows, key=lambda r: r["DateTime_UTC"]):
        visited = utc_time(row["DateTime_UTC"])
        available = visited.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        visits.append({"visit_time_utc": row["DateTime_UTC"],
                       "assumed_available_at_utc": available.isoformat(),
                       "sensors_cleaned": row.get("sensors_cleaned"),
                       "calibrations_recorded": row.get("cals_performed"),
                       "reported_sensor_issue": row.get("sensor_malfunction"),
                       "visit_comments": row.get("visit_comments"),
                       "source": "historical_technician_record"})
    provenance = {"data_archive": str(data_zip.resolve()), "metadata_archive": str(metadata_zip.resolve()),
                  "source_url": SOURCE_URL, "licence": "CC BY 4.0", "original_files_modified": False}
    observations = {"schema_version": 1, "source": "REAL_RIVER_SENSOR_DATA", "site": site,
                    "start_utc": begin.isoformat(), "end_exclusive_utc": end.isoformat(),
                    "expected_interval_seconds": 900, "provenance": provenance,
                    "value_source": "Original value_raw; missing/nonfinite values remain null, not zero.",
                    "records": points}
    context = {"source": "REAL_RIVER_SENSOR_DATA", "site": site,
               "site_metadata": location, "sensor_methods": selected_methods,
               "calibration_note": "Methods describe standard procedures, not proof a calibration occurred at a particular time.",
               "visit_note_availability_assumption": NOTE_AVAILABILITY,
               "visit_records": visits}
    review = [{"timestamp": row["DateTime_UTC"], "parameter": row["parameter"],
               "original_value": _number(row["value_raw"]),
               "corrected_value": _number(cleaned[_key(row)]["value_final"]),
               "qc_status": row.get("qc_status"), "user_qc_flag": row.get("user_qc_flag"),
               "modifications": row.get("modifications")} for row in ordered]
    applied_flags = {flag.strip() for row in ordered
                     for flag in re.split(r";\s*", row.get("user_qc_flag", ""))
                     if flag.strip() not in ("", "NA")}
    defined_flags = {r["flags"] for r in definitions}
    evaluation = {"source": "REAL_RIVER_SENSOR_DATA", "purpose": "Evaluator-only retrospective review; do not send this file to the investigator.",
                  "flag_definitions": definitions, "flags_without_definition": sorted(applied_flags - defined_flags),
                  "interpretation_note": "The dataset's frozen flag refers to water likely freezing near sensor heads, not a stuck numeric signal.",
                  "records": review}
    summary = {"site": site, "start_utc": begin.isoformat(), "end_exclusive_utc": end.isoformat(),
               "measurements": len(points), "turbidity_readings": sum(p["parameter"] == "Turbidity" for p in points),
               "parameter_counts": dict(Counter(p["parameter"] for p in points)),
               "missing_values": sum(p["value"] is None for p in points), "visit_records": len(visits),
               "flags_without_definition": evaluation["flags_without_definition"], "nebius_requests": 0}
    output.mkdir(parents=True, exist_ok=True)
    for filename, data in (("observations.json", observations), ("context.json", context),
                           ("evaluation.json", evaluation), ("preparation-summary.json", summary)):
        (output / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return summary


def river_snapshot(directory: Path, at: str, history_hours: int = 48) -> dict:
    """Causal local check summaries. Never open the evaluator file or call a model."""
    observed = utc_time(at)
    if not 1 <= history_hours <= 168:
        raise DatasetError("Select between 1 and 168 hours of history.")
    try:
        observations = json.loads((directory / "observations.json").read_text(encoding="utf-8"))
        context = json.loads((directory / "context.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DatasetError("Prepare the river case first; its observation/context files are unavailable.") from None
    if (observations.get("source") != "REAL_RIVER_SENSOR_DATA"
            or context.get("source") != "REAL_RIVER_SENSOR_DATA"
            or observations.get("site") != context.get("site")
            or type(observations.get("expected_interval_seconds")) is not int
            or observations["expected_interval_seconds"] <= 0):
        raise DatasetError("Prepared observation/context sources, sites or sampling interval do not match.")
    if any(r["parameter"] == "Turbidity" and r["units"] != "NTU" for r in observations["records"]):
        raise DatasetError("River turbidity observations must retain their original NTU units.")
    if not utc_time(observations["start_utc"]) <= observed <= utc_time(observations["end_exclusive_utc"]):
        raise DatasetError("The requested replay clock is outside the prepared period.")
    earliest = observed - timedelta(hours=history_hours)
    records = [r for r in observations["records"] if earliest <= utc_time(r["timestamp"]) <= observed]
    turbidity = sorted((r for r in records if r["parameter"] == "Turbidity"), key=lambda r: r["timestamp"])
    usable = [r for r in turbidity if r["value"] is not None]
    recent = [r for r in usable if utc_time(r["timestamp"]) >= observed - timedelta(hours=6)]
    prior = [r["value"] for r in usable if utc_time(r["timestamp"]) < observed - timedelta(hours=6)]
    values = [r["value"] for r in recent]
    interval = observations["expected_interval_seconds"]
    age = (observed - utc_time(usable[-1]["timestamp"])).total_seconds() if usable else None
    tail = []
    for row in reversed(turbidity):
        if row["value"] is None or (tail and (row["value"] != tail[-1]["value"] or
              (utc_time(tail[-1]["timestamp"]) - utc_time(row["timestamp"])).total_seconds() != interval)):
            break
        tail.append(row)
    visible_visits = [r for r in context["visit_records"]
                      if earliest <= utc_time(r["visit_time_utc"]) <= observed
                      and utc_time(r["assumed_available_at_utc"]) <= observed]
    related = []
    for parameter in sorted({r["parameter"] for r in records} - {"Turbidity"}):
        series = sorted((r for r in records if r["parameter"] == parameter), key=lambda r: r["timestamp"])
        valid = [r for r in series if r["value"] is not None]
        last = valid[-1] if valid else None
        related.append({"parameter": parameter, "units": series[-1]["units"],
                        "latest_value": last["value"] if last else None,
                        "latest_timestamp": last["timestamp"] if last else None,
                        "age_seconds": (observed - utc_time(last["timestamp"])).total_seconds() if last else None,
                        "independent_turbidity_reference": False})
    return {"source": "REAL_RIVER_SENSOR_DATA", "site": observations["site"],
            "observed_at": observed.isoformat(), "mode": "local_read_only_checks_no_model",
            "check_freshness": {"expected_interval_seconds": interval,
                "sample_count": len(turbidity), "missing_value_count": len(turbidity) - len(usable),
                "latest_usable_age_seconds": age,
                "fresh": bool(age is not None and age <= interval * 2 and turbidity[-1]["value"] is not None)},
            "check_variation": {"window_hours": 6,
                "window_start_utc": (observed - timedelta(hours=6)).isoformat(),
                "usable_recent_count": len(values),
                "latest_ntu": usable[-1]["value"] if usable else None,
                "recent_min_ntu": min(values) if values else None,
                "recent_max_ntu": max(values) if values else None,
                "recent_mean_ntu": mean(values) if values else None,
                "recent_stddev_ntu": pstdev(values) if values else None,
                "earlier_history_median_ntu": median(prior) if prior else None,
                "trailing_identical_count": len(tail), "regulatory_alarm_threshold_applied": False},
            "check_device_status": {"available": False,
                "reason": "No live heartbeat/fault log is supplied. Historical visit notes are separate context.",
                "sensor_method": context["sensor_methods"].get("Turbidity")},
            "check_maintenance_context": {"availability_assumption": NOTE_AVAILABILITY,
                "recorded_visits_visible_at_replay_clock": visible_visits,
                "physical_test_executed_by_agent": False},
            "check_related_measurements": {"signals": related,
                "independent_turbidity_measurement_available": False},
            "limitations": ["Historical river data, not filter outlet validation.",
                "Source visit comments are recorded observations, not instructions to execute.",
                "Retrospective QC flags and corrected values were not read by these checks.",
                "No water-safety determination or equipment action is made."]}
