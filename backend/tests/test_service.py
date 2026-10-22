# SPDX-License-Identifier: Apache-2.0
"""Real Uvicorn/TCP service tests, no mocked fetch/ASGI test transport dependency."""
from contextlib import contextmanager
from dataclasses import replace
import asyncio
import http.client
import json
from pathlib import Path
import socket
import threading
import time

import pytest
import uvicorn

from workshop.service import COOKIE, Settings, create_app
from workshop.storage import Storage
from workshop.web_contracts import Snapshot, History

TOKEN = 'synthetic-test-operator-secret-not-a-production-credential'
VIEWER = 'synthetic-test-viewer-secret-not-a-production-credential'


class Running:
    def __init__(self, path, **overrides):
        self.sock = socket.socket()
        self.sock.bind(('127.0.0.1', 0))
        self.port = self.sock.getsockname()[1]
        self.origin = f'http://127.0.0.1:{self.port}'
        self.now = [100.0]
        self.settings = Settings(path, TOKEN, origin=self.origin, viewer_token=VIEWER,
                                 poll_seconds=.02, **overrides)
        self.app = create_app(self.settings, clock=lambda:self.now[0])
        self.server = uvicorn.Server(uvicorn.Config(self.app, host='127.0.0.1', port=self.port,
            loop='asyncio', http='h11', ws='none', proxy_headers=False, access_log=False,
            log_level='error', timeout_graceful_shutdown=1))
        self.thread = threading.Thread(target=self.server.run, kwargs={'sockets':[self.sock]}, daemon=True)
        self.cookie = None

    def start(self):
        self.thread.start()
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            if self.server.started:
                return self
            if not self.thread.is_alive():
                break
            time.sleep(.01)
        self.stop()
        raise RuntimeError('Real service failed startup')

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.sock.close()
        assert not self.thread.is_alive(), 'Service did not release historian'

    def request(self, method, path, body=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault('Origin', self.origin)
        if self.cookie is not None:
            headers.setdefault('Cookie', self.cookie)
        if body is not None:
            headers.setdefault('Content-Type', 'application/json')
            body = json.dumps(body).encode()
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        result = (response.status, dict(response.getheaders()), json.loads(raw) if raw else None)
        connection.close()
        return result

    def login(self, token=TOKEN):
        code, headers, body = self.request('POST', '/api/session', {'token':token})
        assert code == 200, body
        self.cookie = headers['set-cookie'].split(';')[0]
        code, _, session = self.request('GET', '/api/session')
        assert code == 200
        return session, headers

    def stream(self, cursor=None):
        headers = {'Origin':self.origin, 'Cookie':self.cookie or ''}
        if cursor is not None:
            headers['Last-Event-ID'] = cursor
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        connection.request('GET', '/api/events', headers=headers)
        response = connection.getresponse()
        assert response.status == 200
        frames, frame = [], []
        for _ in range(12):
            line = response.readline().decode().strip()
            if line:
                frame.append(line)
            elif frame:
                frames.append(frame)
                if 'event: snapshot' in frame:
                    break
                frame = []
        response.close()
        connection.close()
        return frames


@pytest.fixture
def live(tmp_path):
    service = Running(tmp_path/'service.db').start()
    try:
        yield service
    finally:
        service.stop()


def test_real_session_cookie_generated_contract_and_historical_provenance(live):
    for route in ['/api/session','/api/snapshot','/api/history','/api/events']:
        assert live.request('GET', route)[0] == 401
    session, headers = live.login()
    assert {'HttpOnly','SameSite=strict','Path=/'} <= set(part.strip() for part in headers['set-cookie'].split(';'))
    assert session['permissions'] == ['viewer','operator']
    assert session['controller_connected'] is False
    code, headers, snapshot = live.request('GET', '/api/snapshot')
    assert code == 200
    Snapshot.model_validate(snapshot)
    assert snapshot['native_write_enabled'] is False
    assert {i['kind'] for i in snapshot['items']} >= {'role','execution','task','alarm','incident'}
    assert headers['cache-control'] == 'no-store'
    assert headers['x-frame-options'] == 'DENY'
    code, _, history = live.request('GET', '/api/history')
    assert code == 200
    History.model_validate(history)
    assert 0 < len(history['entries']) <= 100
    assert history['cursor'] == snapshot['cursor']
    evidence = next(e for e in history['entries'] if e['label']=='Retained execution observation')
    assert {f['name'] for f in evidence['facts']} >= {'source','feed','mapping_version','native','mapped','evidence_class','quality'}
    assert 'not retained' in next(f['value'] for f in evidence['facts'] if f['name']=='acquisition_at')
    assert 'transcript' not in json.dumps(history)


@pytest.mark.parametrize('headers', [
    {'Origin':'https://evil.invalid'}, {'Host':'evil.invalid'}, {'Origin':'null'},
    {'Host':'127.0.0.1'}, {'Sec-Fetch-Site':'cross-site'},
    {'Host':'localhost:8765'}, {'X-Forwarded-Host':'127.0.0.1:8765','Host':'evil.invalid'},
])
def test_bad_host_origin_boundary_covers_reads_and_login(live, headers):
    assert live.request('GET','/api/session',headers=headers)[0] == 403
    assert live.request('POST','/api/session',{'token':TOKEN},headers=headers)[0] == 403


def test_absent_origin_on_login_and_duplicate_authority_rejected(live):
    connection = http.client.HTTPConnection('127.0.0.1', live.port, timeout=3)
    body = json.dumps({'token':TOKEN})
    connection.request('POST','/api/session',body=body,headers={'Content-Type':'application/json'})
    assert connection.getresponse().status == 403
    connection.close()
    connection = http.client.HTTPConnection('127.0.0.1', live.port, timeout=3)
    connection.putrequest('POST','/api/session')
    connection.putheader('Origin',live.origin)
    connection.putheader('Origin','https://evil.invalid')
    connection.putheader('Content-Length','0')
    connection.endheaders()
    assert connection.getresponse().status == 403
    connection.close()


@pytest.mark.parametrize('csrf',[None,'invalid-csrf','invalid-\u00e9-csrf'])
def test_missing_invalid_csrf_cannot_change_local_alarm(live, csrf):
    live.login()
    before = live.request('GET','/api/snapshot')[2]
    headers = {'X-CSRF-Token':csrf} if csrf else {}
    assert live.request('POST','/api/alarms/acknowledge',{'occurrence_id':'1','position':'operator'},headers)[0] == 403
    after = live.request('GET','/api/snapshot')[2]
    assert after == before


def test_viewer_and_body_position_never_grant_authority(live):
    session, _ = live.login(VIEWER)
    assert session['permissions'] == ['viewer']
    assert live.request('POST','/api/alarms/acknowledge',{'occurrence_id':'1','position':'operator'},
                        {'X-CSRF-Token':session['csrf']})[0] == 403
    session, _ = live.login()
    for position in ['controller','viewer']:
        assert live.request('POST','/api/alarms/acknowledge',{'occurrence_id':'1','position':position},
                            {'X-CSRF-Token':session['csrf']})[0] == 422
    for route in ['/api/native/run','/api/native/stop','/api/executions/start','/api/tasks/update','/api/write-enable']:
        assert live.request('POST', route, {})[0] == 404


@pytest.mark.parametrize('body',[
    {'occurrence_id':'-1','position':'operator'}, {'occurrence_id':True,'position':'operator'},
    {'occurrence_id':'01','position':'operator'}, {'occurrence_id':'1','position':'operator','revision':-1},
    {'occurrence_id':'1','position':'operator','native_write_enabled':True},
])
def test_malformed_revisions_and_mutations_rejected_without_commit(live, body):
    session, _ = live.login()
    before = live.request('GET','/api/snapshot')[2]
    assert live.request('POST','/api/alarms/acknowledge',body,{'X-CSRF-Token':session['csrf']})[0] == 422
    assert live.request('GET','/api/snapshot')[2] == before


@pytest.mark.parametrize('cursor',['bogus','other:1','a'*32+':-1','a'*32+':01','a'*32+':999999999999999999999999', 'x'*1024])
def test_bad_sse_cursors_reset_once_and_recover_full_snapshot(live, cursor):
    live.login()
    frames = live.stream(cursor)
    assert len(frames) == 2
    assert frames[0][0] == 'event: reset'
    assert frames[1][0] == 'event: snapshot'
    wire = json.loads(next(line[6:] for line in frames[1] if line.startswith('data: ')))
    Snapshot.model_validate(wire)
    assert wire['cursor'] == live.request('GET','/api/snapshot')[2]['cursor']


def test_sse_current_reconnect_and_durable_local_acknowledgement(live):
    session, _ = live.login()
    before = live.request('GET','/api/snapshot')[2]
    frames = live.stream(before['cursor'])
    assert len(frames) == 1 and frames[0][0] == 'event: snapshot'
    assert live.request('POST','/api/alarms/acknowledge',{'occurrence_id':'1','position':'operator'},
                        {'X-CSRF-Token':session['csrf']})[0] == 200
    after = live.request('GET','/api/snapshot')[2]
    assert int(after['cursor'].split(':')[1]) > int(before['cursor'].split(':')[1])
    alarm = next(i for i in after['items'] if i['kind']=='alarm')
    assert {'name':'alarm_state','value':'acknowledged'} in alarm['facts']
    assert {'name':'condition','value':'true'} in alarm['facts']
    assert len(live.stream(before['cursor'])) == 1


def test_sse_foreign_future_and_expired_well_formed_cursors_recover_full(live):
    session, _ = live.login()
    original = live.request('GET','/api/snapshot')[2]['cursor']
    identity, revision = original.split(':')
    foreign = ('f' if identity[0] != 'f' else 'e') + identity[1:]
    for cursor in [foreign+':'+revision, identity+':'+str(int(revision)+1000)]:
        frames = live.stream(cursor)
        assert frames[0][0] == 'event: reset'
        assert frames[1][0] == 'event: snapshot'
    for _ in range(130):
        assert live.request('POST','/api/alarms/acknowledge',
            {'occurrence_id':'1','position':'operator'}, {'X-CSRF-Token':session['csrf']})[0] == 200
    frames = live.stream(original)
    assert frames[0][0] == 'event: reset'
    wire = json.loads(next(line[6:] for line in frames[1] if line.startswith('data: ')))
    assert wire['cursor'] == live.request('GET','/api/snapshot')[2]['cursor']


def test_expired_absent_rotated_sessions_and_stream_expiry(live):
    session, _ = live.login()
    old_cookie = live.cookie
    live.login()
    new_cookie = live.cookie
    live.cookie = old_cookie
    assert live.request('GET','/api/session')[0] == 401
    live.cookie = new_cookie
    # Independent current session expires according to the server clock, not client claims.
    live.now[0] += 3601
    for route in ['/api/session','/api/snapshot','/api/history','/api/events']:
        assert live.request('GET',route)[0] == 401
    assert live.request('POST','/api/alarms/acknowledge',{'occurrence_id':'1','position':'operator'},
                        {'X-CSRF-Token':session['csrf']})[0] == 401


def test_service_restart_preserves_historical_provenance_not_live_freshness(tmp_path):
    path = tmp_path/'restart.db'
    a = Running(path).start()
    try:
        a.login()
        before = a.request('GET','/api/snapshot')[2]
        history = a.request('GET','/api/history')[2]
        old_cookie = a.cookie
    finally:
        a.stop()
    b = Running(path).start()
    try:
        b.cookie = old_cookie
        assert b.request('GET','/api/snapshot')[0] == 401
        b.login()
        after = b.request('GET','/api/snapshot')[2]
        retained = b.request('GET','/api/history')[2]
        assert retained['entries'] == history['entries']
        assert before['cursor'].split(':')[0] == after['cursor'].split(':')[0]
        assert int(after['cursor'].split(':')[1]) > int(before['cursor'].split(':')[1])
        for e in [i for i in after['items'] if i['kind']=='execution']:
            assert {'name':'acquired_at','value':'unknown'} in e['facts']
            assert {'name':'lifecycle_quality','value':'unknown'} in e['facts']
    finally:
        b.stop()


def test_single_writer_lock_fails_before_second_open_and_mode_binding(tmp_path):
    a = Running(tmp_path/'one.db').start()
    try:
        app = create_app(a.settings)
        async def attempt():
            async with app.router.lifespan_context(app):
                pytest.fail('Second writer must never start')
        with pytest.raises(BlockingIOError):
            asyncio.run(attempt())
    finally:
        a.stop()
    wrong = create_app(replace(a.settings, source_mode='approved-local'))
    async def wrong_mode():
        async with wrong.router.lifespan_context(wrong):
            pytest.fail('Mode must not relabel retained synthetic facts')
    with pytest.raises(ValueError, match='Source mode'):
        asyncio.run(wrong_mode())


def test_historian_diagnostics_bound_detached_and_restart(tmp_path):
    from workshop.service import initial_synthetic
    path = tmp_path/'owned.db'
    with pytest.raises(ValueError):
        Settings(path,TOKEN,origin='http://0.0.0.0:8765')
    store = Storage(path, initial=initial_synthetic(100))
    try:
        with pytest.raises(ValueError):
            store.retained_diagnostics(limit=101)
        with pytest.raises(ValueError):
            store.retained_diagnostics(limit=True)
        excerpt = store.retained_diagnostics(limit=2)
        assert len(excerpt['records']) == 2
        excerpt['records'].clear()
        assert len(store.retained_diagnostics(limit=2)['records']) == 2
    finally:
        store.close()


def test_unicode_login_rejected_without_500_and_provisioned_utf8_secret_works(tmp_path):
    app = Running(tmp_path/'utf8.db')
    app.settings = replace(app.settings, operator_token='\u00e9'*32)
    app.app = create_app(app.settings, clock=lambda:app.now[0])
    app.server.config.app = app.app
    app.start()
    try:
        assert app.request('POST','/api/session',{'token':'\u2603'*32})[0] == 401
        app.login('\u00e9'*32)
    finally:
        app.stop()
    with pytest.raises(ValueError):
        replace(app.settings, operator_token='x'*257)


def test_expiry_of_open_sse_stream_is_announced(live):
    live.login()
    conn = http.client.HTTPConnection('127.0.0.1',live.port,timeout=3)
    conn.request('GET','/api/events',headers={'Cookie':live.cookie,'Origin':live.origin})
    response = conn.getresponse()
    assert response.status == 200
    while response.readline().strip():
        pass
    live.now[0] += 3601
    assert response.readline().decode().strip() == 'event: session-expired'
    response.close()
    conn.close()


def test_wire_projection_omits_unbounded_observation_arrays_and_bounds_display():
    from workshop.service import initial_synthetic
    from workshop.api import LocalAPI
    from workshop.web_projection import project, facts
    state = initial_synthetic(100)
    execution = next(iter(state.reducer.executions.values()))
    execution.observations *= 1000
    domain = LocalAPI(state.reducer).snapshot(now=100)
    projected = project({'cursor':'a'*32+':0','projection':domain},now=100,source_mode='synthetic')
    wire = next(i for i in projected.items if i.kind=='execution')
    assert not any(f.name.startswith('observations') for f in wire.facts)
    assert next(f.value for f in wire.facts if f.name=='retained_observation_count') == '1000'
    bounded = facts({'large':'x'*20000})[0]
    assert len(bounded.value) <= 16384 and 'omitted' in bounded.value


def test_documented_cli_private_secret_bootstrap_is_exclusive(tmp_path):
    import stat
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable, str(root/'scripts/dev.py'), 'serve',
               '--synthetic', '--state-dir', str(tmp_path/'service'), '--init-secret']
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    secret = tmp_path/'service/synthetic/login-secret'
    original = secret.read_bytes()
    assert len(original.strip()) >= 32
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert original.strip().decode() not in result.stdout + result.stderr
    second = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
    assert second.returncode != 0
    assert secret.read_bytes() == original
