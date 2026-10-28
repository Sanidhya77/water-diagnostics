"""Replay operator interface with explicit local and free public-demo modes."""

import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from water_diagnostics.config import PROJECT_ROOT, Settings, load_settings
from water_diagnostics.guidance import GuidanceError, GuidanceService, guidance_topic
from water_diagnostics.incident_reports.reporting import render_markdown, save_report
from water_diagnostics.incident_reports.schema import IncidentReport
from water_diagnostics.investigator import investigate_nebius, investigate_offline
from water_diagnostics.model_client.budget import BudgetError, CostGuard
from water_diagnostics.model_client.nebius import ModelClientError, NebiusClient
from water_diagnostics.river_data import DatasetError, river_snapshot, utc_time
from water_diagnostics.river_investigator import (
    CAUSE_WORDING, RiverReport, investigate_river, render_river_report, save_river_report,
)
from water_diagnostics.simulator import CASE_NAMES, make_replay
from water_diagnostics.recovery import CASES as RECOVERY_CASES, RecoveryError, render_recovery, run_recovery_demo, save_recovery


DEFAULT_AT = "2024-04-03T00:00:00Z"
RIVER_REPLAYS = {
    "udall-2024-04-01": {"label": "Apr 1–7 · cleaning visit", "min": "2024-04-01T00:00", "max": "2024-04-07T23:59", "before": "2024-04-02T22:00:00Z", "after": DEFAULT_AT, "before_label": "Before visit", "after_label": "After visit", "hours": 6},
    "udall-2024-04-08": {"label": "Apr 8–14 · recorded data gap", "min": "2024-04-08T00:00", "max": "2024-04-14T23:59", "before": "2024-04-10T00:00:00Z", "after": "2024-04-12T00:00:00Z", "before_label": "Before gap", "after_label": "After gap", "hours": 48},
}
CASE_LABELS = {
    "normal": "Brief excursion", "frozen": "Held sensor reading",
    "communication_loss": "Missing telemetry", "maintenance": "Maintenance disturbance",
    "process_change": "Corroborating process change", "insufficient": "Ambiguous evidence",
}
WEB_ROOT = Path(__file__).parent / "web"


def selection(values: dict) -> dict:
    if not isinstance(values, dict) or set(values) - {"source", "at", "case", "mode", "dataset"}:
        raise ValueError("Choose an available replay and investigation mode.")
    source = values.get("source", "river")
    mode = values.get("mode", "offline")
    if source not in ("river", "simulated") or mode not in ("offline", "nebius"):
        raise ValueError("Choose an available replay and investigation mode.")
    case = values.get("case", "frozen")
    if case not in CASE_NAMES:
        raise ValueError("Choose an available simulated case.")
    dataset = values.get("dataset", "udall-2024-04-01")
    if not isinstance(dataset, str) or dataset not in RIVER_REPLAYS:
        raise ValueError("Choose one of the two prepared river weeks.")
    at = utc_time(values.get("at", RIVER_REPLAYS[dataset]["after"])).isoformat()
    return {"source": source, "at": at, "case": case, "mode": mode, "dataset": dataset}


def report_view(report: IncidentReport | RiverReport) -> dict:
    river = isinstance(report, RiverReport)
    hypotheses = []
    for cause in report.possible_causes:
        if river:
            hypotheses.append({"name": cause.cause, "text": CAUSE_WORDING[cause.cause],
                "support": cause.relevant_evidence_ids, "conflict": []})
        else:
            hypotheses.append({"name": cause.cause.value, "text": cause.interpretation,
                "support": cause.supporting_evidence_ids, "conflict": cause.conflicting_evidence_ids})
    return {"source": report.source, "mode": report.investigation_mode, "model": report.model,
        "status": report.investigation_status, "conclusion": str(report.conclusion),
        "observations": [e.model_dump(mode="json") for e in report.observations],
        "attempts": [a.model_dump() for a in report.tool_attempts], "hypotheses": hypotheses,
        "uncertainty": report.uncertainty, "boundaries": report.boundaries,
        "actions": [a.action for a in report.suggested_operator_actions]}


