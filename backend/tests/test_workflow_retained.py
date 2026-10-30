# SPDX-License-Identifier: Apache-2.0
"""Core-approved retained-fact presentation; only synthetic native stores are written."""
from dataclasses import replace

import pytest

from workshop.contracts import ExecutionKey
from workshop.storage import Storage
from workshop_collectors.outbox import Outbox
from workshop_collectors.workflow import verify_agreement
from test_hermes_work import native, change, hashes
from test_hermes_runtime import configured, collect, sample


@pytest.fixture
def mixed(native, tmp_path):
    # Three originally running attempts; a fourth is first seen after reopen.
    for identity in (2, 3):
        change(native, "INSERT INTO task_runs (id,task_id,profile,status,started_at) "
               "VALUES (?,'task','coder','running',3)", (identity,))
    observer, state = configured(native, probe=sample)
    path = tmp_path / 'historian.db'
    store = Storage(path, initial=state)
    queue = Outbox(tmp_path / 'outbox.db', binding=observer.binding, clock_id='fixture-boot')
    queue.enqueue(collect(observer, 10))
    assert queue.deliver_one(store, received_at=10).accepted == 3
    store.close()
    store = Storage(path)
    assert store.read().ingests['runtime'].reconcile_required is True
    change(native, "UPDATE task_runs SET status='blocked',outcome='blocked',ended_at=11 WHERE id=1")
    change(native, "UPDATE task_runs SET status='scheduled' WHERE id=2")
    change(native, "UPDATE task_runs SET status='done',outcome='completed',ended_at=11 WHERE id=3")
    change(native, "INSERT INTO task_runs (id,task_id,profile,status,started_at) "
           "VALUES (4,'task','coder','running',11)")
    snapshot = collect(observer, 12)
    queue.enqueue(snapshot)
    result = queue.deliver_one(store, received_at=12)
    assert (result.accepted, result.ignored) == (2, 2)
    try:
        yield observer, snapshot, store, native
    finally:
        queue.close()
        store.close()


def test_live_shape_reopen_two_retained_two_current_and_ignored_raw_retained(mixed):
    observer, snapshot, store, native = mixed
    before = hashes(native)
    saved = store.read()
    ingest = saved.ingests['runtime']
    # Ordering rejects canonical replacements, NOT the newest raw provenance.
    assert len(ingest.records) == 7
    for identity, status in [('1', 'blocked'), ('2', 'unknown')]:
        records = [r for r in ingest.records
                   if r['attributes']['workshop.execution.id'] == identity]
        assert len(records) == 2
        assert records[0]['domain']['lifecycle'] == 'active'
        assert records[-1]['domain']['lifecycle'] == 'unknown'
        assert records[-1]['attributes']['workshop.hermes.attempt.status'] == status
        assert records[-1]['acquired_at'] is None
        fact = saved.reducer.executions[ExecutionKey(observer.binding.runtime, identity)]
        assert fact.lifecycle.mapped == 'active' and fact.acquired_at is None
    report = verify_agreement(observer, snapshot, store, now=12)
    rows = {r['execution_id']: r for r in report['comparisons']}
    assert report['compared_attempts'] == 4
    for identity in ('1', '2'):
        row = rows[identity]
        assert row['agreement_basis'] == 'retained_prior_fact'
        assert row['retained_lifecycle'] == row['projected_lifecycle'] == 'active'
        assert row['lifecycle_quality'] == 'unknown'
        assert row['reconcile_latched'] is True and row['agrees'] is True
    for identity, lifecycle in [('3', 'succeeded'), ('4', 'active')]:
        assert rows[identity]['agreement_basis'] == 'current'
        assert rows[identity]['projected_lifecycle'] == lifecycle
        assert 'retained_lifecycle' not in rows[identity]
    assert report['runtime_coverage'] == 'partial'
    assert report['role_availability'] == 'unknown'
    assert report['native_write_enabled'] is False
    assert hashes(native) == before


@pytest.mark.parametrize('mutation', [
    'terminal', 'unknown', 'unsupported', 'not_source', 'acquired', 'unlatched',
    'projected_terminal', 'projected_unknown', 'projected_not_source', 'projected_unsupported',
])
def test_retained_contract_requires_every_guard(mixed, monkeypatch, mutation):
    observer, snapshot, store, _ = mixed
    assert verify_agreement(observer, snapshot, store, now=12)['source_projection_agreement']
    saved = store.read()
    fact = saved.reducer.executions[ExecutionKey(observer.binding.runtime, '1')]
    projection = store.snapshot(now=12)
    view = next(e for e in projection['projection']['executions'] if e['key']['native_id'] == '1')
    if mutation == 'terminal':
        fact.lifecycle = replace(fact.lifecycle, mapped='succeeded')
    elif mutation == 'unknown':
        fact.lifecycle = replace(fact.lifecycle, mapped='unknown', supported=False)
    elif mutation == 'unsupported':
        fact.lifecycle = replace(fact.lifecycle, supported=False)
    elif mutation == 'not_source':
        fact.lifecycle = replace(fact.lifecycle, evidence_class='inferred')
    elif mutation == 'acquired':
        fact.acquired_at = 12
    elif mutation == 'unlatched':
        saved.ingests['runtime'].reconcile_required = False
        assert view['lifecycle_quality'] == 'unknown'
    else:
        field, value = {
            'projected_terminal': ('mapped', 'succeeded'),
            'projected_unknown': ('mapped', 'unknown'),
            'projected_not_source': ('evidence_class', 'inferred'),
            'projected_unsupported': ('supported', False),
        }[mutation]
        view['lifecycle'][field] = value
    monkeypatch.setattr(store, 'read', lambda: saved)
    monkeypatch.setattr(store, 'snapshot', lambda **kwargs: projection)
    with pytest.raises(ValueError, match='disagreement'):
        verify_agreement(observer, snapshot, store, now=12)


