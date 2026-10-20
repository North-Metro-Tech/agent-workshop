# SPDX-License-Identifier: Apache-2.0
"""Deterministic in-memory reduction of already-mapped synthetic observations.

No collector imports, database access, command callbacks, or wall-clock reads.
A later ingress owns authentication/source binding and wire validation. Explicit
correlation mappings here are trusted local configuration, not producer input.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from .alarms import Alarms
from .contracts import (Ambiguity, Execution, ExecutionKey, Observation, FeedPolicy,
                        AlarmRule, TaskKey, timestamp)
from .freshness import Feed, quality


ACTIVE = {'starting', 'active', 'stopping'}
TERMINAL = {'succeeded', 'failed', 'cancelled'}
LIFECYCLE = ACTIVE | TERMINAL


@dataclass
class Role:
    scope: tuple[str, ...]
    inventory_approved: bool
    claimed_scope: tuple[str, ...] = ()
    complete: bool = False
    reconciled_at: float | None = None
    reconcile_feed: str | None = None
    signals: dict[str, tuple[Observation, float]] = field(default_factory=dict)
    present: set[ExecutionKey] = field(default_factory=set)
    disputed: set[ExecutionKey] = field(default_factory=set)


class Reducer:
    def __init__(self):
        self.roles: dict[str, Role] = {}
        self.feeds: dict[str, Feed] = {}
        self.executions: dict[ExecutionKey, Execution] = {}
        self.correlations: dict[ExecutionKey, tuple[ExecutionKey, str]] = {}
        self.ambiguities: list[Ambiguity] = []
        self.alarms = Alarms()
        self._feed_alarms: dict[str, str] = {}

    def register_role(self, role: str, *, scope: tuple[str, ...], inventory_approved: bool):
        if role in self.roles or not scope or len(scope) != len(set(scope)):
            raise ValueError('Role requires unique identity and declared scope')
        self.roles[role] = Role(tuple(scope), inventory_approved)

    def register_feed(self, name: str, policy: FeedPolicy, *, group: str):
        if name in self.feeds or not name or not group:
            raise ValueError('Feed requires unique identity and correlation group')
        self.feeds[name] = Feed(policy, group)

    def acquire(self, feed: str, at: float):
        """Only successful acquisition of this feed may advance its clock."""
        self.feeds[feed].acquire(at)

    def feed_quality(self, feed: str, *, now: float) -> str:
        return self.feeds[feed].quality(now)

    def _observation_quality(self, o: Observation, acquired_at: float, now: float) -> str:
        # The field's own acquisition is essential: another role/field on the
        # SAME feed cannot revive old evidence by advancing the feed clock.
        if not o.supported:
            return 'unsupported'
        if o.mapped is None or o.mapped == 'unknown':
            return 'unknown'
        return quality(acquired_at, now, self.feeds[o.feed].policy)

    def add_correlation(self, alias: ExecutionKey, canonical: ExecutionKey, *, mapping_version: str):
        if not mapping_version.strip() or alias == canonical:
            raise ValueError('Correlation requires a versioned explicit mapping')
        if canonical not in self.executions or alias in self.executions or alias in self.correlations:
            raise ValueError('Ambiguous/existing records must not be silently merged')
        self.correlations[alias] = (canonical, mapping_version)

    def note_ambiguity(self, candidates: tuple[ExecutionKey, ...], *, reason: str):
        if len(set(candidates)) < 2 or not reason.strip():
            raise ValueError('Ambiguity requires distinct candidates and reason')
        if any(k not in self.executions for k in candidates):
            raise ValueError('Unknown candidate')
        self.ambiguities.append(Ambiguity(tuple(candidates), reason))

    def observe_execution(self, role: str, key: ExecutionKey, *, session: str,
                          parent: ExecutionKey | None, task: TaskKey | None,
                          lifecycle: Observation, acquired_at: float,
                          canonical: ExecutionKey | None = None) -> ExecutionKey:
        if canonical is not None:
            raise ValueError('Correlation must be registered explicitly, not asserted by an observation')
        r = self.roles[role]
        original = key
        key = self.correlations.get(key, (key, ''))[0]
        previous = self.executions.get(key)
        timestamp(acquired_at)
        # Never replace a fact with an older acquisition from another authority.
        # Preserve conflicts for inspection instead of guessing an ordering.
        self.acquire(lifecycle.feed, acquired_at)
        observation = deepcopy(lifecycle)
        if previous:
            previous.observations.append(observation)
            identity_changed = (role, session, parent, task) != (
                previous.role, previous.session, previous.parent, previous.task)
            state_changed = observation.mapped != previous.lifecycle.mapped
            cross_authority = observation.source != previous.lifecycle.source
            terminal = previous.lifecycle.mapped in TERMINAL
            if identity_changed or (state_changed and (cross_authority or terminal)):
                previous.discrepancies.append({'source_key': original, 'role': role,
                    'session': session, 'parent': parent, 'task': task,
                    'observation': observation, 'acquired_at': acquired_at})
                # A disputed role assignment must not make the losing role
                # appear empty/available just because the canonical record
                # remains attached to the other role.
                r.disputed.add(key)
                self.roles[previous.role].disputed.add(key)
            elif acquired_at >= previous.acquired_at and not terminal and not cross_authority:
                previous.lifecycle, previous.acquired_at = observation, acquired_at
        else:
            if not session:
                raise ValueError('Execution requires explicit session identity')
            self.executions[key] = Execution(key, role, session, parent, task,
                observation, acquired_at, [observation])
        r.present.add(key)
        return key

    def observe_role(self, role: str, field_name: str, observation: Observation, *, acquired_at: float):
        if field_name not in {'admission', 'reachability', 'capacity'}:
            raise ValueError('Unsupported role signal')
        self.acquire(observation.feed, acquired_at)
        r = self.roles[role]
        previous = r.signals.get(field_name)
        if previous and previous[0].source != observation.source:
            raise ValueError('Role-signal authority requires an explicit adapter mapping')
        r.signals[field_name] = (deepcopy(observation), acquired_at)

    def reconcile(self, role: str, execution_keys: list[ExecutionKey], *, scope: tuple[str, ...],
                  complete: bool, feed: str, acquired_at: float):
        r = self.roles[role]
        if not set(scope) <= set(r.scope):
            raise ValueError('Reconciliation exceeds registered scope')
        for key in execution_keys:
            if key not in self.executions or self.executions[key].role != role:
                raise ValueError('Snapshot must reference known executions in this role')
        self.acquire(feed, acquired_at)
        r.claimed_scope = tuple(scope)
        r.complete = complete and set(scope) == set(r.scope)
        r.reconciled_at, r.reconcile_feed = acquired_at, feed
        if r.complete:
            r.present = set(execution_keys)
        else:
            r.present.update(execution_keys)

    def summary(self, role: str, *, now: float) -> dict:
        timestamp(now)
        r = self.roles[role]
        reconcile_quality = 'unknown'
        if r.reconcile_feed:
            reconcile_quality = quality(r.reconciled_at, now, self.feeds[r.reconcile_feed].policy)
        coverage = 'not_configured'
        if r.reconciled_at is not None:
            coverage = 'covered' if r.complete and reconcile_quality == 'fresh' else 'partial'
            if reconcile_quality == 'disconnected':
                coverage = 'unreachable'
        signals = {}
        for name, (o, at) in r.signals.items():
            signals[name] = {'native': deepcopy(o.native), 'mapped': deepcopy(o.mapped),
                'mapping_version': o.mapping_version, 'source': o.source,
                'feed': o.feed, 'observed_at': o.observed_at, 'acquired_at': at,
                'evidence_class': o.evidence_class,
                'quality': self._observation_quality(o, at, now)}
        current = [e for key, e in self.executions.items() if key in r.present and e.role == role]
        active = [e.key for e in current if e.lifecycle.mapped in ACTIVE
                  and self._observation_quality(e.lifecycle, e.acquired_at, now) == 'fresh'
                  and e.lifecycle.evidence_class == 'runtime_observed'
                  and not e.discrepancies]
        uncertain = bool(r.disputed) or any(e.discrepancies or e.lifecycle.mapped not in LIFECYCLE
                        or e.lifecycle.evidence_class != 'runtime_observed'
                        or not e.lifecycle.supported
                        or (e.lifecycle.mapped not in TERMINAL and
                            self._observation_quality(e.lifecycle, e.acquired_at, now) != 'fresh')
                        for e in current)
        evidence_fresh = all(name in signals and signals[name]['quality'] == 'fresh'
                             and signals[name]['evidence_class'] in {'runtime_observed', 'source_record'}
                             for name in ('admission', 'reachability', 'capacity'))
        # A configuration/source record can establish admission or a limit,
        # but cannot prove that a runtime is currently reachable.
        evidence_fresh = (evidence_fresh and
                          signals['reachability']['evidence_class'] == 'runtime_observed')
        capacity = signals.get('capacity', {}).get('mapped')
        usable = (isinstance(capacity, dict)
                  and type(capacity.get('limit')) is int
                  and type(capacity.get('used')) is int
                  and 0 <= capacity['used'] < capacity['limit'])
        available = (coverage == 'covered' and r.inventory_approved and not current_active(current)
                     and not uncertain and evidence_fresh and usable
                     and signals['admission']['mapped'] == 'enabled'
                     and signals['reachability']['mapped'] == 'reachable')
        availability = 'busy' if active else ('available' if available else 'unknown')
        return {'role': role, 'availability': availability, 'coverage': coverage,
                'inventory': 'approved' if r.inventory_approved else 'incomplete',
                'claimed_scope': r.claimed_scope, 'active_executions': active,
                'disputed_executions': sorted(r.disputed),
                'signals': signals, 'reconciliation_quality': reconcile_quality,
                'indication': 'telemetry lost' if reconcile_quality == 'disconnected'
                    else ('no observed executions / availability unknown'
                          if availability == 'unknown' else availability)}

    def enable_feed_alarm(self, feed: str, rule: AlarmRule):
        if feed in self._feed_alarms or rule.group != self.feeds[feed].group:
            raise ValueError('Alarm must use feed correlation group and unique binding')
        self.alarms.register(rule)
        self._feed_alarms[feed] = rule.name

    def tick(self, *, now: float):
        timestamp(now)
        self.alarms.expire_shelves(now=now)
        for feed, alarm in self._feed_alarms.items():
            q = self.feed_quality(feed, now=now)
            # An unobserved feed is unknown, not an invented loss event.
            # Unknown quality cannot clear an outstanding observation loss.
            if q == 'unknown':
                continue
            self.alarms.update(alarm, q in {'stale', 'disconnected'}, now=now)


def current_active(executions):
    return any(e.lifecycle.mapped in ACTIVE for e in executions)
