# SPDX-License-Identifier: Apache-2.0
"""Additive PR#9 boundary regressions over real loopback TCP, never a live fleet."""
import asyncio
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

from workshop.service import Boundary, Settings
from test_service import Running, TOKEN, live

EXTRA = 'https://frankenfarm.taile4f46c.ts.net:10000'
HOST = urlsplit(EXTRA).netloc
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tailnet(tmp_path):
    # Real transport is still loopback HTTP as it is behind Serve. Authority is
    # the literal browser-facing extra; no proxy-header trust is required.
    frontend = tmp_path/'dist'
    frontend.mkdir()
    (frontend/'index.html').write_text('<!doctype html><title>Boundary fixture</title>')
    service = Running(tmp_path/'service.db', extra_origin=EXTRA, frontend=frontend).start()
    try:
        yield service
    finally:
        service.stop()


def wire(service, method, path, headers=(), body=None):
    conn = http.client.HTTPConnection('127.0.0.1', service.port, timeout=3)
    payload = json.dumps(body).encode() if body is not None else b''
    conn.putrequest(method, path, skip_host=True)
    for name, value in headers:
        conn.putheader(name, value)
    conn.putheader('Content-Length', str(len(payload)))
    if body is not None:
        conn.putheader('Content-Type', 'application/json')
    conn.endheaders(payload)
    response = conn.getresponse()
    # h11 rejects duplicate Host before ASGI and may reset with an unread POST
    # body; assert that real rejection status without requiring its error body.
    result = response.status, dict(response.getheaders()), response.read() if response.status != 400 else b''
    conn.close()
    return result


def test_extra_origin_get_login_csrf_mutation_and_primary_still_work(tailnet):
    approved = [('Host', HOST), ('Origin', EXTRA)]
    for headers in (approved, [('Host', HOST)], [('Host', urlsplit(tailnet.origin).netloc)]):
        code, security, body = wire(tailnet, 'GET', '/', headers)
        assert code == 200 and b'Boundary fixture' in body
        assert security['cache-control'] == 'no-store'
        assert security['x-frame-options'] == 'DENY'
        assert not any(k.lower().startswith('access-control-') for k in security)
    code, headers, _ = wire(tailnet, 'POST', '/api/session', approved, {'token': TOKEN})
    assert code == 200
    cookie = headers['set-cookie'].split(';')[0]
    authenticated = approved + [('Cookie', cookie)]
    code, _, body = wire(tailnet, 'GET', '/api/session', authenticated)
    assert code == 200
    session = json.loads(body)
    assert session['permissions'] == ['viewer', 'operator']
    assert session['controller_connected'] is False
    mutation = {'occurrence_id': '1', 'position': 'operator'}
    assert wire(tailnet, 'POST', '/api/alarms/acknowledge', authenticated, mutation)[0] == 403
    assert wire(tailnet, 'POST', '/api/alarms/acknowledge',
                authenticated + [('X-CSRF-Token', session['csrf'])], mutation)[0] == 200
    code, _, body = wire(tailnet, 'GET', '/api/snapshot', authenticated)
    assert code == 200
    snapshot = json.loads(body)
    assert snapshot['native_write_enabled'] is False
    alarm = next(item for item in snapshot['items'] if item['kind'] == 'alarm')
    assert {'name': 'alarm_state', 'value': 'acknowledged'} in alarm['facts']
    # The original login/mutation path remains usable with extra enabled.
    tailnet.login()


@pytest.mark.parametrize('host,origin', [
    ('evil.invalid:10000', EXTRA),
    ('frankenfarm.taile4f46c.ts.net', EXTRA),
    ('frankenfarm.taile4f46c.ts.net:443', EXTRA),
    ('frankenfarm.taile4f46c.ts.net:10001', EXTRA),
    ('sibling.taile4f46c.ts.net:10000', EXTRA),
    ('sub.frankenfarm.taile4f46c.ts.net:10000', EXTRA),
    ('frankenfarm.taile4f46c.ts.net.attacker.invalid:10000', EXTRA),
    ('FRANKENFARM.taile4f46c.ts.net:10000', EXTRA),
    (HOST, 'http://frankenfarm.taile4f46c.ts.net:10000'),
    (HOST, 'https://frankenfarm.taile4f46c.ts.net'),
    (HOST, 'https://frankenfarm.taile4f46c.ts.net:10001'),
    (HOST, 'https://evil.invalid'),
    (HOST, 'https://sibling.taile4f46c.ts.net:10000'),
    (HOST, EXTRA + '/'),
    (HOST, EXTRA + ', http://127.0.0.1:8765'),
    (HOST, 'null'),
    (HOST, ''),
])
def test_extra_enabled_rejects_nonexact_host_or_origin_for_reads_and_mutations(tailnet, host, origin):
    headers = [('Host', host), ('Origin', origin)]
    assert wire(tailnet, 'GET', '/api/session', headers)[0] == 403
    assert wire(tailnet, 'POST', '/api/session', headers, {'token': TOKEN})[0] == 403