class Dashboard:
    def __init__(self, root: Path = PROJECT_ROOT, public_demo: bool = False):
        self.root = root
        self.public_demo = public_demo
        self.river_directory = root / "data" / "river" / "udall-2024-04-01"
        self.lock = Lock()
        self.jobs: dict[str, dict] = {}
        self.latest: dict[tuple, IncidentReport | RiverReport] = {}
        self.active: str | None = None
        self.recoveries = {}
        self.guidance = GuidanceService(root / "reports" / "tavily-guidance.json", settings=Settings() if public_demo else None)

    @staticmethod
    def key(choice):
        return (choice["source"], choice.get("dataset") if choice["source"] == "river" else None,
                choice["at"] if choice["source"] == "river" else choice["case"], choice["mode"])

    def river_directory_for(self, choice):
        return self.river_directory if choice["dataset"] == "udall-2024-04-01" else self.root / "data/river/udall-2024-04-08"

    def budget(self) -> dict:
        if self.public_demo:
            return {"project_cap_usd": 0, "per_run_cap_usd": 0, "requests": 0,
                    "reported_cost_estimate_usd": 0, "conservative_accounted_usd": 0,
                    "limitation": "Paid provider requests are disabled in this public demonstration."}
        return CostGuard(self.root / "reports" / "nebius-usage.json").summary()

    def cached_report(self, choice):
        with self.lock:
            cached = self.latest.get(self.key(choice))
        if cached is not None:
            return cached
        mode = choice["mode"]
        if choice["source"] == "river":
            stamp = utc_time(choice["at"]).strftime("%Y%m%dT%H%M%SZ")
            names = [f"RIVER-udall-{stamp}-{mode}.json"]
            report_type = RiverReport
        else:
            incident = make_replay(choice["case"]).incident_id
            names = ([f"{incident}-{mode}-retry.json"] if mode == "nebius" else []) + [f"{incident}-{mode}.json"]
            report_type = IncidentReport
        paths = [folder / name for folder in (self.root / "demo_reports", self.root / "reports") for name in names]
        for path in paths:
            try:
                report = report_type.model_validate_json(path.read_text(encoding="utf-8"))
                if (report.investigation_mode == "nebius_model") != (mode == "nebius"):
                    continue
                if isinstance(report, RiverReport):
                    if report.site != "udall" or utc_time(report.observed_at) != utc_time(choice["at"]):
                        continue
                elif report.incident != make_replay(choice["case"]).incident_context():
                    continue
                return report
            except (OSError, ValueError):
                continue
        return None

    def replay(self, choice: dict) -> dict:
        if choice["source"] == "river":
            river_directory = self.river_directory_for(choice)
            snapshot = river_snapshot(river_directory, choice["at"])
            observed = utc_time(snapshot["observed_at"])
            # Only original observations are read. Future points, evaluator flags,
            # corrected values and local archive paths never reach the browser.
            raw = json.loads((river_directory / "observations.json").read_text(encoding="utf-8"))
            points = [{"time": r["timestamp"], "value": r["value"]} for r in raw["records"]
                if r["parameter"] == "Turbidity" and observed - timedelta(hours=48) <= utc_time(r["timestamp"]) <= observed]
            points.sort(key=lambda p: utc_time(p["time"]))
            visits = snapshot["check_maintenance_context"]["recorded_visits_visible_at_replay_clock"]
            events = [{"time": v["visit_time_utc"], "label": "Recorded technician visit"} for v in visits]
            summary = {"latest": snapshot["check_variation"]["latest_ntu"],
                "fresh": snapshot["check_freshness"]["fresh"], "interval_seconds": 900,
                "device_available": False, "visits": len(visits), "independent": False,
                "source_label": "Historical river data", "site": "Udall · Poudre River, Colorado",
                "clock": snapshot["observed_at"], "threshold": None}
        else:
            replay = make_replay(choice["case"])
            points = [{"time": s.timestamp.isoformat(), "value": s.value} for s in replay.samples]
            events = [{"time": e.start.isoformat(), "label": "Recorded maintenance"} for e in replay.maintenance_events]
            latest = replay.samples[-1] if replay.samples else None
            summary = {"latest": latest.value if latest else None,
                "fresh": bool(latest and (replay.observed_at - latest.timestamp).total_seconds() <= 120),
                "interval_seconds": replay.expected_interval_seconds, "device_available": replay.device is not None,
                "visits": len(replay.maintenance_events),
                "independent": any(s.role == "independent_outlet_turbidity" and s.samples for s in replay.related_signals),
                "source_label": "Simulated filter outlet", "site": CASE_LABELS[choice["case"]],
                "clock": replay.observed_at.isoformat(), "threshold": replay.alarm_threshold_ntu}
        # Prefer an existing AI report for the selected replay. Loading is free.
        saved_choice = {**choice, "mode": "nebius"}
        saved = self.cached_report(saved_choice)
        if saved is None:
            saved_choice["mode"] = "offline"
            saved = self.cached_report(saved_choice)
        try:
            guidance = self.guidance.cached(guidance_topic(choice))
        except GuidanceError:
            guidance = None
        return {"selection": choice, "summary": summary, "points": points, "events": events,
            "report": report_view(saved) if saved else None,
            "guidance": guidance,
            "saved_mode": saved_choice["mode"] if saved else None,
            "cases": CASE_LABELS, "river_replays": RIVER_REPLAYS,
            "capabilities": {"public_demo": self.public_demo, "live_inference": not self.public_demo, "reference_lookup": not self.public_demo}}

    def start(self, choice: dict) -> str:
        if self.public_demo and choice["mode"] == "nebius":
            raise ValueError("This public demo uses saved hosted results and free local checks. Fresh inference is available in the downloaded local build.")
        # Validate the replay before starting a thread or creating a paid client.
        self.replay(choice)
        with self.lock:
            if self.active is not None:
                raise ValueError("An investigation is already running. Wait for it to finish.")
            identifier = uuid4().hex
            self.jobs[identifier] = {"id": identifier, "status": "running", "events": [],
                                     "mode": choice["mode"], "result": None, "error": None}
            self.active = identifier
            while len(self.jobs) > 12:
                self.jobs.pop(next(iter(self.jobs)))
        Thread(target=self._run, args=(identifier, choice), daemon=True, name="water-investigation").start()
        return identifier

    def _run(self, identifier: str, choice: dict) -> None:
        client = None
        try:
            if choice["mode"] == "nebius":
                client = NebiusClient(load_settings(), budget=CostGuard(self.root / "reports" / "nebius-usage.json"))

            def progress(message):
                with self.lock:
                    self.jobs[identifier]["events"].append(message)

            directory = self.root / "reports" / "ui" / identifier
            if choice["source"] == "river":
                report = investigate_river(self.river_directory_for(choice), choice["at"], client, progress)
                if not self.public_demo:
                    save_river_report(report, directory)
            else:
                replay = make_replay(choice["case"])
                report = investigate_nebius(replay, client, progress) if client else investigate_offline(replay, progress)
                if not self.public_demo:
                    save_report(report, directory, f"{replay.incident_id}-{choice['mode']}")
            with self.lock:
                self.latest[self.key(choice)] = report
                if self.public_demo:
                    while len(self.latest) > 12:
                        self.latest.pop(next(iter(self.latest)))
                self.jobs[identifier].update(status="finished", result=report_view(report))
        except (DatasetError, ModelClientError, BudgetError) as error:
            with self.lock:
                self.jobs[identifier].update(status="failed", error=str(error))
        except Exception:
            with self.lock:
                self.jobs[identifier].update(status="failed", error="The investigation could not finish. Check the local dataset and report folder.")
        finally:
            if client:
                client.close()
            with self.lock:
                self.active = None

    def job(self, identifier: str) -> dict:
        with self.lock:
            if identifier not in self.jobs:
                raise ValueError("That investigation is not available in this session.")
            return json.loads(json.dumps(self.jobs[identifier]))

    def recovery_demo(self, values: dict) -> dict:
        if (not isinstance(values, dict) or set(values) != {"case"}
                or not isinstance(values["case"], str) or values["case"] not in RECOVERY_CASES):
            raise RecoveryError("Choose one of the two collector-recovery simulations.")
        with self.lock:
            if self.active is not None:
                raise RecoveryError("An investigation is already running. Wait for it to finish.")
            self.active = "recovery"
        try:
            report = run_recovery_demo(values["case"], root=self.root)
            if not self.public_demo:
                save_recovery(report, self.root / "reports" / "recovery")
            with self.lock:
                self.recoveries[report.run_id] = report
                while len(self.recoveries) > 12:
                    self.recoveries.pop(next(iter(self.recoveries)))
            return {"report": report.model_dump(mode="json"),
                    "download_url": "/api/recovery-download?id=" + report.run_id}
        finally:
            with self.lock:
                self.active = None


