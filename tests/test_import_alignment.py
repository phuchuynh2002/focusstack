import json
from unittest.mock import patch
import numpy as np
from focus_stacker.core.io.images import save
from focus_stacker.core.pipeline import run
from focus_stacker.workers.prealign import PrealignJob


def test_prealignment_cache_reused_only_for_unchanged_inputs(tmp_path):
    image = np.random.default_rng(123).random((96, 96, 3), dtype=np.float32)
    paths = [tmp_path / 'a.tif', tmp_path / 'b.tif']
    for p in paths: save(p, image)
    job = PrealignJob(paths, 1, False, False)
    errors = []
    job.signals.done.connect(lambda unused, error: errors.append(error))
    job.run()
    assert errors == [''] and job.cache
    from pathlib import Path
    cache = Path(job.cache.name)
    assert len(json.loads((cache / 'manifest.json').read_text())['sha256']) == 2
    with patch('focus_stacker.core.pipeline.align', side_effect=AssertionError('cache not used')):
        run(paths, tmp_path / 'result.tif', report_output=tmp_path / 'report.json', prealigned_cache=cache)
    save(paths[1], image * .9)
    with patch('focus_stacker.core.pipeline.align', side_effect=ValueError('alignment rerun')):
        try:
            run(paths, tmp_path / 'result2.tif', report_output=tmp_path / 'report2.json', prealigned_cache=cache)
        except ValueError as exc:
            assert str(exc) == 'alignment rerun'
        else:
            raise AssertionError('changed input must not reuse cache')
    job.cache.cleanup()