@pytest.mark.parametrize('additional', [
    [],
    [('X-Forwarded-Origin', EXTRA), ('X-Forwarded-Host', HOST), ('X-Forwarded-Proto', 'https')],
    [('Forwarded', f'host={HOST};proto=https')],
])
def test_extra_mutation_requires_real_origin_not_forwarded_replacement(tailnet, additional):
    assert wire(tailnet, 'POST', '/api/session', [('Host', HOST)] + additional, {'token': TOKEN})[0] == 403


def test_forwarded_headers_neither_rescue_foreign_headers_nor_override_approved(tailnet):
    spoof = [('X-Forwarded-Host', HOST), ('X-Forwarded-Proto', 'https'),
             ('X-Forwarded-Origin', EXTRA), ('Forwarded', f'host={HOST};proto=https')]
    assert wire(tailnet, 'GET', '/', [('Host', 'evil.invalid')] + spoof)[0] == 403
    assert wire(tailnet, 'POST', '/api/session',
                [('Host', HOST), ('Origin', 'https://evil.invalid')] + spoof, {'token': TOKEN})[0] == 403
    foreign = [('X-Forwarded-Host', 'evil.invalid'), ('X-Forwarded-Proto', 'http'),
               ('X-Forwarded-Origin', 'https://evil.invalid'), ('Forwarded', 'host=evil.invalid;proto=http')]
    assert wire(tailnet, 'GET', '/', [('Host', HOST), ('Origin', EXTRA)] + foreign)[0] == 200


@pytest.mark.parametrize('additional', [
    [('Host', HOST)],
    [('Origin', EXTRA)],
    [('Origin', 'https://evil.invalid')],
    [('Cookie', 'a=1'), ('Cookie', 'b=2')],
    [('Sec-Fetch-Site', 'cross-site')],
])
def test_extra_does_not_weaken_duplicate_header_or_fetch_site_rejection(tailnet, additional):
    headers = [('Host', HOST), ('Origin', EXTRA)] + additional
    assert wire(tailnet, 'GET', '/api/session', headers)[0] in {400, 403}
    assert wire(tailnet, 'POST', '/api/session', headers, {'token': TOKEN})[0] in {400, 403}


def test_extra_enabled_query_and_preflight_still_rejected(tailnet):
    headers = [('Host', HOST), ('Origin', EXTRA)]
    assert wire(tailnet, 'GET', '/api/session?token=never-a-real-secret', headers)[0] == 403
    code, result, _ = wire(tailnet, 'OPTIONS', '/api/session', headers + [
        ('Access-Control-Request-Method', 'POST')])
    assert code == 405
    assert not any(k.lower().startswith('access-control-') for k in result)


def test_without_extra_config_tailnet_is_still_rejected(live):
    headers = [('Host', HOST), ('Origin', EXTRA)]
    assert wire(live, 'GET', '/api/session', headers)[0] == 403
    assert wire(live, 'POST', '/api/session', headers, {'token': TOKEN})[0] == 403


