import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import ImageCms
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtGui import QFileOpenEvent, QImage
from PySide6.QtCore import Qt, QItemSelectionModel
from focus_stacker.ui.main_window import MainWindow as Window
from focus_stacker.main import Application
from focus_stacker.core.io.images import save, load
from focus_stacker.core.workflow import digest, stack_record
from test_raw import write_test_dng


def pump(app, condition, seconds=30):
    end = time.monotonic()+seconds
    while condition() and time.monotonic()<end:
        app.processEvents(); time.sleep(.01)
    assert not condition(), 'UI timed out'


def sample_inputs(tmp_path, count=2):
    image = np.random.default_rng(1).random((80,80,3),dtype=np.float32)
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    paths=[]
    for i in range(count):
        p=tmp_path/f'{i}.tif'; save(p,image,icc=icc); paths.append(str(p))
    return image, paths


def test_worker_result_and_cancel(tmp_path):
    app = QApplication.instance() or Application([])
    image, paths = sample_inputs(tmp_path)
    w=Window(); w.show(); w.add_paths(paths); w.align.setChecked(False)
    pump(app, lambda: bool(w.jobs))
    assert w.files.count()==2 and len(w.selected_paths())==2
    assert w.files.currentItem() is not None
    assert all(not w.files.item(i).icon().isNull() for i in range(2))
    assert len(w.preview.scene().items())==1
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is not None, w.log.toPlainText()
    assert w.progress.value()==100 and w.report['output']['verified']
    assert w.live_path.exists() and not QImage(str(w.live_path)).isNull()
    np.testing.assert_allclose(load(w.result),image,atol=1/65535)
    pump(app,lambda: bool(w.jobs))
    exported=tmp_path/'saved.tif'
    with patch.object(QFileDialog,'getSaveFileName',return_value=(str(exported), '')):
        w.export()
    import json
    saved_report=json.loads(exported.with_suffix('.tif.focusstack.json').read_text())
    assert saved_report['output']['sha256']==digest(exported)
    assert stack_record(exported)['input_count']==2
    png = tmp_path / 'saved.png'
    with patch.object(QFileDialog,'getSaveFileName',return_value=(str(png), 'PNG 16-bit')):
        w.export()
    assert png.exists() and np.array_equal(load(png), load(w.result))
    with patch.object(QFileDialog,'getSaveFileName',return_value=(paths[0], '')), patch.object(QMessageBox,'warning') as warning:
        original=digest(paths[0]); w.export()
        assert warning.call_count==1 and digest(paths[0])==original
    w.files.setCurrentRow(0)  # plain click: previewing a source keeps the unsaved result
    assert len(w.selected_paths())==2 and w.result is not None and w.export_button.isEnabled()
    w.files.selectAll()
    w.start(); w.add_paths(paths); assert len(w.queued)==2
    w.cancel(); pump(app,lambda: w.proc is not None)
    assert w.result is None and not w.export_button.isEnabled()
    w.close()


def test_raw_prompt_and_fileopen_batch(tmp_path):
    app=QApplication.instance() or Application([])
    _, paths=sample_inputs(tmp_path)
    w=Window(); app.window=w
    raw=tmp_path/'test.DNG'; write_test_dng(raw)
    w.add_paths([str(raw)])
    pump(app,lambda: bool(w.jobs))
    assert w.files.count()==1 and len(w.selected_paths()) == 1
    w.clear_files()
    for p in paths:
        QApplication.sendEvent(app,QFileOpenEvent(p))
    pump(app,lambda: bool(app.pending) or bool(w.jobs))
    assert w.files.count()==2 and len(w.selected_paths())==2
    QApplication.sendEvent(app,QFileOpenEvent(paths[0]))
    pump(app,lambda: bool(app.pending))
    assert w.files.count()==2
    w.files.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert len(w.selected_paths())==1 and 'chọn ghép 1' in w.count_label.text()
    with patch.object(QMessageBox,'warning') as warning:
        w.start(); assert warning.call_count==1 and w.proc is None
    w.clear_files(); assert not w.preview.scene().items()
    w.close(); app.window=None


def test_add_more_and_stack_selected(tmp_path):
    app=QApplication.instance() or Application([])
    _, paths=sample_inputs(tmp_path, 5)
    w=Window(); w.show(); w.align.setChecked(False)
    w.add_paths(paths[:2]); w.add_paths(paths[2:])
    pump(app, lambda: bool(w.jobs))
    assert w.files.count()==5 and len(w.selected_paths())==5
    w.files.item(4).setCheckState(Qt.CheckState.Unchecked)
    assert 'Ghép stack 4' in w.start_button.text()
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is not None, w.log.toPlainText()
    assert w.report['input_count']==4 and w.run_paths==[str(Path(p).resolve()) for p in paths[:4]]
    w.files.clearSelection()
    w.files.setCurrentRow(4)
    w.remove_button.click()
    assert w.files.count()==4 and w.result is None
    jpg=tmp_path/'a.jpg'; save(jpg, np.zeros((80,80,3),np.float32))
    w.add_paths([paths[0], str(jpg)]); pump(app, lambda: bool(w.jobs))
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is None and 'a.jpg' in w.log.toPlainText()
    w.close()


