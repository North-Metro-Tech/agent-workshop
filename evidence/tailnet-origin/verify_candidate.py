#!/usr/bin/env python3
"""Candidate integrity + result reconciliation; stdlib, no mutation of product/state."""
import configparser
import hashlib
import json
from pathlib import Path
import re
import subprocess
# XML inputs are this run's locally generated pytest JUnit artifacts, not uploads
# or network input; no untrusted XML is accepted by the application.
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = 'd56e3ccf6f332fd4b578fa47cd2e2a7f24a726d4'
EVIDENCE = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


tracked = git('ls-tree', '-r', '--name-only', BASE).decode().splitlines()
protected = [name for name in tracked if name.startswith(('backend/tests/', 'collectors/', 'frontend/'))
             or name in {'requirements.in', 'requirements.lock'}]
for name in protected:
    assert (ROOT/name).read_bytes() == git('show', BASE+':'+name), 'Protected base file changed: '+name
assert git('diff', '--check', BASE) == b''
config = configparser.ConfigParser()
config.read(ROOT/'docs/systemd/agent-workshop-release1.service.d/tailnet-origin.conf')
assert config.sections() == ['Service']
assert dict(config['Service']) == {'environment': 'WORKSHOP_EXTRA_ORIGIN=https://frankenfarm.taile4f46c.ts.net:10000'}

suites = {}
for name in ('baseline', 'backend'):
    tree = ET.parse(EVIDENCE/(name+'.xml'))
    cases = tree.findall('.//testcase')
    suites[name] = {'tests': len(cases), 'failures': len(tree.findall('.//failure')),
                    'errors': len(tree.findall('.//error')), 'skipped': len(tree.findall('.//skipped'))}
    assert not any(suites[name][key] for key in ('failures', 'errors', 'skipped'))
assert suites['baseline']['tests'] == 494
assert suites['backend']['tests'] > suites['baseline']['tests']
# npm's preamble precedes Playwright's JSON when invoked via npm run.
browser_text = (EVIDENCE/'browser.json').read_text()
browser = json.loads(browser_text[browser_text.index('{'):])
assert browser['stats']['expected'] == 4
assert not any(browser['stats'][key] for key in ('unexpected', 'flaky', 'skipped'))
added = '\n'.join(line[1:] for line in git('diff', BASE, '--', 'backend', 'scripts', 'docs/systemd').decode().splitlines()
                  if line.startswith('+') and not line.startswith('+++'))
patterns = {
    'literal_credentials': r'''(?i)(?:api_key|secret|password|token|passwd)\s*=\s*['"][^'"]{6,}['"]''',
    'shell_injection': r'os\.system\(|subprocess.*shell=True',
    'unsafe_eval': r'\beval\(|\bexec\(',
    'unsafe_pickle': r'pickle\.loads?\(',
    'sql_interpolation': r'''execute\(f["']''',
}
findings = {key: re.findall(pattern, added) for key, pattern in patterns.items()}
assert not any(findings.values()), findings
# Never emit the actual installed secret; assert it is absent in every artifact.
secret = Path('/home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/login-secret').read_bytes().strip()
files = sorted(path for path in EVIDENCE.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
assert all(secret not in path.read_bytes() for path in files)
print(json.dumps({'base': BASE, 'protected_files_byte_equal': len(protected),
                  'unit_dropin_exact': True, 'suites': suites, 'new_tests': suites['backend']['tests']-suites['baseline']['tests'],
                  'browser': browser['stats'], 'static_added_line_scan': findings,
                  'actual_login_secret_absent_from_evidence': True}, indent=2, sort_keys=True))
