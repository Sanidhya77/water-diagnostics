"""Short-lived, memory-only visitor credentials. Never fall back to owner keys."""

from dataclasses import dataclass, field
from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from uuid import uuid4

from pydantic import SecretStr

from water_diagnostics.config import Settings
from water_diagnostics.model_client.budget import BudgetError, PRICING_SOURCE, reservation_units


SESSION_SECONDS = 30 * 60
SESSION_CAP_UNITS = 25_000_000  # $0.25 per connection; not a durable account cap.
RUN_CAP_UNITS = 2_000_000  # $0.02 per investigation.
UNITS_PER_USD = 100_000_000
COOKIE_NAME = "__Host-water-key"


@dataclass(repr=False)
class VisitorSession:
    settings: Settings
    expires: float
    clock: object = field(default=monotonic, repr=False)
    lock: object = field(default_factory=Lock, repr=False)
    revoked: bool = False
    rows: dict = field(default_factory=dict, repr=False)

    def valid(self):
        return not self.revoked and self.clock() < self.expires

    def revoke(self):
        with self.lock:
            self.revoked = True
            self.settings = Settings()  # Drop the stored reference to the key.

    def guard(self):
        return VisitorCostGuard(self)

    def summary(self):
        with self.lock:
            return {"project_cap_usd": 0.25, "per_run_cap_usd": 0.02,
                    "requests": len(self.rows),
                    "requests_with_usage": sum(row["estimate"] is not None for row in self.rows.values()),
                    "reported_cost_estimate_usd": sum(row["estimate"] or 0 for row in self.rows.values()) / UNITS_PER_USD,
                    "conservative_accounted_usd": sum(row["accounted"] for row in self.rows.values()) / UNITS_PER_USD,
                    "pricing_source": PRICING_SOURCE,
                    "limitation": "Visitor-funded, temporary $0.25 connection guard / $0.02 per run. Resets after expiry, reconnect or server restart; not a Nebius account or invoice cap."}


class VisitorSessions:
    def __init__(self, *, clock=monotonic, maximum=64):
        self.clock, self.maximum = clock, maximum
        self.lock = Lock()
        self.sessions = {}

    def _prune(self):
        for token, session in list(self.sessions.items()):
            if not session.valid():
                session.revoke()
                del self.sessions[token]

    def connect(self, values, old_token=None):
        if not isinstance(values, dict) or set(values) != {"nebius_api_key"}:
            raise ValueError("Enter one Nebius API key. It is used only for your temporary connection.")
        key = values["nebius_api_key"]
        if not isinstance(key, str) or not 20 <= len(key) <= 512 or any(not 33 <= ord(c) <= 126 for c in key):
            raise ValueError("Enter a valid Nebius key without spaces (20–512 characters).")
        with self.lock:
            self._prune()
            # Replacing a connection first removes that browser's previous key.
            old = self.sessions.pop(old_token, None)
            if old:
                old.revoke()
            if len(self.sessions) >= self.maximum:
                raise ValueError("Temporary AI connections are full. Saved reports and free checks are available; try later.")
            token = token_urlsafe(32)
            self.sessions[token] = VisitorSession(Settings(nebius_api_key=SecretStr(key)),
                                                  self.clock() + SESSION_SECONDS, clock=self.clock)
            return token

    def get(self, token):
        with self.lock:
            self._prune()
            return self.sessions.get(token)

    def expire(self):
        with self.lock:
            self._prune()

    def clear(self):
        with self.lock:
            for session in self.sessions.values():
                session.revoke()
            self.sessions.clear()

    def disconnect(self, token):
        with self.lock:
            session = self.sessions.pop(token, None)
            if session:
                session.revoke()


class VisitorCostGuard:
    def __init__(self, session):
        self.session = session
        self.run_units = 0

    def reserve(self, model, payload):
        units = reservation_units(model, payload)
        with self.session.lock:
            if not self.session.valid():
                raise BudgetError("Your API-key connection expired or was disconnected. Reconnect to start a new model call.")
            total = sum(row["accounted"] for row in self.session.rows.values())
            if total + units > SESSION_CAP_UNITS or self.run_units + units > RUN_CAP_UNITS:
                raise BudgetError("Temporary visitor guard reached ($0.25 per connection / $0.02 per investigation). No new call sent; saved results and free checks remain available.")
            identifier = uuid4().hex
            self.session.rows[identifier] = {"accounted": units, "estimate": None}
            self.run_units += units
            return identifier

    def record_usage(self, identifier, usage):
        if not isinstance(usage, dict):
            return
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if any(type(v) is not int or v < 0 for v in (prompt, completion)):
            return
        estimate = prompt * 6 + completion * 24
        with self.session.lock:
            row = self.session.rows[identifier]
            previous = row["accounted"]
            row.update(estimate=estimate, accounted=max(previous, estimate))
            self.run_units += row["accounted"] - previous

    def summary(self):
        return self.session.summary()
