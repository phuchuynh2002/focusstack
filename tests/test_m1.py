from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pytest

from focus_stacker.core.align.ecc import align
from focus_stacker.core.fusion.depth import fuse
from focus_stacker.core.io.images import discover, load, save
from focus_stacker.core.pipeline import run


def test_16bit_roundtrip(tmp_path):
    image = np.random.default_rng(2).integers(0, 65536, (50, 70, 3), dtype=np.uint16)
    for ext in (".png", ".tif"):
        path = tmp_path / ("test" + ext)
        save(path, image.astype(np.float32) / 65535)
        actual = np.rint(load(path) * 65535).astype(np.uint16)
        np.testing.assert_array_equal(actual, image)


def test_depth_fusion_recovers_separate_focused_regions():
    rng = np.random.default_rng(123)
    sharp = rng.random((160, 160, 3), dtype=np.float32)
    blurred = cv2.GaussianBlur(sharp, (0, 0), 3)
    first, second = blurred.copy(), blurred.copy()
    first[:, :80] = sharp[:, :80]
    second[:, 80:] = sharp[:, 80:]
    result, depth = fuse([first, second], [np.ones((160, 160), bool)] * 2, 2, 5)
    assert np.mean(depth[10:-10, 10:65] == 0) > .98
    assert np.mean(depth[10:-10, 95:-10] == 1) > .98
    assert np.mean((result[10:-10, 10:-10] - sharp[10:-10, 10:-10]) ** 2) < .02


def test_ecc_recovers_translation_and_scale():
    rng = np.random.default_rng(19)
    source = cv2.GaussianBlur(rng.random((256, 256, 3), dtype=np.float32), (0, 0), 1)
    matrix = cv2.getRotationMatrix2D((128, 128), 1.0, 1.015)
    matrix[:, 2] += [4, -3]
    moving = cv2.warpAffine(source, matrix, (256, 256))
    aligned, mask, score = align(source, moving)
    assert score > .85
    assert np.mean((source[mask] - aligned[mask]) ** 2) < .003
    assert not mask.all()


def test_smoothed_depth_never_selects_invalid_pixels():
    rng = np.random.default_rng(1)
    a = np.zeros((40, 40, 3), np.float32)
    b = rng.random((40, 40, 3), dtype=np.float32)
    mask = np.ones((40, 40), bool)
    mask[20, 20] = False
    _, depth = fuse([a, b], [np.ones_like(mask), mask], smoothing=5)
    assert depth[20, 20] == 0


def test_cli_outputs_and_input_protection(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    rng = np.random.default_rng(42)
    a = rng.random((80, 80, 3), dtype=np.float32)
    for i, image in enumerate((a, cv2.GaussianBlur(a, (0, 0), 2))):
        save(inputs / f"{i}.png", image)
    output, depth = tmp_path / "result.tif", tmp_path / "depth.png"
    process = subprocess.run([sys.executable, "-m", "focus_stacker.cli", str(inputs), "-o", str(output),
                              "--depth", str(depth), "--no-align"], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert load(output).shape == a.shape
    assert cv2.imdecode(np.fromfile(depth, dtype=np.uint8), cv2.IMREAD_UNCHANGED).dtype == np.uint16
    with pytest.raises(ValueError, match="overwrite"):
        run(discover([str(inputs)]), inputs / "0.png", do_align=False)


def test_dimension_mismatch_and_missing_exif(tmp_path):
    save(tmp_path / "a.png", np.zeros((20, 20, 3), np.float32))
    save(tmp_path / "b.png", np.zeros((21, 20, 3), np.float32))
    with pytest.raises(ValueError, match="dimensions"):
        run(discover([str(tmp_path)]), tmp_path / "out.png", do_align=False)
    with pytest.raises(ValueError, match="EXIF"):
        discover([str(tmp_path)], "time")
