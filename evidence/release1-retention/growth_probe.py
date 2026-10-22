#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Same synthetic fixed-cardinality assertion at base and candidate, no native I/O.

Run from the target checkout root with PYTHONPATH=backend:collectors. DB files
are created under a caller-supplied scratch directory, never installed state.
"""
import json
from pathlib import Path
import sys

from workshop.contracts import FeedPolicy
from workshop.ingest import Acquisition, Ingest, SourceBinding
from workshop.reducer import Reducer
from workshop.storage import State, Storage, _pack, _sections

path = Path(sys.argv[1])
if path.exists():
    raise SystemExit('Refusing existing probe historian')
r = Reducer()
r.register_role('agent', scope=('chat',), inventory_approved=True)
r.register_feed('runtime', FeedPolicy(15, 45, 120), group='source')
i = Ingest(r, SourceBinding('urn:fixture:source', 'runtime', 'agent', 'runtime'))
s = Storage(path, initial=State(r, {'source': i}))
try:
    for number in range(1, 181):
        payload = [{'specversion': '1.0', 'source': 'urn:fixture:source',
                    'id': f'{number}-{native}', 'type': 'org.agentworkshop.execution.lifecycle.v1',
                    'data': {'execution_id': native, 'session_id': 'session',
                             'lifecycle': lifecycle, 'revision': number}}
                   for native, lifecycle in [('active', 'active'), ('terminal', 'succeeded')]]
        s.cloudevents('source', json.dumps(payload).encode(),
                      context=Acquisition(number, number, 'probe'), source_cursor=number)
    s._db.execute('PRAGMA wal_checkpoint(PASSIVE)')
    state = s.read()
    result = {'cycles': 180, 'accepted_identities': 360,
              'observations': sum(len(e.observations) for e in state.reducer.executions.values()),
              'records': len(state.ingests['source'].records), 'seen': len(state.ingests['source']._seen),
              'state_bytes': len(_pack(_sections(state)).encode()),
              'revision_bytes': s._db.execute('SELECT SUM(length(CAST(state AS BLOB))) FROM revisions').fetchone()[0],
              'revisions': s._db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],
              'allocated_bytes': sum(p.stat().st_blocks * 512 for p in
                  (path, Path(str(path)+'-wal'), Path(str(path)+'-shm')) if p.exists())}
    print(json.dumps(result, sort_keys=True), flush=True)
    assert result['revision_bytes'] < 8 * 1024 * 1024, 'Retained revision payload exceeds fixed 8MiB bound'
    assert result['observations'] <= 65, 'Redundant observations exceed policy'
    assert result['records'] <= 256, 'Ingest metadata exceeds policy'
    assert result['allocated_bytes'] < 32 * 1024 * 1024, 'Historian allocation exceeds fixed 32MiB bound'
finally:
    s.close()
