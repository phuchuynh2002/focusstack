import json
import threading
import time

import numpy as np
import pytest
import tifffile
from PIL import Image

from focus_stacker.core.io.loader import load_stack, convert_result_for_saving
from focus_stacker.core.io.images import load
from focus_stacker.core.pipeline import run


def test_parallel_order_depth_and_callback(tmp_path, monkeypatch):
    from focus_stacker.core.io import loader
    a, b = tmp_path/'a.png', tmp_path/'b.tif'
    Image.new('RGB', (20, 20), (255, 0, 128)).save(a)
    tifffile.imwrite(b, np.full((20,20,3), 32768, np.uint16), photometric='rgb')
    real = loader.load_single_image
    def delayed(path, *args, **kwargs):
        if path == a: time.sleep(.05)
        return real(path, *args, **kwargs)
    monkeypatch.setattr(loader, 'load_single_image', delayed)
    events=[]; caller=threading.get_ident()
    stack=load_stack([a,b], verify_files=True, progress_callback=lambda i,n,m: events.append((i,n,m,threading.get_ident())))
    assert [x.path for x in stack.items]==[a,b]
    assert stack.reference_dtype==np.uint16
    np.testing.assert_allclose(stack.images[0][0,0], [1,0,128/255], atol=1e-7)
    np.testing.assert_allclose(stack.images[1],32768/65535)
    assert all(e[3]==caller for e in events) and [e[0] for e in events]==[1,2]
    assert 'b.tif' in events[0][2] and all(x.sha256 for x in stack.items)
    preserved=load_stack([a,b], target_mode='preserve')
    assert preserved.images[0].dtype==np.uint16 and preserved.images[0][0,0,2]==128*257


def test_grayscale_alpha_resize_and_report(tmp_path):
    a,b=tmp_path/'a.bmp',tmp_path/'b.png'
    Image.new('L',(24,20),128).save(a)
    Image.new('RGBA',(12,10),(255,0,0,64)).save(b)
    with pytest.raises(ValueError,match='dimensions'): load_stack([a,b])
    output,report=tmp_path/'out.tif',tmp_path/'report.json'
    run([a,b],output,do_align=False,desktop_inputs=True,auto_resize_mismatched=True,report_output=report)
    data=json.loads(report.read_text())
    assert data['output']['verified'] and load(output).shape==(20,24,3)
    assert data['sources'][0]['transformations']==['grayscale expanded to RGB']
    assert data['sources'][1]['original_shape']==[10,12,3]
    assert 'alpha discarded' in data['sources'][1]['transformations']
    assert any('resized' in s for s in data['sources'][1]['transformations'])
    with pytest.raises(ValueError): run([a,b],output,rendered_only=True)


def test_webp_and_bad_inputs(tmp_path):
    a,b=tmp_path/'a.webp',tmp_path/'b.bmp'
    for p in (a,b): Image.new('RGB',(20,20),(255,0,0)).save(p,lossless=True)
    np.testing.assert_array_equal(load_stack([a,b]).images[0][0,0],[1,0,0])
    for kwargs in ({'max_workers':0},{'target_mode':'wrong'}):
        with pytest.raises(ValueError): load_stack([a,b],**kwargs)
    with pytest.raises(ValueError,match='Duplicate'): load_stack([a,a])
    bad=tmp_path/'bad.png'; bad.touch()
    with pytest.raises(ValueError,match='bad.png'): load_stack([a,bad])
    floating=tmp_path/'float.tif'
    tifffile.imwrite(floating,np.zeros((20,20,3),np.float32),photometric='rgb')
    with pytest.raises(ValueError,match='8/16-bit'): load_stack([a,floating])


def test_output_conversion_endpoints():
    values=np.array([-1,0,.5,1,2],np.float32)
    np.testing.assert_array_equal(convert_result_for_saving(values,np.uint16),[0,0,32768,65535,65535])
    np.testing.assert_array_equal(convert_result_for_saving(np.array([0,255],np.uint8),np.uint16),[0,65535])
    with pytest.raises(ValueError,match='non-finite'): convert_result_for_saving(np.array([np.nan]))
