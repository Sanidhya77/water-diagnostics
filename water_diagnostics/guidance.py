"""Operator-requested Tavily references, never diagnostic evidence or model input."""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from water_diagnostics.config import PROJECT_ROOT, Settings, load_settings


DOMAINS = ("usgs.gov", "epa.gov", "in-situ.com")
MAX_PROJECT_CREDITS = 3
QUERIES = {
    "river": "USGS continuous water quality turbidity sensor fouling cleaning calibration independent quality assurance guidance",
    "device": "USGS continuous water quality monitoring telemetry data gaps sensor maintenance quality assurance guidance",
    "plant": "EPA turbidity monitoring independent measurement instrument calibration quality assurance guidance",
}


class GuidanceError(RuntimeError):
    """Displayable error that never includes keys or raw provider responses."""


def guidance_topic(choice: dict) -> str:
    return "river" if choice["source"] == "river" else ("device" if choice["case"] == "communication_loss" else "plant")


def _safe_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return bool(url.scheme == "https" and not url.username and not url.password
                    and url.port in (None, 443) and url.hostname
                    and any(url.hostname == domain or url.hostname.endswith("." + domain) for domain in DOMAINS))
    except (TypeError, ValueError, AttributeError):
        return False


class GuidanceService:
    def __init__(self, path: Path | None = None, settings: Settings | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.path = path or PROJECT_ROOT / "reports" / "tavily-guidance.json"
        self.settings = settings
        self.transport = transport

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "requests": [], "cache": {}}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state["version"] != 1 or not isinstance(state["requests"], list) or not isinstance(state["cache"], dict):
                raise ValueError()
            for row in state["requests"]:
                if type(row["accounted_credits"]) is not int or not 1 <= row["accounted_credits"] <= 100:
                    raise ValueError()
            return state
        except (OSError, ValueError, TypeError, KeyError):
            raise GuidanceError("The local Tavily usage record needs review; no search was sent.") from None

    def _write(self, state):
        try:
            self.path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            raise GuidanceError("Could not save the Tavily usage record. Preserve it before another search.") from None

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError:
            raise GuidanceError("A guidance lookup is already running. Wait before trying again.") from None
        try:
            with handle:
                yield
        finally:
            lock.unlink()

    def _cached(self, state, topic):
        result = state["cache"].get(topic)
        if not isinstance(result, dict):
            return None
        try:
            retrieved = datetime.fromisoformat(result["retrieved_at"])
            if retrieved.tzinfo is None or not timedelta(0) <= datetime.now(timezone.utc) - retrieved < timedelta(hours=24):
                return None
            documents = result["documents"]
            if (not isinstance(documents, list) or len(documents) > 3
                    or any(not isinstance(d, dict) or not _safe_url(d.get("url"))
                           or not isinstance(d.get("title"), str) or not isinstance(d.get("excerpt"), str)
                           for d in documents)):
                return None
            return {**result, "cached": True}
        except (ValueError, KeyError, TypeError):
            return None

    def cached(self, topic):
        if topic not in QUERIES:
            raise GuidanceError("Choose an available guidance topic.")
        return self._cached(self._read(), topic)

    def lookup(self, topic: str) -> dict:
        if topic not in QUERIES:
            raise GuidanceError("Choose an available guidance topic.")
        # Hold the exclusive lock through the response, so two browser tabs
        # cannot pay twice before the first result reaches the shared cache.
        with self._locked():
            state = self._read()
            cached = self._cached(state, topic)
            if cached is not None:
                return cached
            if sum(r["accounted_credits"] for r in state["requests"]) + 1 > MAX_PROJECT_CREDITS:
                raise GuidanceError("The three-credit Tavily development guard is reached. Cached sources remain available; no search was sent.")
            settings = self.settings or load_settings()
            key = settings.tavily_api_key.get_secret_value().strip()
            if not key:
                raise GuidanceError("Add TAVILY_API_KEY to the local .env file to look up guidance. No search was sent.")
            now = datetime.now(timezone.utc).isoformat()
            row = {"id": uuid4().hex, "topic": topic, "started_at": now,
                   "status": "reserved_usage_unknown", "accounted_credits": 1, "reported_credits": None}
            state["requests"].append(row)
            self._write(state)
            payload = {"query": QUERIES[topic], "search_depth": "basic", "max_results": 3,
                "include_domains": list(DOMAINS), "auto_parameters": False,
                "include_answer": False, "include_raw_content": False, "include_usage": True}
            try:
                with httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=False,
                                  transport=self.transport) as client:
                    response = client.post("https://api.tavily.com/search", json=payload,
                                           headers={"Authorization": "Bearer " + key})
            except httpx.HTTPError:
                raise GuidanceError("Tavily did not return a usable response. No automatic retry; its credit reservation is retained.") from None
            if response.status_code != 200:
                raise GuidanceError(f"Tavily returned HTTP {response.status_code}. Check the key and Tavily account credits; no automatic retry.")
            try:
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                    raise ValueError()
                usage = body.get("usage")
                reported = usage.get("credits") if isinstance(usage, dict) else None
                if type(reported) is int and 0 <= reported <= 100:
                    row.update(reported_credits=reported, accounted_credits=max(1, reported), status="usage_reported")
                else:
                    reported = None
                self._write(state)
                documents = []
                for item in body["results"]:
                    if (not isinstance(item, dict) or not _safe_url(item.get("url"))
                            or not isinstance(item.get("title"), str) or not isinstance(item.get("content"), str)):
                        continue
                    documents.append({"reference_id": f"D{len(documents)+1:02d}",
                        "title": item["title"][:200], "url": item["url"],
                        "domain": urlsplit(item["url"]).hostname,
                        "excerpt": item["content"][:300]})
                    if len(documents) == 3:
                        break
            except (ValueError, TypeError, KeyError):
                raise GuidanceError("Tavily returned an unexpected result. No source text was treated as instructions or diagnostic evidence.") from None
            result = {"topic": topic, "query": QUERIES[topic], "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "documents": documents, "cached": False, "provider": "Tavily", "reported_credits": reported,
                "accounted_project_credits": sum(r["accounted_credits"] for r in state["requests"]),
                "project_credit_limit": MAX_PROJECT_CREDITS,
                "limitation": "Current background references, not evidence from the historical replay. These sources are not sent to the diagnostic model."}
            state["cache"][topic] = result
            self._write(state)
            return result
