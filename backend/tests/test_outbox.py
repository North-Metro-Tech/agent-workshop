# SPDX-License-Identifier: Apache-2.0
"""Bounded durable observation delivery; all native sources are synthetic."""
from dataclasses import replace
import sqlite3

import pytest

from workshop.contracts import ExecutionKey
from workshop.storage import Storage, RecoveryRequired
from test_hermes_work import native, hashes
from test_hermes_runtime import configured, collect, sample


def box(path, observer, **kwargs):
    from workshop_collectors.outbox import Outbox
    return Outbox(path, binding=observer.binding, clock_id='test-boot', **kwargs)


def test_A08_outbox_offline_restart_fifo_original_acquisition(native, tmp_path):
    observer, state = configured(native, probe=sample)
    before = hashes(native)
    path = tmp_path / 'outbox.db'
    q = box(path, observer)
    assert q.enqueue(collect(observer, 10)) == 1
    assert q.enqueue(collect(observer, 11)) == 2
    epoch = q.status()['epoch']
    assert q.status()['pending'] == 2
    q.close()
    q = box(path, observer)
    assert q.status()['epoch'] == epoch
    store = Storage(tmp_path / 'historian.db', initial=state)
    assert q.deliver_one(store, received_at=1000).accepted == 1
    assert store.read().source_cursors['runtime'] == 1
    assert q.deliver_one(store, received_at=1001).accepted == 1
    assert q.deliver_one(store, received_at=1002) is None
    saved = store.read()
    assert saved.source_cursors['runtime'] == 2
    assert next(iter(saved.reducer.executions.values())).acquired_at == 11
    assert saved.reducer.feed_quality(observer.binding.feed, now=1001) == 'disconnected'
    assert q.status()['pending'] == 0
    assert q.status()['next_cursor'] == 3
    assert hashes(native) == before
    q.close()
    store.close()


def test_A08_outbox_commit_ack_crash_replays_exact_identity(native, tmp_path, monkeypatch):
    observer, state = configured(native, probe=sample)
    q = box(tmp_path / 'outbox.db', observer)
    store = Storage(tmp_path / 'historian.db', initial=state)
    q.enqueue(collect(observer))
    original = q._ack
    def crash(cursor):
        raise OSError('simulated crash after historian commit')
    monkeypatch.setattr(q, '_ack', crash)
    with pytest.raises(OSError):
        q.deliver_one(store, received_at=11)
    assert store.read().source_cursors['runtime'] == 1
    assert q.status()['pending'] == 1
    monkeypatch.setattr(q, '_ack', original)
    assert q.deliver_one(store, received_at=99).duplicates == 1
    assert len(store.read().ingests['runtime'].records) == 1
    assert q.status()['pending'] == 0
    q.close()
    store.close()


def test_A08_outbox_ingest_failure_never_acknowledges(native, tmp_path, monkeypatch):
    observer, state = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    store = Storage(tmp_path / 'historian.db', initial=state)
    q.enqueue(collect(observer))
    before = q.status()
    def offline(*args, **kwargs):
        raise OSError('offline')
    monkeypatch.setattr(store, 'otlp', offline)
    with pytest.raises(OSError):
        q.deliver_one(store, received_at=11)
    assert q.status() == before
    assert not store.read().source_cursors
    q.close()
    store.close()


def test_A08_outbox_backpressure_no_drop_or_sequence_consumption(native, tmp_path):
    from workshop_collectors.outbox import OutboxFull
    observer, _ = configured(native)
    q = box(tmp_path / 'outbox.db', observer, max_items=1)
    q.enqueue(collect(observer))
    before = q.status()
    with pytest.raises(OutboxFull):
        q.enqueue(collect(observer, 11))
    assert q.status() == before
    q.close()


def test_A08_outbox_byte_backpressure(native, tmp_path):
    from workshop_collectors.outbox import OutboxFull
    observer, _ = configured(native)
    q = box(tmp_path / 'outbox.db', observer, max_bytes=100)
    with pytest.raises(OutboxFull):
        q.enqueue(collect(observer))
    assert q.status()['next_cursor'] == 1
    assert q.status()['pending'] == 0
    q.close()


@pytest.mark.parametrize('kwargs', [{'max_items': 0}, {'max_items': True}, {'max_items': 65},
    {'max_bytes': 0}, {'max_bytes': True}, {'max_bytes': 4194305}, {'clock_id': ''}])
def test_outbox_bounds_required_before_file_creation(native, tmp_path, kwargs):
    from workshop_collectors.outbox import Outbox
    observer, _ = configured(native)
    options = dict(binding=observer.binding, clock_id='test-boot')
    options.update(kwargs)
    path = tmp_path / 'outbox.db'
    with pytest.raises(ValueError):
        Outbox(path, **options)
    assert not path.exists()


def test_A10_outbox_rejects_native_historian_and_symlink_unchanged(native, tmp_path):
    observer, state = configured(native)
    before = hashes(native)
    with pytest.raises(ValueError, match='outbox'):
        box(native, observer)
    assert hashes(native) == before
    historian = tmp_path / 'historian.db'
    store = Storage(historian, initial=state)
    view = store.snapshot(now=10)
    with pytest.raises(ValueError, match='outbox'):
        box(historian, observer)
    assert store.snapshot(now=10) == view
    link = tmp_path / 'link.db'
    link.symlink_to(native)
    with pytest.raises(ValueError, match='path'):
        box(link, observer)
    store.close()


