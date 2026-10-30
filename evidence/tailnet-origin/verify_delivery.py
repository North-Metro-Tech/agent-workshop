#!/usr/bin/env python3
"""Read-back delivery evidence. Never updates unit, checkout, Serve or native data.

Use --expect-extra disabled before deployment; enabled after reviewed deployment.
Only mutation is in-memory login; never acknowledge alarms or alter historian.
"""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

BASE = Path('/home/aaron/.local/share/agent-workshop/release1')
STATE = BASE/'state-schema2/approved-local'
LOCAL = 'http://127.0.0.1:8765'
EXTRA = 'https://frankenfarm.taile4f46c.ts.net:10000'


def get_status(url, headers=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, headers=headers or {}), timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def authenticated(origin):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
    # The provisioned secret stays only in memory; never print payload/cookies.
    body = json.dumps({'token': (STATE/'login-secret').read_text().strip()}).encode()
    request = urllib.request.Request(origin+'/api/session', data=body, headers={
        'Origin': origin, 'Content-Type': 'application/json'})
    with opener.open(request, timeout=15) as response:
        assert response.status == 200
    with opener.open(origin+'/api/snapshot', timeout=15) as response:
        snapshot = json.load(response)
    with opener.open(origin+'/api/session', timeout=15) as response:
        session = json.load(response)
    assert snapshot['native_write_enabled'] is False
    assert session['controller_connected'] is False
    return {'cursor': snapshot['cursor'], 'source_mode': snapshot['source_mode'],
            'native_write_enabled': False, 'controller_connected': False,
            'authenticated': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-extra', required=True, choices=('disabled', 'enabled'))
    parser.add_argument('--before', type=Path, help='Compare original live historian identity/inode and binding')
    args = parser.parse_args()
    statuses = {
        'loopback': get_status(LOCAL+'/'),
        'tailnet_https': get_status(EXTRA+'/'),
        'foreign_host': get_status(LOCAL+'/', {'Host': 'evil.invalid'}),
        'missing_port': get_status(LOCAL+'/', {'Host': 'frankenfarm.taile4f46c.ts.net'}),
        'wrong_port': get_status(LOCAL+'/', {'Host': 'frankenfarm.taile4f46c.ts.net:10001'}),
        'wrong_scheme_origin': get_status(LOCAL+'/', {'Host': 'frankenfarm.taile4f46c.ts.net:10000',
            'Origin': 'http://frankenfarm.taile4f46c.ts.net:10000'}),
    }
    assert statuses == {'loopback': 200, 'tailnet_https': 200 if args.expect_extra == 'enabled' else 403,
                        'foreign_host': 403, 'missing_port': 403, 'wrong_port': 403, 'wrong_scheme_origin': 403}, statuses
    unit = subprocess.run(['systemctl', '--user', 'show', 'agent-workshop-release1.service',
                           '-p', 'ActiveState', '-p', 'SubState', '-p', 'Restart', '-p', 'UnitFileState',
                           '-p', 'MainPID', '-p', 'Environment'], check=True, capture_output=True, text=True).stdout
    assert 'ActiveState=active' in unit and 'SubState=running' in unit
    assert 'Restart=no' in unit and 'UnitFileState=disabled' in unit
    # Do not persist the Environment line, which could contain future secrets.
    has_extra = 'WORKSHOP_EXTRA_ORIGIN='+EXTRA in unit
    assert has_extra == (args.expect_extra == 'enabled')
    serve = json.loads(subprocess.run(['tailscale', 'serve', 'status', '--json'],
                        check=True, capture_output=True, text=True).stdout)
    assert not any(serve.get('AllowFunnel', {}).values()), 'Funnel must remain disabled'
    assert serve['Web']['frankenfarm.taile4f46c.ts.net:10000']['Handlers']['/']['Proxy'] == LOCAL
    local = authenticated(LOCAL)
    result = {'statuses': statuses, 'local_session': local,
              'historian_inode': (STATE/'historian.db').stat().st_ino,
              'historian_device': (STATE/'historian.db').stat().st_dev,
              'binding_sha256': hashlib.sha256((STATE/'historian.service-binding.json').read_bytes()).hexdigest(),
              'unit_state': [line for line in unit.splitlines() if not line.startswith('Environment=')],
              'unit_extra_present': has_extra, 'serve': serve}
    if args.expect_extra == 'enabled':
        result['tailnet_session'] = authenticated(EXTRA)
    if args.before:
        before = json.loads(args.before.read_text())
        for field in ('historian_inode', 'historian_device', 'binding_sha256', 'serve'):
            assert before[field] == result[field], 'Unexpected replacement/change: '+field
        old_identity, old_revision = before['local_session']['cursor'].split(':')
        identity, revision = local['cursor'].split(':')
        assert identity == old_identity and int(revision) > int(old_revision)
        result['original_historian_and_binding_preserved'] = True
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
