# SPDX-License-Identifier: Apache-2.0
"""Workshop-local alarm occurrences. No runtime operations or fault clearing."""
from dataclasses import dataclass
from .contracts import AlarmRule, timestamp


@dataclass
class Controls:
    suppressed: bool = False
    suppression_reason: str = ''
    shelved_until: float | None = None
    shelving_reason: str = ''
    maintenance: bool = False
    maintenance_owner: str = ''
    maintenance_reason: str = ''


@dataclass
class Occurrence:
    id: str
    rule: AlarmRule
    incident: int
    raised_at: float
    reliable_order: bool
    controls: Controls
    condition: bool = True
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: float | None = None
    cleared_at: float | None = None

    @property
    def outstanding(self):
        return self.condition or not self.acknowledged

    def state(self, *, now: float) -> str:
        timestamp(now)
        if self.controls.maintenance:
            return 'out-of-service'
        if self.controls.suppressed:
            return 'suppressed-by-design'
        if self.controls.shelved_until is not None and now < self.controls.shelved_until:
            return 'shelved'
        if self.condition:
            return 'acknowledged' if self.acknowledged else 'unacknowledged'
        return 'normal' if self.acknowledged else 'return-to-normal-unacked'


class Alarms:
    def __init__(self):
        self.rules: dict[str, AlarmRule] = {}
        self.controls: dict[str, Controls] = {}
        self.occurrences: list[Occurrence] = []
        self.audit: list[dict] = []
        self._current: dict[str, Occurrence] = {}
        self._pending: dict[str, tuple[bool, float, bool]] = {}
        self._incident: dict[str, int] = {}
        self._last_update: dict[str, float] = {}

    def register(self, rule: AlarmRule):
        if rule.name in self.rules:
            raise ValueError('Alarm already registered')
        self.rules[rule.name] = rule
        self.controls[rule.name] = Controls()

    def update(self, name: str, condition: bool, *, now: float,
               reliable_order: bool = True) -> Occurrence | None:
        timestamp(now)
        if type(condition) is not bool:
            raise ValueError('Alarm condition must be explicit boolean')
        if name in self._last_update and now < self._last_update[name]:
            raise ValueError('Alarm observation clock regressed')
        self._last_update[name] = now
        rule = self.rules[name]
        current = self._current.get(name)
        existing = current.condition if current else False
        if condition == existing:
            self._pending.pop(name, None)
            return current
        pending = self._pending.get(name)
        if pending is None or pending[0] != condition:
            pending = (condition, now, reliable_order)
        else:
            pending = (pending[0], pending[1], pending[2] and reliable_order)
        self._pending[name] = pending
        delay = rule.on_delay if condition else rule.off_delay
        if now - pending[1] < delay:
            return current
        self._pending.pop(name, None)
        if condition:
            # Retain the group's original first-out until ALL children have
            # cleared and been acknowledged, even if the root cleared first.
            open_group = any(o.rule.group == rule.group and o.outstanding
                             for o in self.occurrences)
            if not open_group:
                self._incident[rule.group] = self._incident.get(rule.group, 0) + 1
            current = Occurrence(str(len(self.occurrences) + 1), rule,
                self._incident[rule.group], pending[1] + delay, pending[2],
                self.controls[name])
            self.occurrences.append(current)
            self._current[name] = current
            self.audit.append({'action': 'raised', 'id': current.id, 'at': now})
        else:
            assert current is not None  # A clear transition requires an active occurrence.
            current.condition = False
            current.cleared_at = pending[1] + delay
            self.audit.append({'action': 'cleared', 'id': current.id, 'at': now})
        return current

    def acknowledge(self, occurrence_id: str, *, now: float, actor: str):
        timestamp(now)
        if not actor.strip():
            raise ValueError('Acknowledgement requires a local actor')
        occurrence = next((o for o in self.occurrences if o.id == occurrence_id), None)
        if occurrence is None:
            raise KeyError(occurrence_id)
        if now < occurrence.raised_at:
            raise ValueError('Acknowledgement predates occurrence')
        if not occurrence.acknowledged:
            occurrence.acknowledged = True
            occurrence.acknowledged_by = actor
            occurrence.acknowledged_at = now
            self.audit.append({'action': 'acknowledged', 'id': occurrence_id,
                               'actor': actor, 'at': now})

    def suppress(self, name: str, enabled: bool, *, reason: str, now: float):
        self._record('design-suppression', name, now, reason, enabled=enabled)
        c = self.controls[name]
        c.suppressed, c.suppression_reason = enabled, reason

    def shelve(self, name: str, *, until: float, reason: str, actor: str, now: float):
        if timestamp(until) <= timestamp(now) or not actor.strip():
            raise ValueError('Shelving requires actor and future expiry')
        self._record('shelved', name, now, reason, actor=actor, until=until)
        c = self.controls[name]
        c.shelved_until, c.shelving_reason = until, reason

    def unshelve(self, name: str, *, reason: str, actor: str, now: float):
        if not actor.strip():
            raise ValueError('Unshelving requires actor')
        self._record('unshelved', name, now, reason, actor=actor)
        self.controls[name].shelved_until = None

    def out_of_service(self, name: str, enabled: bool, *, owner: str, reason: str, now: float):
        if not owner.strip():
            raise ValueError('Maintenance removal requires owner')
        self._record('maintenance', name, now, reason, owner=owner, enabled=enabled)
        c = self.controls[name]
        c.maintenance, c.maintenance_owner, c.maintenance_reason = enabled, owner, reason

    def _record(self, action, name, now, reason, **fields):
        timestamp(now)
        if not reason.strip():
            raise ValueError('Alarm control changes require an audit reason')
        if name not in self.rules:
            raise KeyError(name)
        self.audit.append({'action': action, 'name': name, 'at': now,
                           'reason': reason, **fields})

    def expire_shelves(self, *, now: float):
        timestamp(now)
        for name, controls in self.controls.items():
            if controls.shelved_until is not None and now >= controls.shelved_until:
                self.audit.append({'action': 'shelving-expired', 'name': name,
                                   'at': controls.shelved_until})
                controls.shelved_until = None

    def incidents(self) -> list[dict]:
        groups = {}
        for o in self.occurrences:
            groups.setdefault((o.rule.group, o.incident), []).append(o)
        result = []
        for (group, incident), children in groups.items():
            if not any(o.outstanding for o in children):
                continue
            ordered = sorted(children, key=lambda o: (o.raised_at, int(o.id)))
            times = [o.raised_at for o in children]
            result.append({'group': group, 'incident': incident,
                'first_out': ordered[0].id, 'children': [o.id for o in ordered],
                'ordering_uncertain': len(set(times)) != len(times)
                    or any(not o.reliable_order for o in children)})
        return result
