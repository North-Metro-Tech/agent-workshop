# SPDX-License-Identifier: Apache-2.0
"""Phase 1 structural interlock and clean-checkout developer/demo tests."""
import ast
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from workshop.api import LocalAPI
from workshop.ingest import Ingest, SourceBinding
from workshop.storage import Storage
from test_source_scope import configured, event, wire
from workshop.ingest import Acquisition


@pytest.mark.parametrize('position', ['viewer', 'operator', 'controller'])
@pytest.mark.parametrize('path', ['/native/run', '/native/stop', '/native/retry',
    '/native/write-enable', '/executions/start', '/tasks/update', '/hooks/install'])
def test_phase1_interlock_no_native_route_even_for_authorized_controller(tmp_path, position, path):
    store = Storage(tmp_path / 'synthetic.db', initial=configured())
    store.cloudevents('a', wire(event()), context=Acquisition(10, 10, 'boot'), source_cursor=1)
    for api in (LocalAPI(store.read().reducer), LocalAPI(storage=store)):
        before = api.snapshot(now=10)
        with pytest.raises(LookupError):
            api.request('POST', path, position=position, authorized=True, now=10)
        assert api.snapshot(now=10) == before
        assert api.native_write_enabled is False
        with pytest.raises(AttributeError):
            api.native_write_enabled = True
    store.close()


def test_phase1_interlock_explicit_closed_public_mutation_surface():
    expected = {
        LocalAPI: {'snapshot', 'acknowledge', 'request'},
        Ingest: {'cloudevents', 'otlp'},
        Storage: {'close', 'read', 'transaction', 'snapshot', 'replay', 'cloudevents',
                  'otlp', 'begin_snapshot', 'snapshot_page', 'finish_snapshot'},
    }
    for cls, allowed in expected.items():
        actual = {name for name, fn in inspect.getmembers(cls, inspect.isfunction)
                  if not name.startswith('_')}
        assert actual == allowed
        assert not any('executor' in name or 'callback' in name or 'write_enabled' in name
                       for name in inspect.signature(cls).parameters)
    assert 'native_write_enabled' not in inspect.signature(SourceBinding).parameters
    root = Path(__file__).parents[1] / 'workshop'
    # Allowlist imports, not a keyword claim: any new execution/network module
    # or arbitrary dynamic import forces an intentional interlock re-review.
    allowed = {'__future__', 'base64', 'binascii', 'collections', 'contextlib', 'copy',
        'dataclasses', 'datetime', 'hashlib', 'json', 'math', 'pathlib', 're', 'sqlite3',
        'typing', 'urllib', 'uuid', 'argparse', 'sys'}
    for path in root.rglob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split('.')[0] in allowed for a in node.names), path
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split('.')[0] in allowed, path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'eval', 'exec', '__import__'}, path


def test_phase1_synthetic_demo_is_deterministic_json():
    from workshop.demo import snapshot
    a, b = snapshot(), snapshot()
    assert a == b
    assert a['native_write_enabled'] is False
    assert len(a['executions']) >= 3
    assert len({(e['task']['source_instance'], e['task']['namespace'], e['task']['native_id'])
                for e in a['executions']}) >= 3
    assert {role['availability'] for role in a['roles']} >= {'busy', 'unknown', 'available'}
    assert all(e['lifecycle']['source'].startswith('urn:synthetic:') for e in a['executions'])
    assert json.loads(json.dumps(a)) == a


def test_phase1_install_demo_and_test_commands_from_clean_source_copy(tmp_path):
    root = Path(__file__).parents[2]
    checkout = tmp_path / 'clean checkout'
    checkout.mkdir()
    # Copy tracked source layout, not local .venv/cache or any native records.
    for name in ('backend', 'scripts'):
        shutil.copytree(root / name, checkout / name,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    shutil.copy(root / 'pytest.ini', checkout / 'pytest.ini')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    for action in ('install', 'demo'):
        result = subprocess.run([sys.executable, 'scripts/dev.py', action], cwd=checkout,
            env=env, text=True, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        if action == 'demo':
            assert json.loads(result.stdout)['native_write_enabled'] is False
    result = subprocess.run([str(checkout / '.venv/bin/python'), '-m', 'workshop.demo'],
        cwd=checkout, env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['native_write_enabled'] is False
    # Exercise dev.py test dispatch on the complete original A01–A04 fixture
    # module, avoiding recursive execution of this clean-checkout test itself.
    result = subprocess.run([sys.executable, 'scripts/dev.py', 'test',
        'backend/tests/test_truth_model.py', '-q'], cwd=checkout, env=env,
        text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'passed' in result.stdout
