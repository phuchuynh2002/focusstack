from pathlib import Path
import json

import numpy as np
import pytest
from PIL import ImageCms

from focus_stacker.core.io.images import load, profile, save
from focus_stacker.core.pipeline import run_task
from focus_stacker.core.task import RenderSettings, StackTask


def test_task_pipeline_preserves_tiff_and_reports_settings(tmp_path):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    rng = np.random.default_rng(42)
    source = rng.random((40, 40, 3), dtype=np.float32)
    paths = tuple(tmp_path / f'{i}.tif' for i in range(2))
    for p in paths:
        save(p, source, icc=icc)
    output, report = tmp_path / 'stack.tif', tmp_path / 'report.json'
    settings = RenderSettings(align=False, radius=2, smoothing=3, rendered_only=True)
    task = StackTask(paths, output, settings, report_output=report)
    events = []
    run_task(task, progress=lambda percent, message: events.append(percent))
    data = json.loads(report.read_text())
    assert data['input_count'] == 2 and data['settings'] == {'align': False, 'radius': 2, 'smoothing': 3}
    assert data['output']['verified'] and profile(output) == icc
    np.testing.assert_allclose(load(output), source, atol=1 / 65535)
    assert events[0] == 1 and events[-1] == 100
    assert '--rendered-only' in settings.worker_args() and '--no-align' in settings.worker_args()


def test_task_rejects_invalid_settings_and_paths(tmp_path):
    with pytest.raises(ValueError):
        RenderSettings(radius=float('nan'))
    with pytest.raises(ValueError):
        RenderSettings(smoothing=2)
    a, b = tmp_path / 'a.tif', tmp_path / 'b.tif'
    with pytest.raises(ValueError, match='Duplicate'):
        StackTask((a, a), b)
    with pytest.raises(ValueError, match='overwrite'):
        StackTask((a, b), a)


def test_automatic_parameters_and_resource_estimate(tmp_path):
    from focus_stacker.utils.resources import automatic_settings, estimate_resources
    assert automatic_settings((3000, 4500, 3)) == (3.0, 7)
    assert automatic_settings((20, 20, 3)) == (1.0, 3)
    assert estimate_resources((3000, 4500, 3), 5)['estimated_gib'] > estimate_resources((3000, 4500, 3), 2)['estimated_gib']
    assert '--automatic' in RenderSettings(automatic=True).worker_args()