def test_folder_import_and_preview_does_not_change_checks(tmp_path):
    app = QApplication.instance() or Application([])
    _, paths = sample_inputs(tmp_path, 5)
    w = Window(); w.show(); w.add_paths([str(tmp_path)])
    pump(app, lambda: bool(w.jobs))
    assert w.files.count() == 5 and len(w.selected_paths()) == 5
    w.files.setCurrentRow(2)
    assert len(w.selected_paths()) == 5
    w.files.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert len(w.selected_paths()) == 4
    w.select_all_button.click()
    assert len(w.selected_paths()) == 5
    w.add_paths([str(tmp_path)])
    assert w.files.count() == 5
    w.close()


def test_raw_folder_stack_auto_and_manual(tmp_path):
    app = QApplication.instance() or Application([])
    for i in range(2):
        write_test_dng(tmp_path / f'{i}.dng')
    w = Window(); w.show(); w.add_paths([str(tmp_path)]); w.align.setChecked(False)
    pump(app, lambda: bool(w.jobs))
    assert w.files.count() == 2 and len(w.selected_paths()) == 2
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is not None, w.log.toPlainText()
    assert w.report['settings']['automatic'] and w.report['raw_development']['color_space'] == 'sRGB'
    assert 'Ước lượng RAM' in w.log.toPlainText()
    w.auto.setChecked(False); w.radius.setValue(2); w.smooth.setValue(3)
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is not None and w.report['settings']['radius'] == 2
    w.result = None; w.close()


def test_settings_roundtrip(tmp_path):
    from PySide6.QtCore import QSettings
    from focus_stacker.utils.settings import save_window
    app = QApplication.instance() or Application([])
    settings = QSettings(str(tmp_path/'window.ini'), QSettings.Format.IniFormat)
    window = Window(settings=settings)
    # Stay inside the offscreen display; Qt clamps restored windows to the screen.
    bounds = app.primaryScreen().availableGeometry()
    window.resize(min(640, bounds.width()-80), min(480, bounds.height()-80))
    save_window(window, settings)
    geometry = settings.value('window/geometry')
    assert geometry is not None and not geometry.isEmpty()
    restored = Window(settings=settings)
    assert restored.size() == window.size(), (restored.size(), window.size(), bounds)
    restored.close(); window.close()


def test_notebook_loader_controls_and_preview(tmp_path):
    from PIL import Image
    app = QApplication.instance() or Application([])
    for name,size in [('a.bmp',(80,80)),('b.webp',(60,60))]:
        Image.new('RGB',size,(200,20,60)).save(tmp_path/name,lossless=True)
    w=Window(); w.show(); w.add_paths([str(tmp_path)]); w.align.setChecked(False)
    w.load_workers.setValue(2); w.resize_inputs.setChecked(True)
    pump(app,lambda: bool(w.jobs))
    assert len(w.selected_paths())==2
    assert all(not w.files.item(i).icon().isNull() for i in range(2))
    w.start(); pump(app,lambda: w.proc is not None)
    assert w.result is not None, w.log.toPlainText()
    assert w.report['loading']['resize_mismatched'] and w.report['output']['verified']
    assert any('resized' in change for change in w.report['sources'][1]['transformations'])
    w.rendered_only.setChecked(True)
    w.start(); pump(app,lambda: w.proc is not None)
    assert w.result is None and not w.export_button.isEnabled()
    w.close()


def test_select_none_and_progressive_controls(tmp_path):
    app = QApplication.instance() or Application([])
    _, paths = sample_inputs(tmp_path, 3)
    w = Window(); w.show(); w.add_paths(paths)
    pump(app, lambda: bool(w.jobs))
    w.deselect_all_button.click()
    assert not w.selected_paths() and 'chọn ghép 0' in w.count_label.text()
    w.select_all_button.click()
    assert len(w.selected_paths()) == 3
    w.preview.set_processing(True)
    assert w.preview._timer.isActive()
    w.preview.set_processing(False)
    assert not w.preview._timer.isActive()
    w.close()


def test_import_prealignment_cache_and_reveal(tmp_path):
    app = QApplication.instance() or Application([])
    _, paths = sample_inputs(tmp_path, 2)
    w = Window(); w.show(); w.add_paths(paths)
    pump(app, lambda: w.alignment_timer.isActive() or bool(w.alignment_jobs), seconds=30)
    assert w.alignment_cache is not None, w.log.toPlainText()
    w.start(); pump(app, lambda: w.proc is not None)
    assert w.result is not None, w.log.toPlainText()
    assert 'Dùng căn chỉnh đã kiểm tra' in w.log.toPlainText()
    pump(app, lambda: bool(w.jobs))
    assert w.replay_button.isEnabled()
    w.replay_reveal()
    assert w.reveal_timer.isActive() and w.reveal_index == 1
    w.reveal_timer.stop()
    w.result = None; w.close()


def test_auto_stack_after_import(tmp_path):
    app = QApplication.instance() or Application([])
    _, paths = sample_inputs(tmp_path, 2)
    w = Window(); w.show(); w.auto_stack.setChecked(True); w.add_paths(paths)
    pump(app, lambda: w.result is None and (w.proc is not None or w.alignment_timer.isActive() or bool(w.alignment_jobs)))
    assert w.result is not None, w.log.toPlainText()
    assert 'Dùng căn chỉnh đã kiểm tra' in w.log.toPlainText()
    pump(app, lambda: bool(w.jobs))
    w.result = None; w.close()
