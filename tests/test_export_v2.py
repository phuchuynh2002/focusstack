import numpy as np
import pytest
from PIL import ImageCms
from focus_stacker.core.io.images import load, profile, save
from focus_stacker.core.io.export import export_image
from focus_stacker.core.pipeline import run


def test_exports_preserve_profile_and_png_pixels(tmp_path):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    image = np.random.default_rng(3).random((24, 30, 3), dtype=np.float32)
    source = tmp_path / 'source.tif'; save(source, image, icc=icc)
    for ext in ('.png', '.jpg', '.tif'):
        output = tmp_path / ('result' + ext)
        report = export_image(source, output)
        assert report['verified'] and profile(output) == icc
        assert load(output).shape == image.shape
        if ext == '.png':
            assert report['bit_depth'] == 16 and np.array_equal(load(output), load(source))
        if ext == '.jpg':
            from PIL import Image, JpegImagePlugin
            assert report['lossy'] and report['bit_depth'] == 8
            with Image.open(output) as jpeg:
                assert JpegImagePlugin.get_sampling(jpeg) == 0
        with pytest.raises(FileExistsError): export_image(source, output)


def test_progressive_preview_tracks_alignment_and_fusion(tmp_path):
    pixels = np.random.default_rng(4).random((60, 70, 3), dtype=np.float32)
    sources = [tmp_path / '1.png', tmp_path / '2.png']
    for path in sources: save(path, pixels)
    seen = []
    run(sources, tmp_path / 'out.tif', do_align=False, preview=lambda image, i, n, stage: seen.append((image.copy(), i, n, stage)))
    assert [item[3] for item in seen] == ['alignment', 'alignment', 'fusion', 'fusion']
    assert all(np.isfinite(item[0]).all() for item in seen)


def test_multiband_fusion_no_black_border_and_constant_image():
    from focus_stacker.core.fusion.pyramid import fuse_pyramid
    a = np.full((65, 79, 3), .7, np.float32)
    b = np.full_like(a, .7)
    mask = np.ones((65, 79), bool); mask[:, :8] = False
    b[:, :8] = 0
    depth = np.ones((65, 79), np.int32); depth[:, :8] = 0
    result = fuse_pyramid([a, b], [np.ones_like(mask), mask], depth)
    np.testing.assert_allclose(result, a, atol=1e-6)
