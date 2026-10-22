"""Allowlisted, read-only Python checks bound to one simulated incident."""

from datetime import timedelta
from statistics import mean, pstdev

from water_diagnostics.simulator import Replay, Sample


TOOL_DESCRIPTIONS = {
    "check_freshness": "Check sample timestamps, missing intervals and freshness at the replay clock.",
    "check_variation": "Calculate turbidity variation, repeated readings and alarm crossings in Python.",
    "check_device_status": "Read recorded device status, fault codes and calibration date.",
    "check_maintenance_context": "Read available simulated maintenance records and alarm timing.",
    "check_related_measurements": "Read independent outlet and pressure signals, checking their freshness.",
}


def tool_schemas() -> list[dict]:
    return [{"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }} for name, description in TOOL_DESCRIPTIONS.items()]


def _usable(samples: tuple[Sample, ...], replay: Replay) -> list[Sample]:
    return sorted((s for s in samples if s.quality == "good" and s.value is not None
                   and s.timestamp <= replay.observed_at), key=lambda s: s.timestamp)


def _timing(samples: tuple[Sample, ...], replay: Replay) -> dict:
    stamps = [s.timestamp for s in samples]
    latest = max(stamps) if stamps else None
    age = (replay.observed_at - latest).total_seconds() if latest else None
    invalid_order = any(a >= b for a, b in zip(stamps, stamps[1:]))
    future = any(t > replay.observed_at for t in stamps)
    usable = _usable(samples, replay)
    valid_age = (replay.observed_at - usable[-1].timestamp).total_seconds() if usable else None
    missing = sum(max(0, int((b - a).total_seconds() / replay.expected_interval_seconds) - 1)
                  for a, b in zip(sorted(set(stamps)), sorted(set(stamps))[1:]))
    limit = replay.expected_interval_seconds * 2
    latest_quality_good = bool(latest is not None and any(s.timestamp == latest
                              and s.quality == "good" and s.value is not None for s in samples))
    return {
        "sample_count": len(samples), "usable_sample_count": len(usable),
        "latest_timestamp": latest.isoformat() if latest else None,
        "latest_age_seconds": age, "latest_usable_age_seconds": valid_age,
        "freshness_limit_seconds": limit, "missing_intervals": missing,
        "timestamps_out_of_order_or_duplicate": invalid_order, "future_timestamps": future,
        "latest_sample_quality_good": latest_quality_good,
        "fresh": bool(valid_age is not None and 0 <= valid_age <= limit
                      and latest_quality_good and not invalid_order and not future),
    }


class DiagnosticTools:
    def __init__(self, replay: Replay):
        self.replay = replay

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in TOOL_DESCRIPTIONS:
            raise ValueError("Tool is not in the read-only allowlist.")
        if arguments != {}:
            raise ValueError("Diagnostic tools take no arguments; they are bound to this incident.")
        # Only names already checked against the fixed allowlist reach getattr.
        data = getattr(self, name)()
        return {"source": "SIMULATED", "tool": name, "data": data}

    def check_freshness(self) -> dict:
        return _timing(self.replay.samples, self.replay)

    def check_variation(self) -> dict:
        replay = self.replay
        usable = _usable(replay.samples, replay)
        recent = [s for s in usable if s.timestamp >= replay.observed_at - timedelta(minutes=10)]
        baseline = [s.value for s in usable if s.timestamp < replay.observed_at - timedelta(minutes=10)]
        numbers = [s.value for s in recent]
        tail = []
        for sample in reversed(recent):
            if tail and (sample.value != tail[-1].value or
                         (tail[-1].timestamp - sample.timestamp).total_seconds() != replay.expected_interval_seconds):
                break
            tail.append(sample)
        return {
            "unit": "NTU", "window_minutes": 10, "usable_recent_count": len(recent),
            "baseline_mean_ntu": round(mean(baseline), 4) if baseline else None,
            "latest_ntu": usable[-1].value if usable else None,
            "recent_min_ntu": min(numbers) if numbers else None,
            "recent_max_ntu": max(numbers) if numbers else None,
            "recent_stddev_ntu": round(pstdev(numbers), 5) if numbers else None,
            "recent_distinct_values": len(set(numbers)), "trailing_identical_count": len(tail),
            "trailing_identical_minutes": (tail[0].timestamp - tail[-1].timestamp).total_seconds() / 60 if tail else 0,
            "recent_above_threshold_count": sum(v > replay.alarm_threshold_ntu for v in numbers),
            "latest_above_threshold": usable[-1].value > replay.alarm_threshold_ntu if usable else None,
            "demonstration_threshold_ntu": replay.alarm_threshold_ntu,
        }

    def check_device_status(self) -> dict:
        device = self.replay.device
        if device is None:
            return {"available": False}
        age = (self.replay.observed_at - device.timestamp).total_seconds()
        return {"available": True, "record_timestamp": device.timestamp.isoformat(),
                "record_age_seconds": age,
                "status_fresh": 0 <= age <= self.replay.expected_interval_seconds * 2,
                "online": device.online, "fault_codes": list(device.fault_codes),
                "last_calibration_record": device.last_calibration.isoformat() if device.last_calibration else None,
                "calibration_age_days": (self.replay.observed_at - device.last_calibration).total_seconds() / 86400
                if device.last_calibration else None}

    def check_maintenance_context(self) -> dict:
        replay = self.replay
        events = [e for e in replay.maintenance_events
                  if e.start <= replay.observed_at and e.end >= replay.observed_at - timedelta(minutes=30)]
        overlap = sum(any(e.start <= s.timestamp <= e.end for e in events)
                      for s in _usable(replay.samples, replay)
                      if s.value > replay.alarm_threshold_ntu)
        return {"log_available": replay.maintenance_log_available,
                "window_minutes": 30,
                "events": [e.model_dump(mode="json") for e in events] if replay.maintenance_log_available else [],
                "elevated_samples_during_recorded_event": overlap if replay.maintenance_log_available else None,
                "physical_test_executed_by_agent": False}

    def check_related_measurements(self) -> dict:
        replay = self.replay
        signals = []
        for signal in replay.related_signals:
            usable = _usable(signal.samples, replay)
            baseline = [s.value for s in usable if s.timestamp < replay.observed_at - timedelta(minutes=10)]
            recent = [s.value for s in usable if s.timestamp >= replay.observed_at - timedelta(minutes=10)]
            timing = _timing(signal.samples, replay)
            above = sum(v > replay.alarm_threshold_ntu for v in recent) if signal.unit == "NTU" else None
            signals.append({"instrument_id": signal.instrument_id, "role": signal.role, "unit": signal.unit,
                            "fresh": timing["fresh"], "latest_age_seconds": timing["latest_usable_age_seconds"],
                            "latest_value": usable[-1].value if usable else None,
                            "baseline_mean": round(mean(baseline), 4) if baseline else None,
                            "usable_recent_count": len(recent), "recent_above_threshold_count": above,
                            "latest_above_threshold": usable[-1].value > replay.alarm_threshold_ntu
                            if usable and signal.unit == "NTU" else None,
                            "measurement_source": "simulated_recorded_online_instrument"})
        return {"signals": signals, "physical_test_executed_by_agent": False}
