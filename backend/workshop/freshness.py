# SPDX-License-Identifier: Apache-2.0
"""Per-feed successful-acquisition clocks; transport is never process progress."""
from dataclasses import dataclass
from .contracts import FeedPolicy, timestamp


def quality(acquired_at: float | None, now: float, policy: FeedPolicy) -> str:
    timestamp(now)
    if acquired_at is None or now < acquired_at:
        return 'unknown'
    age = now - acquired_at
    if age >= policy.lost_after:
        return 'disconnected'
    if age >= policy.stale_after:
        return 'stale'
    return 'fresh'


@dataclass
class Feed:
    policy: FeedPolicy
    group: str
    last_acquired_at: float | None = None

    def acquire(self, at: float):
        timestamp(at)
        if self.last_acquired_at is not None and at < self.last_acquired_at:
            raise ValueError('Acquisition clock regressed')
        self.last_acquired_at = at

    def quality(self, now: float) -> str:
        return quality(self.last_acquired_at, now, self.policy)