def make_server(port: int = 8765, app: Dashboard | None = None, *,
                bind_address: str = "127.0.0.1", public_origin: str | None = None) -> ThreadingHTTPServer:
    app = app or Dashboard()
    if bind_address not in ("127.0.0.1", "0.0.0.0") or (bind_address == "0.0.0.0" and not app.public_demo):
        raise ValueError("External binding is supported only for the public demo with paid calls disabled.")
    public_host = None
    if public_origin:
        origin = urlsplit(public_origin)
        if (not app.public_demo or origin.scheme != "https" or not origin.hostname
                or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ("", "/")):
            raise ValueError("Configure the public demo with one plain HTTPS origin.")
        public_origin = public_origin.rstrip("/")
        public_host = origin.netloc

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No URLs, browser input, model bodies or credentials in logs.

        def reply(self, status: int, body, content_type="application/json; charset=utf-8", download=False):
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8") if isinstance(body, dict) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="water-investigation.md"')
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            port = self.server.server_port
            host = self.headers.get("Host")
            return bool(host) and host in (f"127.0.0.1:{port}", f"localhost:{port}", public_host)

        def expected_origin(self):
            return public_origin if public_host and self.headers.get("Host") == public_host else "http://" + self.headers.get("Host", "")

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, {"error": "Open the interface using its configured address."})
                return
            url = urlsplit(self.path)
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/plex-regular.ttf": ("plex-regular.ttf", "font/ttf"),
                     "/plex-semibold.ttf": ("plex-semibold.ttf", "font/ttf"),
                     "/OFL-Plex.txt": ("OFL-Plex.txt", "text/plain; charset=utf-8")}
            try:
                query = parse_qs(url.query, max_num_fields=8)
                if any(len(v) != 1 for v in query.values()):
                    raise ValueError("Use one replay selection at a time.")
                values = {k: v[0] for k, v in query.items()}
                if url.path == "/health":
                    ready = all((app.river_directory / name).is_file() for name in ("observations.json", "context.json"))
                    self.reply(200 if ready else 503, {"status": "ready" if ready else "dataset_unavailable", "public_demo": app.public_demo})
                elif url.path in files:
                    name, content_type = files[url.path]
                    self.reply(200, (WEB_ROOT / name).read_bytes(), content_type)
                elif url.path == "/api/replay":
                    self.reply(200, app.replay(selection(values)))
                elif url.path == "/api/budget":
                    self.reply(200, app.budget())
                elif url.path == "/api/job" and set(values) == {"id"}:
                    self.reply(200, app.job(values["id"]))
                elif url.path == "/api/recovery-download" and set(values) == {"id"}:
                    with app.lock:
                        report = app.recoveries.get(values["id"])
                    if report is None:
                        self.reply(404, {"error": "Run a recovery simulation in this session first."})
                    else:
                        self.reply(200, render_recovery(report).encode("utf-8"), "text/markdown; charset=utf-8", download=True)
                elif url.path == "/api/download":
                    report = app.cached_report(selection(values))
                    if report is None:
                        self.reply(404, {"error": "Run an investigation or load an available saved report first."})
                    else:
                        text = render_river_report(report) if isinstance(report, RiverReport) else render_markdown(report)
                        self.reply(200, text.encode("utf-8"), "text/markdown; charset=utf-8", download=True)
                else:
                    self.reply(404, {"error": "Page not found."})
            except (ValueError, DatasetError, BudgetError):
                self.reply(400, {"error": "This replay is unavailable. Choose a time within the selected prepared river week."})
            except OSError:
                self.reply(503, {"error": "The local files are unavailable. Keep the prepared dataset in this project."})

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    raise ValueError("Choose an available replay.")
                # Consume the bounded body even when rejecting its origin.
                # Closing with unread POST bytes can reset the connection on
                # Windows before the browser receives the rejection response.
                body = self.rfile.read(size)
            except ValueError as error:
                self.reply(400, {"error": str(error)})
                return
            if (not self.valid_host() or self.headers.get("Origin") != self.expected_origin()
                    or self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                self.reply(403, {"error": "Start investigations from this application's own interface."})
                return
            if self.path not in ("/api/investigate", "/api/guidance", "/api/recovery-demo"):
                self.reply(404, {"error": "Page not found."})
                return
            try:
                values = json.loads(body)
                if self.path == "/api/recovery-demo":
                    self.reply(200, app.recovery_demo(values))
                    return
                choice = selection(values)
                if self.path == "/api/guidance":
                    if app.public_demo:
                        raise GuidanceError("Paid reference lookup is disabled in this public demonstration.")
                    app.replay(choice)  # Reject invalid clocks before any search credit is reserved.
                    self.reply(200, app.guidance.lookup(guidance_topic(choice)))
                else:
                    self.reply(202, {"id": app.start(choice)})
            except (ValueError, DatasetError, GuidanceError) as error:
                self.reply(400, {"error": str(error)})
            except OSError:
                self.reply(503, {"error": "The local report could not be saved. Check the project's reports folder before trying again."})

    return ThreadingHTTPServer((bind_address, port), Handler)


def serve(port: int = 8765, *, bind_address: str = "127.0.0.1", public_demo: bool = False,
          public_origin: str | None = None) -> None:
    with make_server(port, Dashboard(public_demo=public_demo), bind_address=bind_address, public_origin=public_origin) as server:
        print(f"Water Diagnostics is ready: {public_origin or f'http://127.0.0.1:{server.server_port}'}", flush=True)
        print("Public demonstration: paid APIs disabled; generated reports last for this server session."
              if public_demo else "Preview and local checks are free. Nemotron and requested Tavily guidance use their separate credit guards.", flush=True)
        print("Press Ctrl+C to stop the interface.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
