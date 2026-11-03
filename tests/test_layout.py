"""Integration boundaries that must survive package moves and desktop packaging."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_core_has_no_qt_dependency_and_legacy_paths_share_implementations():
    code = '''
import sys
from focus_stacker.core.pipeline import run_task
from focusstack.pipeline import run_task as legacy
assert legacy is run_task
assert not any(name.startswith('PySide6') for name in sys.modules)
'''
    process = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src')))
    assert process.returncode == 0, process.stderr


def test_old_and_new_cli_entry_points():
    results = []
    for module in ('focusstack.cli', 'focus_stacker.cli'):
        p = subprocess.run([sys.executable, '-m', module, '--help'], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src')))
        assert p.returncode == 0, p.stderr
        assert '--desktop-inputs' in p.stdout and '--report' in p.stdout
        results.append(p.stdout)
    assert results[0] == results[1]


def test_asset_resolution_in_source_and_bundle(tmp_path, monkeypatch):
    from focus_stacker.utils.assets import asset_path
    assert asset_path('theme.qss').is_file()
    (tmp_path/'assets').mkdir()
    bundled = tmp_path/'assets/theme.qss'; bundled.write_text('/* bundle */')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert asset_path('theme.qss') == bundled
