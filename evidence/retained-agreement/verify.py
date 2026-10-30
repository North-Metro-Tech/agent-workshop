"""Check scope/preserved guards and reproduce the synthetic live-shape report."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(os.environ.get('WORKSHOP_GATE_EVIDENCE', str(Path(__file__).resolve().parent)))
CHECKPOINT = '5ee7ab43697ef8fc5b583341e4c45703184d586b'
PRODUCT = '5f7df84da20206a89d87a8ed692dff537edfefc4'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def original(path):
    return git('show', CHECKPOINT + ':' + path)


def section(text, start, end):
    return text[text.index(start):text.index(end)]


path = 'collectors/workshop_collectors/workflow.py'
old = original(path).decode()
new = (ROOT / path).read_text()
for start, end in [
    ('        # Intentionally independent', '        record = records[identity]'),
    ("        if (attrs.get('workshop.record.id')", "        status = run['status']"),
    ("            attrs['workshop.hermes.process']", '        if not all(checks):'),
    ("    if (projection['native_write_enabled']", "    return {'source_projection_agreement'"),
]:
    assert section(old, start, end) == section(new, start, end), start
preserved = {}
for name in git('ls-tree', '-r', '--name-only', CHECKPOINT).decode().splitlines():
    if name in (path, 'RESUME.md'):
        continue
    data = (ROOT / name).read_bytes()
    assert data == original(name), name
    preserved[name] = hashlib.sha256(data).hexdigest()
assert (ROOT / 'RESUME.md').read_bytes().endswith(original('RESUME.md').split(b'\n', 1)[1])
assert git('merge-base', PRODUCT, 'HEAD').decode().strip() == PRODUCT
sys.path[:0] = [str(ROOT / p) for p in ('backend', 'collectors', 'backend/tests')]
from test_hermes_work import native
from test_workflow_retained import mixed
from workshop_collectors.workflow import verify_agreement
with tempfile.TemporaryDirectory(prefix='retained-shape-') as scratch:
    fixture = Path(scratch)
    source = native.__wrapped__(fixture)
    scenario = mixed.__wrapped__(source, fixture)
    observer, snapshot, storage, _ = next(scenario)
    try:
        report = verify_agreement(observer, snapshot, storage, now=12)
        assert [r['agreement_basis'] for r in report['comparisons']] == [
            'retained_prior_fact', 'retained_prior_fact', 'current', 'current']
        (HERE / 'synthetic-live-shape.json').write_text(json.dumps(report, indent=2) + '\n')
    finally:
        scenario.close()
output = {'checkpoint': CHECKPOINT, 'product_merge_base': PRODUCT,
          'head': git('rev-parse', 'HEAD').decode().strip(),
          'mandatory_expected_raw_and_global_guards': 'BYTE_IDENTICAL',
          'preserved_checkpoint_files': preserved,
          'observe_workflow_changed': False,
          'previous_resume_text_preserved': True,
          'synthetic_shape': {'retained': 2, 'current': 2}}
(HERE / 'boundaries.json').write_text(json.dumps(output, indent=2) + '\n')
print('SCOPE/GUARDS/PRESERVATION/SYNTHETIC-SHAPE VERIFIED', len(preserved), 'preserved checkpoint files')
