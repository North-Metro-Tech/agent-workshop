"""Read-only integrity/provenance check for the scoped policy correction."""
from pathlib import Path
import hashlib
import importlib
import importlib.metadata
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = '60f507670cfa46facd01638dc272d804d7edad73'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

print('Base:', BASE)
print('Python:', sys.version)
print('Test runner:', importlib.metadata.version('pytest'))
for name in ('workshop', 'workshop_collectors'):
    filename = importlib.import_module(name).__file__
    assert filename is not None
    origin = Path(filename).resolve()
    assert origin.is_relative_to(ROOT), (name, origin)
    print('Candidate import:', name, origin.relative_to(ROOT))
lock = (ROOT / 'requirements.lock').read_text()
locked = re.findall(r'^([a-zA-Z0-9_-]+)==([^\s\\]+)', lock, re.M)
assert locked
for name, version in locked:
    installed = importlib.metadata.version(name)
    assert installed == version, (name, version, installed)
    print('Locked runtime:', name, installed)
allowed = {
    'collectors/workshop_collectors/hermes_work.py',
    'backend/tests/test_hermes_work.py',
    'backend/tests/test_hermes_runtime_edges.py',
    'backend/tests/test_phase2_gate.py',
    'docs/hermes-work.md',
    'docs/phase2-workflow.md',
}
changed = set(git('diff', BASE, '--name-only').decode().splitlines())
assert {p for p in changed if not p.startswith('evidence/')} == allowed
source = 'collectors/workshop_collectors/hermes_work.py'
old = git('show', BASE + ':' + source)
assert old.count(b"('coder', 'vitruvius-core')") == 1
assert (ROOT / source).read_bytes() == old.replace(
    b"('coder', 'vitruvius-core')", b"('coder', 'default')")
print('PASS: production diff is exactly one approved profile tuple replacement')
print('PASS: original path/board fences and observe() fail-closed logic byte-identical')
for source in ('collectors/workshop_collectors/demo.py', 'requirements.lock',
               'requirements.in', 'RESUME.md'):
    assert (ROOT / source).read_bytes() == git('show', BASE + ':' + source)
    print('Unchanged:', source, hashlib.sha256((ROOT / source).read_bytes()).hexdigest())
logs = ROOT / 'evidence' / 'profile-scope-remediation'
before = (logs / 'regression-before.txt').read_text()
after = (logs / 'regression-after.txt').read_text()
full = (logs / 'backend-full.txt').read_text()
assert '3 failed, 3 passed' in before
assert '6 passed, 31 deselected' in after
assert '472 passed' in full
assert len(re.findall(r'^backend/tests/.* PASSED', full, re.M)) == 472
assert not re.search(r'\b(?:FAILED|SKIPPED)\b|\b\d+ skipped\b', full)
print('PASS: recorded before/after regression and 472 named backend passes; zero skips')
print('No native source acquisition performed by this verifier; no dependency install.')
print('Stage 1 only. Independent approval, integration and twelve-scenario rerun remain pending.')