@pytest.mark.parametrize('extra', [
    'http://frankenfarm.taile4f46c.ts.net:10000',
    'https://example.com:10000', 'https://127.0.0.1:10000',
    'https://100.100.100.100:10000', 'https://[::1]:10000',
    'https://ts.net:10000', 'https://notts.net:10000',
    'https://frankenfarm.taile4f46c.ts.net.attacker.invalid:10000',
    'https://user@frankenfarm.taile4f46c.ts.net:10000',
    'https://:password@frankenfarm.taile4f46c.ts.net:10000',
    EXTRA + '/', EXTRA + '/path', EXTRA + '?token=x', EXTRA + '#fragment',
    EXTRA + '?', EXTRA + '#', EXTRA + ',' + EXTRA, '',
    EXTRA + ' ', '\t' + EXTRA, EXTRA + '\n', EXTRA.replace('farm', 'farm\t'),
    'https://frankenfarm.taile4f46c.ts.net:0',
    'https://frankenfarm.taile4f46c.ts.net:65536',
    'https://frankenfarm.taile4f46c.ts.net:port',
    'https://frankenfarm.taile4f46c.ts.net:',
    'https://frankenfarm.taile4f46c.ts.net:010000',
    'https://*.taile4f46c.ts.net:10000', 'https://.ts.net:10000',
    'https://-bad.ts.net:10000', 'https://bad-.ts.net:10000',
    'https://a..ts.net:10000', 'https://a_b.ts.net:10000',
    'https://é.ts.net:10000', 'https://' + 'a'*64 + '.ts.net:10000',
    'https://frankenfarm.taile4f46c.ts.net.:10000',
])
def test_extra_config_guard_rejects_unsafe_or_nonorigin_values(tmp_path, extra):
    with pytest.raises(ValueError):
        Settings(tmp_path/'never-created.db', TOKEN, extra_origin=extra)
    assert not (tmp_path/'never-created.db').exists()


@pytest.mark.parametrize('extra', [None, EXTRA, 'https://other.owner.ts.net', 'https://other.owner.ts.net:443'])
def test_optional_single_https_tailnet_origin_config(tmp_path, extra):
    settings = Settings(tmp_path/'unused.db', TOKEN, extra_origin=extra)
    assert settings.extra_origin == extra


def test_asgi_missing_or_duplicate_authority_is_rejected_before_app():
    async def forbidden(scope, receive, send):
        pytest.fail('Invalid authority must not reach application')
    boundary = Boundary(forbidden, origin='http://127.0.0.1:8765', extra_origin=EXTRA)
    async def check(headers):
        messages = []
        async def send(message):
            messages.append(message)
        await boundary({'type': 'http', 'method': 'GET', 'path': '/', 'headers': headers}, None, send)
        assert messages[0]['status'] == 403
    for headers in ([], [(b'host', HOST.encode()), (b'host', HOST.encode())]):
        asyncio.run(check(headers))


@pytest.mark.parametrize('extra', ['http://bad.ts.net:10000', 'https://example.com', 'https://127.0.0.1'])
def test_cli_rejects_invalid_extra_at_startup_without_historian(tmp_path, extra):
    env = dict(os.environ, WORKSHOP_EXTRA_ORIGIN=extra, WORKSHOP_LOGIN_TOKEN=TOKEN)
    result = subprocess.run([sys.executable, str(ROOT/'scripts/dev.py'), 'serve',
                             '--synthetic', '--state-dir', str(tmp_path)],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Extra origin must be' in result.stderr
    assert TOKEN not in result.stdout + result.stderr
    assert not (tmp_path/'synthetic/historian.db').exists()


def test_cli_plumbs_extra_env_and_preserves_loopback_bind(monkeypatch, tmp_path):
    import importlib.util
    import uvicorn
    spec = importlib.util.spec_from_file_location('tailnet_serve_entrypoint', ROOT/'scripts/serve.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frontend = tmp_path/'frontend/dist'
    frontend.mkdir(parents=True)
    (frontend/'index.html').write_text('<!doctype html><title>CLI fixture</title>')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setenv('WORKSHOP_EXTRA_ORIGIN', EXTRA)
    monkeypatch.setenv('WORKSHOP_LOGIN_TOKEN', TOKEN)
    captured = {}
    def run(app, **options):
        captured.update(app=app, **options)
    monkeypatch.setattr(uvicorn, 'run', run)
    assert module.main(['--synthetic', '--state-dir', str(tmp_path)]) == 0
    assert captured['host'] == '127.0.0.1'
    assert captured['port'] == 8765
    assert captured['proxy_headers'] is False
    assert captured['workers'] == 1
    middleware = captured['app'].user_middleware[0]
    assert middleware.kwargs['extra_origin'] == EXTRA
    assert middleware.kwargs['origin'] == 'http://127.0.0.1:8765'
