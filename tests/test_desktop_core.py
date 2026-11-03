import numpy as np
import tifffile
from PIL import Image, ImageCms
import pytest

from focus_stacker.core.io.images import load, save, profile, discover
from focus_stacker.core.fusion.depth import fuse
from focus_stacker.core.pipeline import run


def test_tiff_orientation_once(tmp_path):
    a = np.arange(12*18*3, dtype=np.uint16).reshape(12, 18, 3)
    p = tmp_path / 'oriented.tif'
    tifffile.imwrite(p, a, photometric='rgb', extratags=[(274, 'H', 1, 6, False)])
    np.testing.assert_allclose(load(p), np.rot90(a, 3).astype(np.float32)/65535)


def test_nested_capture_time(tmp_path):
    for name, time in [('a', '2026:01:02 12:00:00'), ('b', '2026:01:01 12:00:00')]:
        exif = Image.Exif(); exif[34665] = {36867: time}
        Image.new('RGB', (20, 20)).save(tmp_path / f'{name}.jpg', exif=exif)
    assert [p.stem for p in discover([str(tmp_path)], 'time')] == ['b', 'a']


def test_profile_preserved_and_mismatch_rejected(tmp_path):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    a = np.random.default_rng(4).random((40, 40, 3), dtype=np.float32)
    paths = [tmp_path / 'a.tif', tmp_path / 'b.tif']
    for path in paths: save(path, a, icc=icc)
    out = tmp_path / 'out.tif'
    run(paths, out, do_align=False)
    assert profile(out) == icc
    save(paths[1], a)
    with pytest.raises(ValueError, match='ICC'):
        run(paths, out, do_align=False)


def test_warp_border_does_not_win():
    y, x = np.indices((100, 100))
    reference = np.repeat((.5 + .02*((x+y)%2))[:, :, None], 3, axis=2).astype(np.float32)
    flat = np.full_like(reference, .5); flat[:, :20] = 0
    mask = np.ones((100, 100), bool); mask[:, :20] = False
    _, depth = fuse([reference, flat], [np.ones_like(mask), mask], radius=3, smoothing=1)
    assert not depth[:, 20:30].any()
