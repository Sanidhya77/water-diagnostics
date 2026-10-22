"""Evaluate a preselected river week locally. No model, training or API requests."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from water_diagnostics.river_data import DatasetError, utc_time
from water_diagnostics.river_investigator import RIVER_TOOLS, investigate_river, save_river_report


def run_evaluation(directory, selection, output):
    directory, output = Path(directory), Path(output)
    allowed = {directory.joinpath(name).resolve() for name in ("observations.json", "context.json")}
    original_read = Path.read_text
    observations = json.loads(original_read(directory / "observations.json", encoding="utf-8"))
    context = json.loads(original_read(directory / "context.json", encoding="utf-8"))
    begin, end = utc_time(selection["start_utc"]), utc_time(selection["end_exclusive_utc"])
    if (observations["site"] != selection["site"] or context["site"] != selection["site"]
            or utc_time(observations["start_utc"]) != begin
            or utc_time(observations["end_exclusive_utc"]) != end):
        raise DatasetError("Prepared data does not match the preselected site and period.")
    clocks = selection["replay_clocks_utc"]
    if not 1 <= len(clocks) <= 12 or len(set(clocks)) != len(clocks):
        raise DatasetError("Select between one and twelve distinct replay clocks.")
    if any(not begin <= utc_time(clock) <= end for clock in clocks):
        raise DatasetError("A selected replay clock is outside the prepared period.")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(allowed)}
    output.mkdir(parents=True, exist_ok=False)
    reads = set()

    def read_input(path, *args, **kwargs):
        if path.resolve() not in allowed:
            raise PermissionError("Investigation attempted to read outside observation/context inputs.")
        reads.add(path.name)
        return original_read(path, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise PermissionError("Network calls are disabled for this local evaluation.")

    rows = []
    for clock in clocks:
        row = {"clock_utc": clock}
        try:
            with patch.object(Path, "read_text", read_input), \
                 patch("httpx.Client.send", no_network), patch("httpx.AsyncClient.send", no_network):
                report = investigate_river(directory, clock, client=None)
            evidence = {item.tool: item for item in report.observations}
            ids = {item.evidence_id for item in report.observations}
            observed = utc_time(clock)
            timestamps = []
            for item in evidence.get("check_related_measurements").data["signals"]:
                if item["latest_timestamp"]:
                    timestamps.append(utc_time(item["latest_timestamp"]))
            visits = evidence["check_maintenance_context"].data["recorded_visits_visible_at_replay_clock"]
            for visit in visits:
                timestamps += [utc_time(visit["visit_time_utc"]), utc_time(visit["assumed_available_at_utc"])]
            forbidden = {"qc_status", "user_qc_flag", "value_final", "corrected_value", "modifications"}

            def keys(value):
                if isinstance(value, dict):
                    return set(value).union(*(keys(v) for v in value.values()))
                if isinstance(value, list):
                    return set().union(*(keys(v) for v in value))
                return set()

            checks = {
                "complete_five_checks": report.investigation_status == "complete"
                    and len(report.observations) == len(ids) == 5
                    and set(report.checks_performed) == set(RIVER_TOOLS),
                "local_reference_only": report.investigation_mode == "offline_reference_policy" and report.model is None,
                "source_preserved": report.source == "REAL_RIVER_SENSOR_DATA"
                    and all(item.source == report.source for item in report.observations),
                "no_future_evidence": all(time <= observed for time in timestamps),
                "no_retrospective_fields": not (keys(report.model_dump()) & forbidden),
                "citations_resolve": all(set(cause.relevant_evidence_ids) <= ids for cause in report.possible_causes),
                "uncertainty_preserved": report.conclusion == "insufficient_evidence"
                    and not evidence["check_device_status"].data["available"]
                    and not evidence["check_related_measurements"].data["independent_turbidity_measurement_available"],
                "no_plant_threshold": evidence["check_variation"].data["regulatory_alarm_threshold_applied"] is False,
            }
            variation = evidence["check_variation"].data
            freshness = evidence["check_freshness"].data
            paths = save_river_report(report, output)
            row.update({"status": report.investigation_status, "integrity_checks": checks,
                "integrity_passed": all(checks.values()), "conclusion": report.conclusion,
                "latest_ntu": variation["latest_ntu"], "recent_min_ntu": variation["recent_min_ntu"],
                "recent_max_ntu": variation["recent_max_ntu"], "fresh": freshness["fresh"],
                "missing_turbidity_values_in_history": freshness["missing_value_count"],
                "latest_usable_age_seconds": freshness["latest_usable_age_seconds"],
                "visible_visits": len(visits), "checks_performed": report.checks_performed,
                "reports": [path.name for path in paths]})
        except Exception as error:
            # Keep every attempted clock. Private paths or raw provider errors never enter the summary.
            row.update({"status": "error", "integrity_passed": False, "error_type": type(error).__name__})
        rows.append(row)
    unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path.name] for path in allowed)
    result = {"source": "REAL_RIVER_SENSOR_DATA", "site": selection["site"],
        "period": {"start_utc": selection["start_utc"], "end_exclusive_utc": selection["end_exclusive_utc"]},
        "selection_basis": selection["selection_basis"], "prepared_measurements": len(observations["records"]),
        "prepared_turbidity_readings": sum(r["parameter"] == "Turbidity" for r in observations["records"]),
        "prepared_missing_values": sum(r["value"] is None for r in observations["records"]),
        "prepared_missing_turbidity": sum(r["parameter"] == "Turbidity" and r["value"] is None for r in observations["records"]),
        "input_sha256": hashes, "investigation_files_read": sorted(reads), "inputs_unchanged": unchanged,
        "replays_evaluated": len(rows), "workflow_integrity_passed": sum(r["integrity_passed"] for r in rows),
        "new_nebius_requests": 0, "new_tavily_requests": 0, "training_performed": False,
        "hosted_model_evaluated": False, "results": rows,
        "limitation": "Additional nonoverlapping week of local workflow checks; not diagnostic accuracy, an independent benchmark or a fresh hosted-model evaluation. The river policy permits only insufficient_evidence because independent turbidity and live fault logs are unavailable."}
    (output / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "comparison.md").write_text(render(result), encoding="utf-8")
    return result


def render(result):
    lines = ["# Additional river-week local checks", "", result["limitation"], "",
        f"Site: {result['site']}. Period: {result['period']['start_utc']} to {result['period']['end_exclusive_utc']} (end exclusive).",
        "", result["selection_basis"], "",
        f"Turbidity time slots: {result['prepared_turbidity_readings']}; missing values: {result['prepared_missing_turbidity']}. Missing values stay null, not zero or interpolated.", "",
        "| Replay clock UTC | Latest NTU | Six-hour range NTU | Fresh | Missing in 48h | Visible visits | Integrity |",
        "| --- | ---: | --- | --- | ---: | ---: | --- |"]
    for row in result["results"]:
        lines.append(f"| {row['clock_utc']} | {row.get('latest_ntu', '—')} | {row.get('recent_min_ntu', '—')}–{row.get('recent_max_ntu', '—')} | {row.get('fresh', '—')} | {row.get('missing_turbidity_values_in_history', '—')} | {row.get('visible_visits', '—')} | {'Pass' if row['integrity_passed'] else 'Fail'} |")
    lines += ["", f"Workflow integrity: {result['workflow_integrity_passed']}/{result['replays_evaluated']} replay checks passed.",
        "Every attempted clock is retained, including errors or incomplete investigations.", "",
        "No model called, no training performed, no new Nebius or Tavily requests.",
        "The investigator read only observations.json and context.json. Retrospective QC was excluded.",
        f"Observation/context input hashes unchanged: {result['inputs_unchanged']}.", "",
        "Complete per-clock evidence, uncertainty and requested operator actions are in the companion JSON/Markdown reports.",
        "Source: CSU ROSS / Poudre Water Quality Network, CC BY 4.0. See THIRD_PARTY.md."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/river/udall-2024-04-08")
    parser.add_argument("--selection", type=Path, default=ROOT / "evaluations/river-holdout-2024-04-08/selection.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" /
        ("river-holdout-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    args = parser.parse_args()
    result = run_evaluation(args.input, json.loads(args.selection.read_text(encoding="utf-8")), args.output)
    print(json.dumps({"replays": result["replays_evaluated"], "workflow_integrity": result["workflow_integrity_passed"],
        "hosted_model_evaluated": False, "new_api_requests": 0, "inputs_unchanged": result["inputs_unchanged"]}))
    raise SystemExit(0 if result["workflow_integrity_passed"] == result["replays_evaluated"] and result["inputs_unchanged"] else 2)
