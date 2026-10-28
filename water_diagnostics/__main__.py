"""Run with: python -m water_diagnostics --help."""

import argparse
import json
import os
import sys
from pathlib import Path

from water_diagnostics.config import PROJECT_ROOT, load_settings
from water_diagnostics.evaluation import evaluate
from water_diagnostics.incident_reports.reporting import save_report
from water_diagnostics.incident_reports.schema import IncidentReport
from water_diagnostics.investigator import investigate_nebius, investigate_offline
from water_diagnostics.model_client.nebius import ModelClientError, NebiusClient
from water_diagnostics.model_client.budget import BudgetError, CostGuard
from water_diagnostics.simulator import CASE_NAMES, make_replay
from water_diagnostics.river_data import DatasetError, RAW, LOCATIONS, find_archive, prepare_river_case, river_snapshot
from water_diagnostics.river_investigator import investigate_river, save_river_report
from water_diagnostics.recovery import CASES as RECOVERY_CASES, RecoveryError, run_recovery_demo, save_recovery


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Read-only water investigations and local river replay preparation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-cases", help="List the six simulated replay cases")
    sub.add_parser("check-connection", help="One short Nebius request; requires a local key and uses credits")
    sub.add_parser("budget-status", help="Read local usage estimates and conservative limits; no network")
    interface = sub.add_parser("serve", help="Open a local operator interface; browsing and local checks use no credits")
    interface.add_argument("--port", type=int, default=8765)
    interface.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    interface.add_argument("--public-demo", action="store_true", help="Disable paid APIs and keep generated reports in memory")
    export = sub.add_parser("export-replays", help="Save inspectable simulated inputs; no network")
    export.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "replays")
    run = sub.add_parser("run", help="Investigate one simulated incident and save JSON + Markdown")
    run.add_argument("--case", choices=CASE_NAMES, default="insufficient")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--mode", choices=("offline", "nebius"), default="offline")
    run.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports")
    run.add_argument("--resume-report", type=Path,
                     help="Retry only the final report from an incomplete hosted report; one API request")
    evaluation = sub.add_parser("evaluate", help="Run synthetic smoke cases; nebius mode uses credits")
    evaluation.add_argument("--mode", choices=("offline", "nebius"), default="offline")
    evaluation.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports")
    validation = sub.add_parser("validate-demo", help="Compare three fixtures with saved model reports; nebius fills missing cases under a $0.04 local guard")
    validation.add_argument("--mode", choices=("saved", "nebius"), default="saved")
    validation.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "demo-validation")
    recovery = sub.add_parser("recovery-demo", help="Simulate one bounded collector reconnect, verification and escalation; no API or hardware")
    recovery.add_argument("--case", choices=RECOVERY_CASES, default="collector_recovers")
    recovery.add_argument("--investigation-report", type=Path, help="Reuse a saved complete hosted communication-loss report after local audit")
    recovery.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "recovery")
    prepare = sub.add_parser("prepare-river", help="Prepare the uploaded Udall river subset locally; no network")
    prepare.add_argument("--data-zip", type=Path)
    prepare.add_argument("--metadata-zip", type=Path)
    prepare.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "river" / "udall-2024-04-01")
    inspect = sub.add_parser("inspect-river", help="Run five local checks at a historical replay clock; no model")
    inspect.add_argument("--input", type=Path, default=PROJECT_ROOT / "data" / "river" / "udall-2024-04-01")
    inspect.add_argument("--at", default="2024-04-03T00:00:00Z")
    inspect.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "river-snapshot.json")
    river = sub.add_parser("run-river", help="Investigate the prepared historical river case; nebius mode uses credits")
    river.add_argument("--input", type=Path, default=PROJECT_ROOT / "data" / "river" / "udall-2024-04-01")
    river.add_argument("--at", default="2024-04-03T00:00:00Z")
    river.add_argument("--mode", choices=("offline", "nebius"), default="offline")
    river.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports")
    args = parser.parse_args()
    if args.command == "run" and args.resume_report and args.mode != "nebius":
        parser.error("--resume-report requires --mode nebius")
    client = None
    try:
        if args.command == "recovery-demo":
            report = run_recovery_demo(args.case, investigation_path=args.investigation_report)
            paths = save_recovery(report, args.output)
            print(f"SIMULATED collector recovery: {report.outcome}; policy={report.policy.verdict}; attempts={report.attempts}/1")
            print(f"Diagnosis: {report.diagnostic_origin}; verification={report.verification.status}")
            for event in report.events:
                print(event)
            for path in paths:
                print(f"Saved: {path.resolve()}")
            print("No new API call, real hardware action or notification. Telemetry recovery does not establish water safety.")
            return 0
        if args.command == "serve":
            from water_diagnostics.dashboard import serve
            if not 1024 <= args.port <= 65535:
                parser.error("Choose a local port between 1024 and 65535.")
            try:
                if args.host == "0.0.0.0" and not args.public_demo:
                    parser.error("External binding requires --public-demo; paid provider requests stay disabled.")
                serve(args.port, bind_address=args.host, public_demo=args.public_demo,
                      public_origin=os.environ.get("RENDER_EXTERNAL_URL") if args.public_demo else None)
            except OSError:
                print("Could not start the local interface. Try --port 8766 if the address is already in use.", file=sys.stderr)
                return 2
            return 0
        if args.command == "prepare-river":
            summary = prepare_river_case(args.data_zip or find_archive(PROJECT_ROOT.parent, RAW),
                args.metadata_zip or find_archive(PROJECT_ROOT.parent, LOCATIONS), args.output)
            print(json.dumps(summary, indent=2))
            print(f"Prepared local files: {args.output.resolve()}")
            print("Real river data; evaluator annotations are separate. No API requests.")
            return 0
        if args.command == "inspect-river":
            snapshot = river_snapshot(args.input, args.at)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            print(f"Real river replay clock: {snapshot['observed_at']}")
            print(f"Local checks: 5; latest turbidity: {snapshot['check_variation']['latest_ntu']} NTU")
            print(f"Visible technician visits: {len(snapshot['check_maintenance_context']['recorded_visits_visible_at_replay_clock'])}")
            print(f"Saved: {args.output.resolve()}")
            print("No model called; no retrospective QC answers read; no water-safety determination.")
            return 0
        if args.command == "budget-status":
            print(json.dumps(CostGuard().summary(), indent=2))
            return 0
        if args.command == "list-cases":
            print("SIMULATED cases: " + ", ".join(CASE_NAMES))
            return 0
        if args.command == "export-replays":
            args.output.mkdir(parents=True, exist_ok=True)
            for case in CASE_NAMES:
                (args.output / f"{case}.json").write_text(make_replay(case).model_dump_json(indent=2), encoding="utf-8")
            print(f"Saved six SIMULATED replay inputs: {args.output.resolve()}")
            print("Filenames label cases for humans; these labels are not sent to the investigator.")
            return 0
        if args.command == "validate-demo":
            from water_diagnostics.demo_validation import validate_demo
            summary = validate_demo(mode=args.mode, output=args.output)
            print(f"Local policy: {summary['baseline_passed']}/3; hosted: {summary['hosted_passed']}/{summary['hosted_evaluated']} evaluated reports matched.")
            print(f"New API requests: {summary['new_requests']}; token-cost estimate: ${summary['new_reported_cost_estimate_usd']:.6f}; conservative reservations: ${summary['new_conservative_accounted_usd']:.6f} / $0.04.")
            print(f"Saved: {(args.output / 'comparison.md').resolve()}")
            print(summary["limitation"])
            return 0 if summary["baseline_passed"] == 3 and summary["hosted_passed"] == 3 else 2
        if args.command == "run" and args.resume_report:
            retry_stem = args.resume_report.stem + "-retry"
            if any((args.output / (retry_stem + suffix)).exists() for suffix in (".json", ".md")):
                raise ModelClientError("Retry output already exists. Resume from the latest incomplete report to preserve earlier attempts; no request sent.")
        if args.command == "check-connection" or args.mode == "nebius":
            client = NebiusClient(load_settings())
        if args.command == "check-connection":
            client.ping()
            print("Nebius connection verified with one short request. Credentials and response text omitted.")
            return 0

        if args.command == "run-river":
            print(f"Historical river investigation; source=REAL_RIVER_SENSOR_DATA; mode={args.mode}")
            report = investigate_river(args.input, args.at, client, progress=print)
            paths = save_river_report(report, args.output)
            print(f"Conclusion: {report.conclusion}; status={report.investigation_status}")
            if report.investigation_status == "incomplete":
                print(f"Stopped: {report.uncertainty[-1]}")
            else:
                print("The workflow completed; the physical cause remains unresolved without independent evidence.")
            for path in paths:
                print(f"Saved: {path.resolve()}")
            print("Operator actions are requested, not performed. Water safety is not determined.")
            return 0 if report.investigation_status == "complete" else 2

        def investigate(replay, progress=None):
            return investigate_nebius(replay, client, progress) if client else investigate_offline(replay, progress)

        if args.command == "run":
            print(f"SIMULATED investigation; mode={args.mode}")
            replay = make_replay(args.case, args.seed)
            if args.resume_report:
                try:
                    previous = IncidentReport.model_validate_json(args.resume_report.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raise ModelClientError("Cannot read a valid saved incident report; no request sent.") from None
                report = investigate_nebius(replay, client, progress=print, resume_report=previous)
                stem = args.resume_report.stem + "-retry"
            else:
                report = investigate(replay, progress=print)
                stem = f"{report.incident['incident_id']}-{args.mode}"
            paths = save_report(report, args.output, stem)
            print(f"Conclusion: {report.conclusion.value}; status={report.investigation_status}")
            if report.investigation_status == "incomplete":
                print(f"Stopped: {report.uncertainty[-1]}")
            for path in paths:
                print(f"Saved: {path.resolve()}")
            print("Operator actions are requested, not performed. Water safety is not determined.")
            return 0 if report.investigation_status == "complete" else 2
        summary = evaluate(investigate)
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / f"evaluation-{args.mode}.json"
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Synthetic smoke checks: {summary['passed']}/{summary['total']} passed")
        print(f"Insufficient evidence cases: {summary['insufficient_evidence_passed']}/{summary['insufficient_evidence_total']} passed")
        print(summary["limitation"])
        print(f"Saved: {path.resolve()}")
        return 0 if summary["passed"] == summary["total"] else 2
    except RecoveryError as error:
        print(f"Cannot run recovery simulation: {error}", file=sys.stderr)
        return 2
    except DatasetError as error:
        print(f"Dataset operation failed: {error}", file=sys.stderr)
        return 2
    except (ModelClientError, BudgetError) as error:
        print(f"Cannot run hosted inference: {error}", file=sys.stderr)
        return 2
    finally:
        if client:
            client.close()
            if client.budget:
                try:
                    summary = client.budget.summary()
                    print(f"Local token-cost estimate: ${summary['reported_cost_estimate_usd']:.6f}; "
                          f"conservative guard total: ${summary['conservative_accounted_usd']:.6f} / ${summary['project_cap_usd']:.2f}.")
                    print("This is a local estimate; the Nebius console shows the actual account balance.")
                except BudgetError:
                    print("Local usage ledger needs review before another paid call.")


if __name__ == "__main__":
    raise SystemExit(main())