@pytest.mark.parametrize('quality', ['fresh', 'stale', 'disconnected', 'unsupported', None])
def test_retained_requires_presented_unknown_quality(mixed, monkeypatch, quality):
    observer, snapshot, store, _ = mixed
    assert verify_agreement(observer, snapshot, store, now=12)['source_projection_agreement']
    projection = store.snapshot(now=12)
    next(e for e in projection['projection']['executions']
         if e['key']['native_id'] == '1')['lifecycle_quality'] = quality
    monkeypatch.setattr(store, 'snapshot', lambda **kwargs: projection)
    with pytest.raises(ValueError, match='disagreement'):
        verify_agreement(observer, snapshot, store, now=12)


@pytest.mark.parametrize('field,value', [
    ('workshop.record.id', 'not-current'), ('epoch', 'other-epoch'),
    ('cursor', 1), ('workshop.hermes.board.event_id', 999),
    ('workshop.hermes.native.complete', False),
    ('workshop.hermes.process', 'exited'), ('workshop.hermes.task.station', 'done'),
    ('workshop.hermes.attempt.status', 'running'),
    ('workshop.hermes.attempt.outcome', 'completed'),
])
def test_retained_never_waives_current_raw_checks(mixed, monkeypatch, field, value):
    observer, snapshot, store, _ = mixed
    assert verify_agreement(observer, snapshot, store, now=12)['source_projection_agreement']
    saved = store.read()
    record = next(r for r in reversed(saved.ingests['runtime'].records)
                  if r['attributes']['workshop.execution.id'] == '1')
    if field == 'epoch':
        record['epoch'] = value
    elif field == 'cursor':
        saved.source_cursors['runtime'] = value
    else:
        record['attributes'][field] = value
    monkeypatch.setattr(store, 'read', lambda: saved)
    with pytest.raises(ValueError, match='disagreement|acquisition'):
        verify_agreement(observer, snapshot, store, now=12)


@pytest.mark.parametrize('identity', ['3', '4'])
@pytest.mark.parametrize('target', ['fact', 'view'])
def test_active_and_terminal_equality_still_required(mixed, monkeypatch, identity, target):
    observer, snapshot, store, _ = mixed
    assert verify_agreement(observer, snapshot, store, now=12)['source_projection_agreement']
    saved = store.read()
    projection = store.snapshot(now=12)
    if target == 'fact':
        fact = saved.reducer.executions[ExecutionKey(observer.binding.runtime, identity)]
        fact.lifecycle = replace(fact.lifecycle, mapped='unknown', supported=False)
    else:
        next(e for e in projection['projection']['executions']
             if e['key']['native_id'] == identity)['lifecycle']['mapped'] = 'unknown'
    monkeypatch.setattr(store, 'read', lambda: saved)
    monkeypatch.setattr(store, 'snapshot', lambda **kwargs: projection)
    with pytest.raises(ValueError, match='disagreement'):
        verify_agreement(observer, snapshot, store, now=12)


@pytest.mark.parametrize('status,outcome,ended,expected', [
    ('running', None, None, 'active'), ('blocked', 'blocked', 8, 'unknown'),
    ('scheduled', None, None, 'unknown'), ('done', 'completed', 8, 'succeeded'),
])
def test_fresh_first_observation_unchanged(native, tmp_path, status, outcome, ended, expected):
    change(native, 'UPDATE task_runs SET status=?,outcome=?,ended_at=?', (status, outcome, ended))
    observer, state = configured(native)
    store = Storage(tmp_path / 'historian.db', initial=state)
    queue = Outbox(tmp_path / 'outbox.db', binding=observer.binding, clock_id='fixture-boot')
    try:
        snapshot = collect(observer)
        queue.enqueue(snapshot)
        queue.deliver_one(store, received_at=10)
        assert not store.read().ingests['runtime'].reconcile_required
        row = verify_agreement(observer, snapshot, store, now=10)['comparisons'][0]
        assert row['projected_lifecycle'] == expected and row['agreement_basis'] == 'current'
        assert 'retained_lifecycle' not in row
    finally:
        queue.close()
        store.close()


def test_retained_unknown_cannot_hide_source_now_active(native, tmp_path):
    change(native, "UPDATE task_runs SET status='blocked',outcome='blocked',ended_at=8")
    observer, state = configured(native)
    path = tmp_path / 'historian.db'
    store = Storage(path, initial=state)
    queue = Outbox(tmp_path / 'outbox.db', binding=observer.binding, clock_id='fixture-boot')
    queue.enqueue(collect(observer))
    queue.deliver_one(store, received_at=10)
    store.close()
    store = Storage(path)
    try:
        change(native, "UPDATE task_runs SET status='running',outcome=NULL,ended_at=NULL")
        snapshot = collect(observer, 12)
        queue.enqueue(snapshot)
        assert queue.deliver_one(store, received_at=12).ignored == 1
        fact = next(iter(store.read().reducer.executions.values()))
        assert fact.lifecycle.mapped == 'unknown' and not fact.lifecycle.supported
        with pytest.raises(ValueError, match='disagreement'):
            verify_agreement(observer, snapshot, store, now=12)
    finally:
        queue.close()
        store.close()
