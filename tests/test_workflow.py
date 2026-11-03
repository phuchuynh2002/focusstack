import json

import cv2
import numpy as np
import pytest
from PIL import ImageCms

from focus_stacker.core.io.images import save, load, profile
from focus_stacker.core.pipeline import run
from focus_stacker.core.workflow import digest, stack_record, preview_rgb, validate_rendered


def inputs(tmp_path):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    sharp = np.random.default_rng(45).random((80, 80, 3), dtype=np.float32)
    blur = cv2.GaussianBlur(sharp, (0, 0), 3)
    a, b = blur.copy(), blur.copy()
    a[:, :40] = sharp[:, :40]; b[:, 40:] = sharp[:, 40:]
    paths = [tmp_path/'ảnh 01.tif', tmp_path/'ảnh 02.tif']
    for path, image in zip(paths, [a, b]): save(path, image, icc=icc)
    return paths


def test_scan_and_verified_stack(tmp_path):
    paths = inputs(tmp_path)
    report, output, focus_map = tmp_path/'report.json', tmp_path/'out.tif', tmp_path/'map.png'
    events = []
    run(paths, output, do_align=False, report_output=report, map_output=focus_map,
        scan_only=True, rendered_only=True, progress=lambda p,m: events.append(p))
    scanned = json.loads(report.read_text())
    assert scanned['status'] == 'scanned' and not output.exists()
    assert focus_map.exists() and len(scanned['regions']) == 64
    assert scanned['sources_used'] == 2
    assert scanned['regions'][0]['source_index'] == 0
    assert scanned['regions'][7]['source_index'] == 1
    assert events == sorted(events) and events[-1] == 100
    run(paths, output, do_align=False, report_output=report, rendered_only=True)
    finished = json.loads(report.read_text())
    assert finished['status'] == 'completed'
    assert finished['output']['sha256'] == digest(output)
    assert finished['output']['verified']
    assert profile(output) == profile(paths[0])
    assert load(output).shape == (80,80,3)
    assert stack_record(output)['input_count'] == 2
    assert stack_record(paths[0]) is None
    assert preview_rgb(output, size=40).size == (40,40)


def test_rendered_input_guard(tmp_path):
    paths = inputs(tmp_path)
    with pytest.raises(ValueError, match='TIFF 16-bit'):
        validate_rendered([tmp_path/'source.arw'])
    save(paths[1], np.zeros((80,80,3), np.float32))
    with pytest.raises(ValueError, match='ICC'):
        validate_rendered(paths)


def test_same_images_warn_no_multiple_source_contribution(tmp_path):
    paths = inputs(tmp_path)
    paths[1].write_bytes(paths[0].read_bytes())
    report = tmp_path/'report.json'
    run(paths, tmp_path/'out.tif', do_align=False, report_output=report, rendered_only=True)
    result = json.loads(report.read_text())
    assert result['sources_used'] == 1
    assert any('Chỉ một ảnh' in s for s in result['warnings'])


def test_compressed_tiff_preview(tmp_path):
    import tifffile
    p = tmp_path/'compressed.tif'
    pixels = np.arange(40*40*3,dtype=np.uint16).reshape(40,40,3)
    tifffile.imwrite(p,pixels,photometric='rgb',compression='lzw')
    assert preview_rgb(p).size == (40,40)
