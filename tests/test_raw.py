from pathlib import Path

import numpy as np
import pytest
import tifffile

from focus_stacker.core.io.formats import RAW
from focus_stacker.core.io.images import discover, load, profile
from focus_stacker.core.pipeline import run


@pytest.mark.parametrize('extension', sorted(RAW))
def test_discover_raw_files_and_folders(tmp_path, extension):
    paths = [tmp_path / ('ảnh 01' + extension.upper()), tmp_path / ('ảnh 02' + extension)]
    for path in paths:
        path.touch()
    assert discover([str(tmp_path)]) == paths
    assert discover([str(p) for p in reversed(paths)]) == paths


def write_test_dng(path):
    """A small, real uncompressed Bayer DNG, decoded by LibRaw (no mock)."""
    mosaic = np.random.default_rng(4).integers(500, 3000, (64, 64), dtype=np.uint16)
    tags = [
        (50706, 'B', 4, (1, 4, 0, 0), False),
        (50707, 'B', 4, (1, 1, 0, 0), False),
        (50708, 's', 0, 'FocusStack test camera', False),
        (33421, 'H', 2, (2, 2), False),
        (33422, 'B', 4, (0, 1, 1, 2), False),
        (50717, 'I', 1, 4095, False),
        (50721, '2i', 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1), False),
        (50728, '2I', 3, (1, 1, 1, 1, 1, 1), False),
        (50778, 'H', 1, 21, False),
    ]
    tifffile.imwrite(path, mosaic, photometric=32803, metadata=None, extratags=tags)


def test_real_raw_decode_and_stack(tmp_path):
    paths = [tmp_path / 'ảnh 01.DNG', tmp_path / 'ảnh 02.dng']
    for path in paths:
        write_test_dng(path)
    decoded = load(paths[0])
    assert decoded.shape == (64, 64, 3)
    assert decoded.dtype == np.float32
    assert np.isfinite(decoded).all()
    assert 0 <= decoded.min() < decoded.max() <= 1
    output = tmp_path / 'stack.tif'
    run(paths, output, do_align=False)
    np.testing.assert_allclose(load(output), decoded, atol=1/65535)
    assert profile(output) == profile(paths[0])


def test_invalid_raw_has_actionable_error(tmp_path):
    path = tmp_path / 'broken.RAF'
    path.write_bytes(b'not a RAW file')
    with pytest.raises(ValueError, match='Cannot decode RAW.*RGB 16-bit TIFF'):
        load(path)


def test_raw_auto_reports_shared_white_balance_and_bad_raw(tmp_path):
    import json
    paths = [tmp_path / 'a.dng', tmp_path / 'b.dng']
    for path in paths:
        write_test_dng(path)
    report = tmp_path / 'report.json'
    events = []
    run(paths, tmp_path / 'stack.tif', do_align=False, automatic=True,
        desktop_inputs=True, report_output=report, progress=lambda p, m: events.append(m))
    result = json.loads(report.read_text())
    assert result['settings']['automatic'] and result['raw_development']['white_balance']
    assert result['raw_development']['capture_one_adjustments'] == 'not applied'
    assert any('Ước lượng RAM' in message for message in events)
    paths[1].write_bytes(b'invalid')
    with pytest.raises(ValueError, match='Cannot decode RAW'):
        run(paths, tmp_path / 'bad.tif', do_align=False, desktop_inputs=True)
