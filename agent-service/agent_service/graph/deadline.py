from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class DeadlineExceeded(TimeoutError):
    pass


@dataclass(frozen=True)
class Deadline:
    at: datetime

    @classmethod
    def from_timeout(cls, now: datetime, timeout_ms: int, maximum_ms: int) -> "Deadline":
        bounded = min(maximum_ms, timeout_ms)
        return cls(now.astimezone(UTC) + timedelta(milliseconds=bounded))

    def remaining_seconds(self, now: datetime | None = None) -> float:
        current = now or datetime.now(UTC)
        return max(0.0, (self.at - current).total_seconds())

    def require_remaining(self, now: datetime | None = None, minimum_seconds: float = 0.0) -> None:
        if self.remaining_seconds(now) <= minimum_seconds:
            raise DeadlineExceeded("deadline exceeded")
