# SPDX-License-Identifier: Apache-2.0
"""Local in-process read facade, not a network service or native command API.

A later HTTP binding must establish its own authenticated same-origin session.
Here `authorized` is supplied only by the trusted local caller, not telemetry.
Release 1 has no executor/callback, native route or configurable write switch.
"""
from copy import deepcopy
from dataclasses import asdict


class LocalAPI:
    def __init__(self, reducer=None, *, storage=None):
        if (reducer is None) == (storage is None):
            raise ValueError('Supply either a reducer or a Workshop historian')
        self._reducer = reducer
        self._storage = storage

    @property
    def native_write_enabled(self):
        return False

    def snapshot(self, *, now):
        if self._storage is not None:
            return self._storage.snapshot(now=now)['projection']
        assert self._reducer is not None
        return {'native_write_enabled': False,
            'roles': [self._reducer.summary(role, now=now) for role in self._reducer.roles],
            'executions': [{**deepcopy(asdict(e)),
                'lifecycle_quality': self._reducer._observation_quality(e.lifecycle, e.acquired_at, now),
                'acquisition_age': (max(0, now - e.acquired_at)
                                    if e.acquired_at is not None else None)}
                for e in self._reducer.executions.values()],
            'ambiguities': [asdict(a) for a in self._reducer.ambiguities],
            'correlations': [{'alias': asdict(alias), 'canonical': asdict(target),
                              'mapping_version': version}
                             for alias, (target, version) in self._reducer.correlations.items()],
            'alarms': [{'id': o.id, 'condition': o.condition,
                        'acknowledged': o.acknowledged, 'state': o.state(now=now),
                        'rule': asdict(o.rule), 'controls': asdict(o.controls),
                        'raised_at': o.raised_at, 'cleared_at': o.cleared_at}
                       for o in self._reducer.alarms.occurrences],
            'incidents': self._reducer.alarms.incidents()}

    def acknowledge(self, occurrence_id, *, now, authorized=False):
        if authorized is not True:
            raise PermissionError('Local operator authorization required')
        if self._storage is not None:
            with self._storage.transaction() as state:
                state.reducer.alarms.acknowledge(occurrence_id, now=now, actor='local-operator')
        else:
            assert self._reducer is not None
            self._reducer.alarms.acknowledge(occurrence_id, now=now, actor='local-operator')

    def request(self, method, path, *, position='viewer', authorized=False,
                now=0, occurrence_id=None):
        if method == 'GET' and path == '/snapshot':
            return self.snapshot(now=now)
        if method == 'POST' and path == '/alarms/acknowledge':
            if position not in {'operator', 'controller'}:
                raise PermissionError('Viewer cannot acknowledge alarms')
            return self.acknowledge(occurrence_id, now=now, authorized=authorized)
        # No dynamic dispatch, native operation mapping or extension callback.
        raise LookupError('No such local operation; native controls are not connected')
