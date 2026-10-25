"""Synthetic-only verification. Never open native or installed historian state."""
from pathlib import Path
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(os.environ.get('WORKSHOP_GATE_EVIDENCE', str(Path(__file__).resolve().parent)))
HERE.mkdir(parents=True, exist_ok=True)
PY = '/home/aaron/hermes-agent/.venv/bin/python'
results = {}


def run(args, name, *, cwd=ROOT, env=None, expected=0, raw=False):
    proc = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=360)
    (HERE / name).write_bytes(proc.stdout if raw else
        ('COMMAND: ' + repr(args) + '\n').encode() + proc.stdout +
        ('\nEXIT_CODE: ' + str(proc.returncode) + '\n').encode())
    results[name] = {'exit_code': proc.returncode, 'expected_exit': expected}
    print(name, proc.returncode, flush=True)
    assert proc.returncode == expected, name
    return proc.stdout


def backend():
    env = dict(os.environ, PYTHONPATH=str(ROOT / '.venv/lib/python3.11/site-packages') +
               ':' + str(ROOT / 'backend') + ':' + str(ROOT / 'collectors'))
    for args, name, count in [
        (['--ignore=backend/tests/test_workflow_retained.py'], 'baseline', 568),
        (['backend/tests/test_workflow_retained.py'], 'focused', 34),
        ([], 'backend', 602),
    ]:
        run([PY, '-m', 'pytest', '-q', *args, '--junitxml=' + str(HERE / (name + '.xml'))],
            name + '.txt', env=env)
        # Only our own just-generated pytest JUnit is parsed, never external XML.
        suite = ET.parse(HERE / (name + '.xml')).getroot().find('testsuite')
        assert suite is not None
        assert int(suite.attrib['tests']) == count
        assert all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped'))
    run([str(ROOT / '.venv/bin/python'), 'scripts/dev.py', 'schema', '--check'], 'schema.txt')
    for command in ('demo', 'collector-demo', 'check'):
        output = run([PY, 'scripts/dev.py', command], command + '.txt')
        if command != 'check':
            assert output == run([PY, 'scripts/dev.py', command], command + '-repeat.txt')


def frontend():
    for command, extra in [('test', ['--', '--run']), ('typecheck', []), ('build', [])]:
        run(['npm', '--prefix', 'frontend', 'run', command, *extra], 'frontend-' + command + '.txt')
    env = dict(os.environ, WORKSHOP_E2E_PYTHON=str(ROOT / '.venv/bin/python'),
               WORKSHOP_E2E_CHROMIUM='/home/aaron/.local/bin/chromium',
               PLAYWRIGHT_JSON_OUTPUT_NAME=str(HERE / 'browser.json'))
    for key in ('WORKSHOP_LOGIN_TOKEN', 'WORKSHOP_E2E_TOKEN', 'WORKSHOP_E2E_URL'):
        env.pop(key, None)
    scene = ROOT / 'evidence/phase3-remediation/browser-scene.png'
    original = scene.read_bytes()
    try:
        run(['npm', '--prefix', 'frontend', 'run', 'test:e2e', '--', '--reporter=list,json'],
            'browser.txt', env=env)
        (HERE / 'synthetic-browser-scene.png').write_bytes(scene.read_bytes())
    finally:
        scene.write_bytes(original)
    stats = json.loads((HERE / 'browser.json').read_text())['stats']
    assert stats['expected'] == 4 and all(stats[k] == 0 for k in ('skipped', 'unexpected', 'flaky'))
    audit = run(['sfw', 'npm', 'audit', '--include=dev', '--json'], 'npm-audit.json',
                cwd=ROOT / 'frontend', expected=1, raw=True)
    prod = run(['sfw', 'npm', 'audit', '--omit=dev', '--json'], 'npm-production-audit.json',
               cwd=ROOT / 'frontend', raw=True)
    dev, production = json.loads(audit), json.loads(prod)
    assert dev['metadata']['vulnerabilities']['total'] == dev['metadata']['vulnerabilities']['high'] == 1
    assert set(dev['vulnerabilities']) == {'happy-dom'} and b'GHSA-834v-8h66-3h79' in audit
    assert production['metadata']['vulnerabilities']['total'] == 0


if __name__ == '__main__':
    mode = sys.argv[1]
    {'backend': backend, 'frontend': frontend}[mode]()
    (HERE / (mode + '-commands.json')).write_text(json.dumps(results, indent=2) + '\n')
    print(mode.upper(), 'VERIFIED', flush=True)
