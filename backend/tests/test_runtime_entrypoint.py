# SPDX-License-Identifier: Apache-2.0
"""Live-proof entrypoint with an isolated native fixture, never the live DB."""
import sys
from pathlib import Path

import pytest

from test_hermes_work import native, collector, change


def test_live_proof_requires_current_attempts_not_historical_inventory(native, tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'scripts'))
    import observe_runtime
    monkeypatch.setattr(observe_runtime, 'ROOT', tmp_path)
    monkeypatch.setattr(observe_runtime, 'approved_scope', lambda: collector(native).scope)
    monkeypatch.setattr(sys, 'argv', ['observe_runtime.py', '--approved-local'])
    observe_runtime.main()
    capsys.readouterr()
    change(native, 'DELETE FROM task_runs')
    with pytest.raises(RuntimeError, match='current.*attempt'):
        observe_runtime.main()


def test_runtime_entrypoint_requires_explicit_live_opt_in(tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'scripts'))
    import observe_runtime
    monkeypatch.setattr(observe_runtime, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['observe_runtime.py'])
    with pytest.raises(SystemExit) as error:
        observe_runtime.main()
    assert error.value.code == 2
    assert 'requires --approved-local' in capsys.readouterr().err
    assert not (tmp_path / '.workshop-state').exists()
