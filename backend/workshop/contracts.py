# SPDX-License-Identifier: Apache-2.0
"""Domain contracts, not a replacement telemetry wire envelope.

Acquisition times are caller-supplied acquisition-clock seconds, or None when
not known. Observation times are source occurrence times and are never used
as acquisition clocks. There is no I/O or globally comparable source revision.
"""
from dataclasses import dataclass, field
from typing import Any
import math


def timestamp(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Time must be a finite acquisition-clock value')
    return value


@dataclass(frozen=True, order=True)
class ExecutionKey:
    runtime: str
    native_id: str


@dataclass(frozen=True, order=True)
class TaskKey:
    source_instance: str
    namespace: str
    native_id: str


@dataclass(frozen=True)
class Observation:
    native: Any
    mapped: Any
    mapping_version: str
    source: str
    feed: str
    observed_at: float | None
    supported: bool = True
    evidence_class: str = 'runtime_observed'

    def __post_init__(self):
        if self.observed_at is not None:
            timestamp(self.observed_at)
        if not all((self.mapping_version, self.source, self.feed)):
            raise ValueError('Observations require mapping and source provenance')


@dataclass(frozen=True)
class FeedPolicy:
    expected_interval: float
    stale_after: float
    lost_after: float

    def __post_init__(self):
        for value in (self.expected_interval, self.stale_after, self.lost_after):
            timestamp(value)
        if not 0 < self.expected_interval <= self.stale_after < self.lost_after:
            raise ValueError('Feed deadlines must accommodate acquisition interval')


@dataclass(frozen=True)
class AlarmRule:
    name: str
    group: str
    cause: str
    consequence: str
    action: str
    response_time: str
    scope: str
    priority: str
    owner: str
    on_delay: float = 0
    off_delay: float = 0
    # Boolean observation-age conditions use separate on/off delays, not
    # numeric hysteresis. Keep this explicit in the rationalisation record.
    deadband: str = 'boolean condition; on/off delays'
    suppression_rule: str = 'explicit configured condition only'
    setpoint: str = 'feed stale deadline'

    def __post_init__(self):
        required = (self.name, self.group, self.cause, self.consequence, self.action,
                    self.response_time, self.scope, self.priority, self.owner,
                    self.deadband, self.suppression_rule, self.setpoint)
        if not all(isinstance(v, str) and v.strip() for v in required):
            raise ValueError('Alarm must be rationalised before enabling')
        if timestamp(self.on_delay) < 0 or timestamp(self.off_delay) < 0:
            raise ValueError('Alarm delays cannot be negative')


@dataclass
class Execution:
    key: ExecutionKey
    role: str
    session: str
    parent: ExecutionKey | None
    task: TaskKey | None
    lifecycle: Observation
    acquired_at: float | None
    observations: list[Observation] = field(default_factory=list)
    discrepancies: list[dict] = field(default_factory=list)
    # Permanent per-identity diagnostic indices survive retirement/restart.
    observation_ids: list[int] = field(default_factory=list)
    next_observation_id: int = 0
    protected_observation_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class Ambiguity:
    candidates: tuple[ExecutionKey, ...]
    reason: str
