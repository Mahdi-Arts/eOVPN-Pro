"""Session-scoped speed-test state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SpeedMeasurement:
    """One immutable measurement for a configuration in the current session."""

    config_id: str
    latency_ms: float | None
    status: str
    measured_at: datetime
    test_generation: int
    error: str | None = None

    @classmethod
    def from_result(
        cls,
        config_id: str,
        latency_ms: float | None,
        generation: int,
        *,
        error: str | None = None,
        measured_at: datetime | None = None,
    ) -> SpeedMeasurement:
        status = "measured" if latency_ms is not None else ("error" if error else "unreachable")
        return cls(
            config_id=str(config_id),
            latency_ms=float(latency_ms) if latency_ms is not None else None,
            status=status,
            measured_at=measured_at or datetime.now(timezone.utc),
            test_generation=int(generation),
            error=error,
        )


@dataclass
class ConnectionAttempt:
    """Mutable lifecycle record for one Auto-Connect candidate."""

    config_id: str
    started_at: datetime
    timeout_seconds: float
    finished_at: datetime | None = None
    elapsed_seconds: float = 0.0
    result: str = "pending"
    error_code: str | None = None
    error_message: str | None = None

    @property
    def error(self) -> str | None:
        """Backward-compatible alias for the user-facing error message."""
        return self.error_message


class SpeedTestSnapshot:
    """Session snapshot used by UI and controllers, independent of GTK."""

    def __init__(self) -> None:
        self._generation = 0
        self._measurements: dict[str, SpeedMeasurement] = {}

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def measurements(self) -> Mapping[str, SpeedMeasurement]:
        return self._measurements.copy()

    def replace(self, results: Mapping[str, float | None]) -> int:
        """Replace the current run without mutating prior measurement objects."""
        self._generation += 1
        generation = self._generation
        self._measurements = {
            str(config_id): SpeedMeasurement.from_result(config_id, latency, generation)
            for config_id, latency in results.items()
        }
        return generation

    def get(self, config_id: str) -> SpeedMeasurement | None:
        return self._measurements.get(str(config_id))

    def latency_map(self) -> dict[str, float | None]:
        return {config_id: measurement.latency_ms for config_id, measurement in self._measurements.items()}
