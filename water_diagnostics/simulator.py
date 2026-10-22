"""Reproducible simulated replays. No plant connection or physical measurements."""

from datetime import datetime, timedelta, timezone
from random import Random
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sample(Record):
    timestamp: AwareDatetime
    value: float | None = Field(default=None, allow_inf_nan=False, ge=0)
    quality: Literal["good", "invalid"] = "good"


class DeviceStatus(Record):
    timestamp: AwareDatetime
    online: bool
    fault_codes: tuple[str, ...] = ()
    last_calibration: AwareDatetime | None = None


class MaintenanceEvent(Record):
    start: AwareDatetime
    end: AwareDatetime
    activity: Literal["sensor_cleaning", "calibration"]
    record_status: Literal["recorded_complete"] = "recorded_complete"


class RelatedSignal(Record):
    instrument_id: str
    role: Literal["independent_outlet_turbidity", "filter_differential_pressure"]
    unit: Literal["NTU", "bar"]
    samples: tuple[Sample, ...]


class Replay(Record):
    source: Literal["SIMULATED"] = "SIMULATED"
    incident_id: str
    observed_at: AwareDatetime
    sensor_id: str = "SIM-FILTER-01-TURBIDITY"
    alarm_description: str = "Simulated filter outlet turbidity / data-quality alarm"
    # Demonstration settings only; these are not regulatory or plant limits.
    alarm_threshold_ntu: float = Field(default=0.3, gt=0)
    expected_interval_seconds: int = Field(default=60, gt=0)
    samples: tuple[Sample, ...]
    device: DeviceStatus | None
    maintenance_log_available: bool
    maintenance_events: tuple[MaintenanceEvent, ...] = ()
    related_signals: tuple[RelatedSignal, ...] = ()

    def incident_context(self) -> dict:
        """Only the trigger is initially visible. Tools reveal the evidence."""
        return {
            "source": self.source,
            "incident_id": self.incident_id,
            "observed_at": self.observed_at.isoformat(),
            "sensor_id": self.sensor_id,
            "alarm_description": self.alarm_description,
            "demonstration_alarm_threshold_ntu": self.alarm_threshold_ntu,
        }


CASE_NAMES = ("normal", "frozen", "communication_loss", "maintenance", "process_change", "insufficient")


def make_replay(case: str, seed: int = 0) -> Replay:
    """Generate 31 one-minute samples on a fixed simulated UTC timeline.

    Case names are for humans selecting fixtures. They are never included in
    Replay, tool results, or model messages. Ground truth lives in evaluation.py.
    """
    if case not in CASE_NAMES:
        raise ValueError(f"Unknown replay case. Choose from {', '.join(CASE_NAMES)}.")
    rng = Random(seed)
    now = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)
    timestamps = [now - timedelta(minutes=30 - i) for i in range(31)]
    baseline = [round(0.1 + rng.uniform(-0.015, 0.015), 3) for _ in timestamps]
    values = list(baseline)
    reference = [round(0.1 + rng.uniform(-0.012, 0.012), 3) for _ in timestamps]
    pressure = [round(0.25 + rng.uniform(-0.01, 0.01), 3) for _ in timestamps]
    device = DeviceStatus(timestamp=now, online=True, last_calibration=now - timedelta(days=7))
    events: tuple[MaintenanceEvent, ...] = ()
    log_available = True

    if case == "normal":
        # A brief historical crossing has already returned to baseline.
        values[22] = 0.36
    elif case == "frozen":
        values[22:] = [round(0.72 + seed % 3 * 0.01, 3)] * 9
        device = device.model_copy(update={"fault_codes": ("SAMPLE_AND_HOLD",)})
    elif case == "communication_loss":
        values = values[:19]
        values[-1] = 0.74
        device = device.model_copy(update={"timestamp": timestamps[18], "online": False})
    elif case == "maintenance":
        values[22:25] = [0.83, 0.62, 0.38]
        events = (MaintenanceEvent(start=now - timedelta(minutes=10),
                                   end=now - timedelta(minutes=6), activity="sensor_cleaning"),)
    elif case in ("process_change", "insufficient"):
        values[22:] = [round(0.78 + rng.uniform(-0.035, 0.035), 3) for _ in range(9)]
        if case == "process_change":
            reference[22:] = [round(0.76 + rng.uniform(-0.025, 0.025), 3) for _ in range(9)]
            pressure[22:] = [round(0.57 + rng.uniform(-0.015, 0.015), 3) for _ in range(9)]
        else:
            log_available = False

    def series(numbers: list[float]) -> tuple[Sample, ...]:
        return tuple(Sample(timestamp=t, value=v) for t, v in zip(timestamps, numbers))

    related = (
        RelatedSignal(instrument_id="SIM-OUTLET-REFERENCE", role="independent_outlet_turbidity",
                      unit="NTU", samples=series(reference)),
        RelatedSignal(instrument_id="SIM-FILTER-DP", role="filter_differential_pressure",
                      unit="bar", samples=series(pressure)),
    ) if case != "insufficient" else ()
    return Replay(
        incident_id=f"SIM-{CASE_NAMES.index(case) + 1:03d}-{seed:03d}",
        observed_at=now, samples=series(values), device=device,
        maintenance_log_available=log_available, maintenance_events=events,
        related_signals=related,
    )