def test_A08_outbox_clock_binding_and_limit_changes_rejected(native, tmp_path):
    from workshop_collectors.outbox import Outbox
    observer, _ = configured(native)
    path = tmp_path / 'outbox.db'
    q = box(path, observer)
    q.enqueue(collect(observer))
    q.close()
    for kwargs in ({'clock_id': 'new-boot'}, {'max_items': 1}, {'max_bytes': 100},
                   {'binding': replace(observer.binding, task_scopes=())}):
        options = dict(binding=observer.binding, clock_id='test-boot')
        options.update(kwargs)
        with pytest.raises(ValueError, match='configuration'):
            Outbox(path, **options)
    q = box(path, observer)
    assert q.status()['pending'] == 1
    q.close()


def test_A08_outbox_rejects_regressed_acquisition_and_replaced_source(native, tmp_path):
    observer, _ = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    s = collect(observer)
    q.enqueue(s)
    before = q.status()
    for bad in (replace(s, acquired_at=9), replace(s, source_identity=(0, 99)),
                replace(s, source_identity=(True, 1)), replace(s, acquired_at=float('nan'))):
        with pytest.raises(ValueError):
            q.enqueue(bad)
        assert q.status() == before
    q.close()


def test_A08_outbox_sequence_divergence_does_not_drop_or_rebase(native, tmp_path):
    observer, state = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    q.enqueue(collect(observer))
    store = Storage(tmp_path / 'historian.db', initial=state)
    observer.publish(store, 'runtime', collect(observer), received_at=10, epoch='other-writer', source_cursor=7)
    before = store.snapshot(now=10)
    with pytest.raises(RecoveryRequired, match='cursor'):
        q.deliver_one(store, received_at=11)
    assert q.status()['pending'] == 1
    assert store.snapshot(now=10) == before
    q.close()
    store.close()


def test_A10_outbox_wrong_historian_binding_and_early_receipt(native, tmp_path):
    observer, state = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    q.enqueue(collect(observer))
    other, other_state = configured(native, binding_change={'runtime': 'wrong-instance'})
    store = Storage(tmp_path / 'other.db', initial=other_state)
    with pytest.raises(ValueError, match='binding'):
        q.deliver_one(store, received_at=11)
    store.close()
    store = Storage(tmp_path / 'historian.db', initial=state)
    with pytest.raises(ValueError, match='Receipt'):
        q.deliver_one(store, received_at=9)
    assert not store.read().source_cursors
    assert q.status()['pending'] == 1
    q.close()
    store.close()


def test_A10_outbox_source_privacy_and_fixed_off(native, tmp_path):
    observer, state = configured(native, probe=sample)
    path = tmp_path / 'outbox.db'
    q = box(path, observer)
    q.enqueue(collect(observer))
    db = sqlite3.connect(path)
    retained = repr(tuple(db.iterdump()))
    db.close()
    for secret in ('private prompt', 'private comment', '/never/follow/this', 'boot:1|22', 'cmdline'):
        assert secret not in retained
    store = Storage(tmp_path / 'historian.db', initial=state)
    q.deliver_one(store, received_at=10)
    assert store.snapshot(now=10)['projection']['native_write_enabled'] is False
    e = store.read().reducer.executions[ExecutionKey(observer.binding.runtime, '1')]
    assert e.task.native_id == 'task'
    q.close()
    store.close()


def test_A08_outbox_retired_epoch_adjacent_cursor_retains_head(native, tmp_path):
    observer, state = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    store = Storage(tmp_path / 'historian.db', initial=state)
    q.enqueue(collect(observer))
    q.deliver_one(store, received_at=10)
    q.enqueue(collect(observer, 12))
    # A divergent writer retires the queue's epoch at the adjacent numeric cursor.
    with store.transaction() as saved:
        ingest = saved.ingests['runtime']
        ingest._retired_epochs.add(ingest._epoch)
        ingest._epoch = 'other-writer'
    before = store.snapshot(now=12)
    with pytest.raises(RecoveryRequired, match='epoch'):
        q.deliver_one(store, received_at=12)
    assert store.snapshot(now=12) == before
    assert q.status()['pending'] == 1
    q.close()
    store.close()


def test_A08_outbox_empty_snapshot_rejected_without_consuming_cursor(native, tmp_path):
    from test_hermes_work import change
    change(native, 'DELETE FROM task_runs')
    observer, _ = configured(native)
    q = box(tmp_path / 'outbox.db', observer)
    before = q.status()
    with pytest.raises(ValueError, match='empty'):
        q.enqueue(collect(observer))
    assert q.status() == before
    q.close()


def test_A08_outbox_commit_ack_crash_both_handles_reopened(native, tmp_path, monkeypatch):
    observer, state = configured(native)
    qpath, hpath = tmp_path / 'outbox.db', tmp_path / 'historian.db'
    q = box(qpath, observer)
    store = Storage(hpath, initial=state)
    q.enqueue(collect(observer))
    def crash(cursor):
        raise OSError('crash after commit')
    monkeypatch.setattr(q, '_ack', crash)
    with pytest.raises(OSError):
        q.deliver_one(store, received_at=10)
    q.close()
    store.close()
    q = box(qpath, observer)
    store = Storage(hpath)
    assert q.deliver_one(store, received_at=1000).duplicates == 1
    assert store.read().source_cursors['runtime'] == 1
    assert len(store.read().ingests['runtime'].records) == 1
    assert next(iter(store.read().reducer.executions.values())).acquired_at is None
    assert q.status()['pending'] == 0
    q.close()
    store.close()
