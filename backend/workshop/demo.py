# SPDX-License-Identifier: Apache-2.0
"""Deterministic synthetic Phase 1 demo. No clock, file, network or runtime reads."""
from dataclasses import asdict
import json

from .api import LocalAPI
from .contracts import FeedPolicy, Observation
from .ingest import Acquisition, EVENT_TYPE, Ingest, SourceBinding
from .reducer import Reducer


def snapshot():
    """Seed scoped synthetic observations and return a JSON-ready snapshot."""
    r = Reducer()
    for name in ('a', 'b', 'c', 'idle', 'unobserved'):
        r.register_role(name, scope=('synthetic-chat',), inventory_approved=True)
        r.register_feed(name, FeedPolicy(5, 15, 30), group='synthetic-' + name)
    for name, instance, board in (('a', 'instance-a', 'board-a'),
                                  ('b', 'instance-a', 'board-b'),
                                  ('c', 'instance-b', 'board-a')):
        source = 'urn:synthetic:' + name
        ingest = Ingest(r, SourceBinding(source, 'synthetic-runtime-' + name, name, name,
                                        task_scopes=((instance, board),)))
        event = dict(specversion='1.0', source=source, id='same-event', type=EVENT_TYPE,
            data=dict(execution_id='same-execution', session_id='same-session',
                      lifecycle='active', revision=1, task=dict(source_instance=instance,
                          namespace=board, native_id='same-task')))
        ingest.cloudevents(json.dumps(event).encode(), context=Acquisition(20, 20, 'synthetic-boot'))
        r.reconcile(name, list(r.roles[name].present), scope=('synthetic-chat',),
                    complete=True, feed=name, acquired_at=20)
    r.reconcile('idle', [], scope=('synthetic-chat',), complete=True, feed='idle', acquired_at=20)
    for name, value in (('admission', 'enabled'), ('reachability', 'reachable'),
                        ('capacity', {'limit': 1, 'used': 0})):
        r.observe_role('idle', name, Observation(value, value, 'synthetic-v1',
            'urn:synthetic:idle', 'idle', None), acquired_at=20)
    # Dataclass identities and tuples are encoded as ordinary JSON objects and
    # arrays. This is a projection, not another public telemetry wire envelope.
    return json.loads(json.dumps(LocalAPI(r).snapshot(now=20), default=asdict))


def main():
    print(json.dumps(snapshot(), indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
