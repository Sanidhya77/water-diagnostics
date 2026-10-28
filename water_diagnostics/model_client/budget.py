"""Local Nano-only cost guard; not a substitute for Nebius account billing.

Rates rechecked against Nebius's public model catalog on 2026-10-28. Reservations use
UTF-8 payload bytes plus framing headroom, maximum output, and a 2x margin.
Only token counters and estimates are saved, never keys, prompts or responses.
"""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from water_diagnostics.config import DEFAULT_MODEL, PROJECT_ROOT


INPUT_USD_PER_MILLION = 0.06
OUTPUT_USD_PER_MILLION = 0.24
PROJECT_CAP_USD = 5.0
RUN_CAP_USD = 0.02
PRICING_SOURCE = "https://tokenfactory.nebius.com/api/public/models_info"


class BudgetError(RuntimeError):
    pass


class CostGuard:
    def __init__(self, path: Path | None = None, project_cap: float = PROJECT_CAP_USD,
                 run_cap: float = RUN_CAP_USD):
        self.path = path or PROJECT_ROOT / "reports" / "nebius-usage.json"
        self.project_cap = project_cap
        self.run_cap = run_cap
        self.run_accounted = 0.0

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError:
            raise BudgetError("The local budget ledger is locked by another run; no request sent.") from None
        try:
            with handle:
                yield
        finally:
            lock.unlink()

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "pricing_checked_on": "2026-10-28",
                    "pricing_source": PRICING_SOURCE, "requests": []}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state["version"] != 1 or not isinstance(state["requests"], list):
                raise ValueError()
            for row in state["requests"]:
                amount = row["accounted_usd"]
                if not isinstance(amount, (int, float)) or not 0 <= amount < 100:
                    raise ValueError()
            return state
        except (ValueError, KeyError, TypeError, OSError):
            raise BudgetError("The local budget ledger is unreadable; no new request sent. Preserve it for review.") from None

    def _write(self, state: dict) -> None:
        # The exclusive lock prevents concurrent writers. An interrupted write
        # leaves an unreadable ledger, which blocks subsequent paid requests.
        try:
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            raise BudgetError("Could not save the local budget ledger; no further request should be sent.") from None

    def reserve(self, model: str, payload: dict) -> str:
        if model != DEFAULT_MODEL:
            raise BudgetError("Cost guard pricing is verified only for the configured Nano model; no request sent.")
        output = payload.get("max_tokens")
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if not isinstance(output, int) or not 1 <= output <= 4096 or size > 60000:
            raise BudgetError("Request exceeds the small-test input/output limit; no request sent.")
        reservation = round(2 * ((size + 2048) * INPUT_USD_PER_MILLION
                                + output * OUTPUT_USD_PER_MILLION) / 1_000_000, 8)
        with self._locked():
            state = self._read()
            total = sum(r["accounted_usd"] for r in state["requests"])
            if total + reservation > self.project_cap or self.run_accounted + reservation > self.run_cap:
                raise BudgetError(f"Local spending guard reached (${self.project_cap:.2f} project / ${self.run_cap:.2f} per run); no request sent.")
            identifier = uuid4().hex
            state["requests"].append({"id": identifier, "model": model,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "reserved_usage_unknown", "accounted_usd": reservation,
                "reservation_usd": reservation, "prompt_tokens": None, "completion_tokens": None,
                "estimated_usd": None})
            self._write(state)
            self.run_accounted += reservation
        return identifier

    def record_usage(self, identifier: str, usage: dict | None) -> None:
        # Unknown usage (including timeout) keeps the full reservation charged
        # against the guard. A retry cannot assume the earlier call was free.
        if not isinstance(usage, dict):
            return
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if any(type(v) is not int or v < 0 for v in (prompt, completion)):
            return
        estimate = round((prompt * INPUT_USD_PER_MILLION + completion * OUTPUT_USD_PER_MILLION) / 1_000_000, 8)
        with self._locked():
            state = self._read()
            row = next(r for r in state["requests"] if r["id"] == identifier)
            previous = row["accounted_usd"]
            # Be conservative: never refund an unverified reservation solely
            # because a provider reports fewer tokens than the local estimate.
            row.update(status="usage_reported", prompt_tokens=prompt, completion_tokens=completion,
                       estimated_usd=estimate, accounted_usd=max(previous, estimate))
            self.run_accounted += row["accounted_usd"] - previous
            self._write(state)

    def summary(self) -> dict:
        with self._locked():
            state = self._read()
        rows = state["requests"]
        return {"project_cap_usd": self.project_cap, "per_run_cap_usd": self.run_cap,
                "requests": len(rows), "requests_with_usage": sum(r["estimated_usd"] is not None for r in rows),
                "reported_cost_estimate_usd": round(sum(r["estimated_usd"] or 0 for r in rows), 8),
                "conservative_accounted_usd": round(sum(r["accounted_usd"] for r in rows), 8),
                "pricing_source": PRICING_SOURCE,
                "limitation": "Local estimates for this project only; excludes other keys/apps, historical usage, taxes and price changes. Check Nebius billing for the account balance."}
