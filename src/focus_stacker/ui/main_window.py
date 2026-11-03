"""Main window: inputs, controls, progress and results."""
from __future__ import annotations
import codecs
import json
import logging
from pathlib import Path
import time
from PySide6.QtCore import QProcess, Qt, QTimer, QSize, QThreadPool, QItemSelectionModel
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog, QCheckBox, QSpinBox,
    QDoubleSpinBox, QLabel, QProgressBar, QPlainTextEdit, QMessageBox, QFormLayout, QGroupBox)
from focus_stacker.core.io.formats import FORMATS, RAW, file_filter
from focus_stacker.core.workflow import stack_record, digest
from focus_stacker.core.task import RenderSettings
from focus_stacker.core.io.export import export_image
from focus_stacker.ui.canvas import Preview
from focus_stacker.workers.preview import PreviewJob
from focus_stacker.workers.prealign import PrealignJob
from focus_stacker.workers.process import StackProcess
from focus_stacker.utils.cache import create_task_cache
from focus_stacker.utils.settings import restore_window, save_window
LOG = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings
        self.setWindowTitle('FocusStack 3.0.0')
        self.resize(1280, 800)
        self.setAcceptDrops(True)
        self.proc = None
        self.temp = None
        self.result = None
        self.report = None
        self.cancelled = False
        self.run_paths = []
        self.queued = []
        self.jobs = {}
        self.alignment_jobs = []
        self.alignment_cache = None
        self.alignment_generation = 0
        self.alignment_pool = QThreadPool(self)
        self.alignment_pool.setMaxThreadCount(1)
        self.alignment_timer = QTimer(self)
        self.alignment_timer.setSingleShot(True)
        self.alignment_timer.timeout.connect(self.start_import_alignment)
        self.reveal_timer = QTimer(self)
        self.reveal_timer.setInterval(500)
        self.reveal_timer.timeout.connect(self.reveal_step)
        self.reveal_image = None
        self.auto_reveal_pending = False
        self.preview_token = 0
        self.current_preview = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.elapsed = QTimer(self)
        self.elapsed.setInterval(1000)
        self.elapsed.timeout.connect(self.update_elapsed)
        root = QWidget(); self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        library = QGroupBox('Thư viện ảnh'); left = QVBoxLayout(library); layout.addWidget(library, 1)
        self.count_label = QLabel('Đã nhận 0 ảnh · chọn ghép 0 ảnh')
        self.count_label.setWordWrap(True); left.addWidget(self.count_label)
        self.files = QListWidget(); self.files.setIconSize(QSize(96, 72))
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files.currentItemChanged.connect(self.source_preview)
        self.files.itemChanged.connect(self.selection_changed)
        self.select_all_button = QPushButton('Chọn tất cả'); self.select_all_button.clicked.connect(self.check_all)
        self.deselect_all_button = QPushButton('Bỏ chọn tất cả'); self.deselect_all_button.clicked.connect(self.uncheck_all)
        self.remove_button = QPushButton('Bỏ ảnh đã chọn khỏi danh sách'); self.remove_button.clicked.connect(self.remove_selected)
        self.add_button = QPushButton('Thêm ảnh / RAW…'); self.add_button.clicked.connect(self.pick_files)
        self.folder_button = QPushButton('Thêm thư mục…'); self.folder_button.clicked.connect(self.pick_folder)
        self.capture_button = QPushButton('Thư mục Capture One…'); self.capture_button.clicked.connect(self.pick_capture_folder)
        self.cancel_align_button = QPushButton('Hủy căn chỉnh khi nhập'); self.cancel_align_button.setEnabled(False)
        self.cancel_align_button.clicked.connect(self.cancel_import_alignment)
        self.clear_button = QPushButton('Xóa danh sách'); self.clear_button.clicked.connect(self.clear_files)
        self.queued_button = QPushButton('Thêm ảnh đang chờ'); self.queued_button.clicked.connect(self.import_queued)
        self.queued_button.setVisible(False)
        hint = QLabel('Đánh dấu ảnh cần ghép; bấm vào tên ảnh để xem trước. Chọn dòng để bỏ ảnh khỏi danh sách.')
        hint.setWordWrap(True)
        for widget in (self.add_button, self.folder_button, self.capture_button, self.cancel_align_button, self.queued_button, hint, self.files,
                       self.select_all_button, self.deselect_all_button, self.remove_button, self.clear_button):
            left.addWidget(widget)
        viewer = QGroupBox('Xem trước và kết quả'); center = QVBoxLayout(viewer); layout.addWidget(viewer, 3)
        self.preview_label = QLabel('Chưa có ảnh. Preview thu nhỏ; ảnh gốc giữ kích thước đầy đủ.')
        self.preview_label.setWordWrap(True); center.addWidget(self.preview_label)
        self.preview = Preview(); center.addWidget(self.preview)
        zoom = QHBoxLayout()
        for label, factor in [('Vừa khung', None), ('100%', 1), ('200%', 2), ('400%', 4)]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, f=factor: self.preview.fit_image() if f is None else self.preview.exact_zoom(f))
            zoom.addWidget(button)
        center.addLayout(zoom)
        self.legend = QLabel(''); self.legend.setWordWrap(True); center.addWidget(self.legend)
        self.result_button = QPushButton('Xem TIFF đã ghép'); self.result_button.clicked.connect(self.show_result)
        self.result_button.setEnabled(False); center.addWidget(self.result_button)
        self.map_button = QPushButton('Xem bản đồ vùng lấy nét'); self.map_button.clicked.connect(self.show_map)
        self.map_button.setEnabled(False); center.addWidget(self.map_button)
        self.replay_button = QPushButton('Phát lại vùng đóng góp'); self.replay_button.setEnabled(False)
        self.replay_button.clicked.connect(self.replay_reveal); center.addWidget(self.replay_button)
        render = QGroupBox('Thiết lập và xử lý'); right = QVBoxLayout(render); layout.addWidget(render, 2)
        self.auto = QCheckBox('Tự chọn thông số theo kích thước ảnh'); self.auto.setChecked(True)
        right.addWidget(self.auto)
        self.auto_stack = QCheckBox('Tự ghép sau khi căn chỉnh nhập xong')
        right.addWidget(self.auto_stack)
        form = QFormLayout(); right.addLayout(form)
        self.radius = QDoubleSpinBox(); self.radius.setRange(0, 20); self.radius.setValue(3)
        self.smooth = QSpinBox(); self.smooth.setRange(1, 31); self.smooth.setSingleStep(2); self.smooth.setValue(5)
        self.load_workers = QSpinBox(); self.load_workers.setRange(1, 8); self.load_workers.setValue(2)
        self.resize_inputs = QCheckBox('Cho phép đổi kích thước về ảnh đầu tiên')
        self.resize_inputs.setToolTip('Nội suy lại pixel; chỉ bật khi chấp nhận thay đổi kích thước ảnh nguồn.')
        self.rendered_only = QCheckBox('Capture One: chỉ TIFF RGB 16-bit có ICC')
        self.rendered_only.setToolTip('Xuất TIFF đã áp dụng chỉnh sửa từ Capture One trước khi nhập.')
        form.addRow('Luồng nạp ảnh', self.load_workers)
        right.addWidget(self.resize_inputs); right.addWidget(self.rendered_only)
        self.align = QCheckBox('Căn chỉnh ảnh'); self.align.setChecked(True)
        form.addRow('Radius', self.radius); form.addRow('Smoothing (lẻ)', self.smooth)
        right.addWidget(self.align)
        self.auto.toggled.connect(lambda active: (self.radius.setEnabled(not active), self.smooth.setEnabled(not active)))
        self.radius.setEnabled(False); self.smooth.setEnabled(False)
        self.start_button = QPushButton('Ghép stack 0 ảnh đã chọn'); self.start_button.clicked.connect(self.start)
        self.cancel_button = QPushButton('Hủy'); self.cancel_button.setEnabled(False); self.cancel_button.clicked.connect(self.cancel)
        self.export_button = QPushButton('Lưu ảnh + báo cáo…'); self.export_button.setEnabled(False); self.export_button.clicked.connect(self.export)
        for widget in (self.start_button, self.cancel_button, self.export_button): right.addWidget(widget)
        self.status = QLabel('Chưa ghép — cần ít nhất 2 ảnh cùng ICC; không trộn RAW với ảnh đã render.'); self.status.setWordWrap(True); right.addWidget(self.status)
        self.timer_label = QLabel(''); right.addWidget(self.timer_label)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0); right.addWidget(self.progress)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); right.addWidget(self.log)
        self.summary = QPlainTextEdit(); self.summary.setReadOnly(True)
        self.summary.setPlaceholderText('Kết quả ghép: ảnh đóng góp, vùng cần kiểm tra, xác minh TIFF.'); right.addWidget(self.summary)
        right.addWidget(QLabel('Xử lý tự động cục bộ · không dùng AI/API.'))
        if self.settings is not None: restore_window(self, self.settings)

    def selected_paths(self):
        # List order, not click order, so the stack keeps its focus sequence.
        return [self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())
                if self.files.item(i).checkState() == Qt.CheckState.Checked]

    def update_count(self):
        n = len(self.selected_paths())
        self.count_label.setText(f'Đã nhận {self.files.count()} ảnh · chọn ghép {n} ảnh')
        self.start_button.setText(f'Ghép stack {n} ảnh đã chọn')
        if self.proc is None and self.files.count() and n < 2:
            self.status.setText('Đánh dấu ít nhất 2 ảnh để ghép. '
                                'Nếu chỉ nhận 1 ảnh, kiểm tra Edit All Selected Variants trong Capture One.')

    def invalidate(self):
        self.result = None; self.report = None
        self.reveal_timer.stop(); self.reveal_image = None; self.replay_button.setEnabled(False)
        self.current_preview = None
        for button in (self.result_button, self.export_button, self.map_button): button.setEnabled(False)
        self.summary.clear()
        self.status.setText('Bộ ảnh thay đổi — cần ghép lại.')

    def check_all(self):
        for i in range(self.files.count()):
            self.files.item(i).setCheckState(Qt.CheckState.Checked)

    def selection_changed(self, item=None):
        # Clicking a row to compare must not discard an unsaved result.
        self.update_count()
        if self.result and set(self.selected_paths()) != set(self.run_paths):
            self.status.setText(f'Kết quả hiện tại là ghép từ {len(self.run_paths)} ảnh trước đó. '
                                'Bấm Ghép stack để ghép lại theo lựa chọn mới.')

    def remove_selected(self):
        self.cancel_import_alignment()
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))
        self.invalidate(); self.update_count()
        if not self.files.count(): self.clear_files()
        else: self.schedule_import_alignment()

    def clear_files(self):
        self.cancel_import_alignment()
        self.files.clear(); self.invalidate(); self.update_count()
        self.current_preview = None; self.preview.scene().clear()
        self.preview_label.setText('Chưa có ảnh.')

    def add_paths(self, paths):
        if self.proc is not None:
            self.queued.extend(paths)
            self.queued_button.setText(f'Thêm {len(self.queued)} đường dẫn đang chờ')
            self.queued_button.setVisible(True); self.queued_button.setEnabled(False)
            self.log.appendPlainText('Ảnh nhận thêm được giữ trong hàng chờ; không thay đổi bộ đang ghép.')
            return
        known = {self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())}
        expanded = []
        for value in paths:
            path = Path(value).expanduser()
            try: expanded.extend(path.iterdir() if path.is_dir() else [path])
            except OSError as exc: self.log.appendPlainText(str(exc))
        added = []
        for path in sorted(expanded, key=lambda p: str(p).casefold()):
            if not path.is_file() or path.suffix.lower() not in FORMATS: continue
            value = str(path.resolve())
            if value in known: continue
            known.add(value)
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, value); item.setToolTip(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.files.addItem(item)
            added.append(value)
            if stack_record(path):
                self.log.appendPlainText(f'{path.name}: có metadata kết quả FocusStack trước đây. Không suy ra lịch sử ảnh khác khi thiếu metadata.')
        if added:
            self.invalidate()
            self.schedule_import_alignment()
            self.log.appendPlainText(f'Nhận thêm {len(added)} ảnh; tổng {self.files.count()}.')
            for value in added: self.request_preview(value, display=False)
            # Set the preview without changing checked inputs.
            self.files.setCurrentRow(self.files.count()-len(added), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.update_count()
        if not added:
            self.log.appendPlainText('Không có ảnh mới được thêm. Kiểm tra thư mục, định dạng hoặc ảnh đã có trong danh sách.')

    def cancel_import_alignment(self):
        self.cancel_align_button.setEnabled(False)
        self.alignment_generation += 1
        self.alignment_timer.stop()
        for job in self.alignment_jobs: job.cancel()
        if self.alignment_cache:
            self.alignment_cache.cleanup(); self.alignment_cache = None

    def schedule_import_alignment(self):
        self.cancel_import_alignment()
        if self.files.count() >= 2:
            self.cancel_align_button.setEnabled(True)
            self.alignment_timer.start(700)

    def start_import_alignment(self):
        paths = sorted((self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())), key=str.casefold)
        if len(paths) < 2: return
        job = PrealignJob(paths, self.load_workers.value(), self.resize_inputs.isChecked(), self.rendered_only.isChecked())
        job.generation = self.alignment_generation
        self.alignment_jobs.append(job)
        job.signals.progress.connect(self.import_alignment_progress)
        job.signals.done.connect(self.import_alignment_finished)
        self.alignment_pool.start(job)

    def import_alignment_progress(self, message):
        if self.proc is None:
            self.status.setText(message)

    def import_alignment_finished(self, job, error):
        if job in self.alignment_jobs: self.alignment_jobs.remove(job)
        if job.generation == self.alignment_generation: self.cancel_align_button.setEnabled(False)
        if job.generation != self.alignment_generation or error:
            if job.cache: job.cache.cleanup()
            if error and error != 'cancelled':
                self.log.appendPlainText(f'Căn chỉnh khi nhập chưa hoàn tất: {error}. Có thể ghép lại hoặc tắt căn chỉnh.')
            return
        if self.alignment_cache: self.alignment_cache.cleanup()
        self.alignment_cache = job.cache
        self.log.appendPlainText(f'Đã căn chỉnh {len(job.paths)} ảnh khi nhập; dùng lại nếu lựa chọn và file không đổi.')
        if self.proc is None:
            self.status.setText(f'Đã căn chỉnh {len(job.paths)} ảnh khi nhập.')
            if self.auto_stack.isChecked() and len(self.selected_paths()) >= 2: self.start()

    def pick_capture_folder(self):
        candidates = [Path.home() / 'Pictures' / 'Capture One Catalog' / 'Output',
                      Path.home() / 'Pictures' / 'Capture One Session' / 'Output', Path.home() / 'Pictures']
        start = next((str(p) for p in candidates if p.is_dir()), str(Path.home()))
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh đã xuất từ Capture One', start)
        if folder: self.add_paths([folder])

    def import_queued(self):
        paths, self.queued = self.queued, []
        self.queued_button.setVisible(False)
        self.add_paths(paths)

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Chọn ảnh nguồn', '', file_filter())
        self.add_paths(files)

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh')
        if folder: self.add_paths([folder])

    def request_preview(self, path, display=True):
        self.preview_token += 1
        token = self.preview_token
        if display:
            self.legend.clear()
            self.current_preview = (path, token)
            self.preview.scene().clear()
            self.preview_label.setText(f'Đang đọc preview: {Path(path).name}')
        job = PreviewJob(path, token, full_resolution=display)
        self.jobs[token] = job
        job.signals.done.connect(self.preview_ready)
        self.pool.start(job, 1 if display else 0)

    def preview_ready(self, path, token, image, error):
        self.jobs.pop(token, None)
        if not image.isNull():
            icon = QIcon(QPixmap.fromImage(image.scaled(96,72,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)))
            self.files.blockSignals(True)
            for i in range(self.files.count()):
                item = self.files.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == path: item.setIcon(icon)
            self.files.blockSignals(False)
        if error:
            self.log.appendPlainText(f'Không đọc được {Path(path).name}: {error}')
        if self.current_preview == (path, token):
            if error:
                self.preview_label.setText(f'Không đọc được preview: {Path(path).name}')
            else:
                self.preview.show_image(image)
                self.preview_label.setText(f'{Path(path).name} · xem sRGB ở độ phân giải gốc; ảnh nguồn không thay đổi')
                if self.result and path == str(self.result) and self.depth_path.exists():
                    self.reveal_image = image
                    self.replay_button.setEnabled(True)
                    if self.auto_reveal_pending:
                        self.auto_reveal_pending = False
                        self.replay_reveal()

    def source_preview(self, item, previous=None):
        self.reveal_timer.stop()
        if item: self.request_preview(item.data(Qt.ItemDataRole.UserRole))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])

    def uncheck_all(self):
        for i in range(self.files.count()):
            self.files.item(i).setCheckState(Qt.CheckState.Unchecked)

    def busy(self, active):
        for w in (self.start_button, self.add_button, self.folder_button, self.capture_button, self.clear_button, self.select_all_button, self.deselect_all_button,
                  self.remove_button, self.radius, self.smooth, self.align, self.auto, self.auto_stack, self.load_workers, self.resize_inputs, self.rendered_only, self.files, self.queued_button):
            w.setEnabled(not active)
        self.cancel_align_button.setEnabled(not active and (bool(self.alignment_jobs) or self.alignment_timer.isActive()))
        if not active and self.auto.isChecked():
            self.radius.setEnabled(False); self.smooth.setEnabled(False)
        self.cancel_button.setEnabled(active)

    def start(self):
        if self.proc is not None: return
        # Same order as the worker's discover() so contribution lines match the inputs.
        paths = sorted(self.selected_paths(), key=str.casefold)
        if len(paths) < 2:
            QMessageBox.warning(self, 'Chưa đủ ảnh để ghép',
                f'Đang đánh dấu {len(paths)} ảnh. Hãy đánh dấu ít nhất 2 ảnh trong danh sách.'); return
        try:
            settings = RenderSettings(align=self.align.isChecked(), radius=self.radius.value(),
                                      smoothing=self.smooth.value(), automatic=self.auto.isChecked(), desktop_inputs=True,
                                      load_workers=self.load_workers.value(), auto_resize_mismatched=self.resize_inputs.isChecked(),
                                      rendered_only=self.rendered_only.isChecked())
        except ValueError as exc:
            QMessageBox.warning(self, 'Kiểm tra đầu vào', str(exc)); return
        self.invalidate()
        if self.temp: self.temp.cleanup()
        self.temp = create_task_cache()
        self.pending = Path(self.temp.name) / 'result.tif'
        self.report_path = Path(self.temp.name) / 'report.json'
        self.map_path = Path(self.temp.name) / 'focus-map.png'
        self.live_path = Path(self.temp.name) / 'live.png'
        self.depth_path = Path(self.temp.name) / 'depth.tif'
        self.run_paths = list(paths)
        args = ['--worker', *paths, '-o', str(self.pending), *settings.worker_args(),
                '--report', str(self.report_path), '--focus-map', str(self.map_path), '--depth', str(self.depth_path), '--preview-output', str(self.live_path), '--events']
        if self.align.isChecked() and self.alignment_cache:
            args.extend(['--prealigned-cache', self.alignment_cache.name])
        self.cancelled = False; self.log.clear(); self.busy(True)
        self.current_preview = None; self.preview.set_processing(True)
        self.progress.setValue(0)
        self.status.setText(f'Đang bắt đầu ghép {len(paths)} ảnh…')
        self.log.appendPlainText(f'Bắt đầu ghép {len(paths)} ảnh:\n' + '\n'.join(Path(p).name for p in paths))
        if any(Path(p).suffix.lower() in RAW for p in paths):
            self.log.appendPlainText('RAW phát triển cục bộ sang sRGB; dùng WB ảnh đầu cho cả bộ. Không áp dụng chỉnh sửa Capture One.')
        self.started_at = time.monotonic(); self.elapsed.start()
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace'); self.log_buffer = ''
        self.proc = StackProcess(self)
        self.proc.readyReadStandardOutput.connect(self.read_log)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.proc.start_worker(args)

    def update_elapsed(self):
        self.timer_label.setText(f'Đã chạy {int(time.monotonic()-self.started_at)} giây · có thể Hủy')

    def consume_line(self, line):
        LOG.info("%s", line)
        if line.startswith('FOCUSSTACK_PREVIEW '):
            try:
                event = json.loads(line[len('FOCUSSTACK_PREVIEW '):])
                if Path(event['path']) == self.live_path:
                    image = QImage(event['path'])
                    if not image.isNull():
                        self.preview.show_image(image)
                        self.preview_label.setText(f"Preview tạm thời · {'căn chỉnh' if event.get('stage') == 'alignment' else 'ghép nháp'} {event['index']}/{event['count']} ảnh")
                return
            except (ValueError, KeyError, TypeError): pass
        if line.startswith('FOCUSSTACK_EVENT '):
            try:
                event = json.loads(line[len('FOCUSSTACK_EVENT '):])
                self.progress.setValue(min(int(event['percent']),99))
                self.status.setText(event['message'])
                self.log.appendPlainText(event['message'])
                return
            except (ValueError, KeyError, TypeError): pass
        if line: self.log.appendPlainText(line)

    def read_log(self):
        if not self.proc: return
        self.log_buffer += self.decoder.decode(bytes(self.proc.readAllStandardOutput()))
        while '\n' in self.log_buffer:
            line, self.log_buffer = self.log_buffer.split('\n',1)
            self.consume_line(line)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.log.appendPlainText(self.proc.errorString()); self.finished(1)

    def finished(self, code, status=None):
        self.read_log()
        if self.log_buffer: self.consume_line(self.log_buffer); self.log_buffer = ''
        if self.proc: self.proc.deleteLater()
        self.proc = None; self.busy(False); self.elapsed.stop(); self.preview.set_processing(False)
        self.timer_label.setText(f'Thời gian: {int(time.monotonic()-self.started_at)} giây')
        try:
            if code != 0 or self.cancelled:
                raise ValueError('Đã hủy.' if self.cancelled else 'Xử lý thất bại. Xem lỗi phía trên.')
            report = json.loads(self.report_path.read_text(encoding='utf-8'))
            if report['status'] != 'completed':
                raise ValueError('Trạng thái báo cáo không khớp.')
            if not self.pending.exists() or not report['output']['verified']:
                raise ValueError('Không có TIFF đã xác minh.')
            self.result = self.pending
            self.result_button.setEnabled(True); self.export_button.setEnabled(True)
            self.report = report
            self.progress.setValue(100); self.map_button.setEnabled(self.map_path.exists())
            self.status.setText(f'Ghép thành công {report["input_count"]} ảnh · TIFF 16-bit và ICC đã kiểm tra. Chưa lưu ra thư mục của bạn.')
            if report['sources_used'] < 2:
                self.status.setText('Đã tạo và kiểm tra TIFF, nhưng chỉ một ảnh đóng góp pixel. Cần kiểm tra bộ ảnh; chưa chứng minh được tăng vùng nét.')
            lines = [f'{report["sources_used"]}/{report["input_count"]} ảnh được chọn theo bản đồ nét; phần trăm vùng là xấp xỉ khi hòa trộn đa dải.',
                     f'Vùng chưa rõ chênh lệch nét: {report["uncertain_percent"]}%.',
                     f'Vùng biên ghép cần kiểm tra: {report.get("seam_risk_percent", 0)}% (ước lượng, không xác nhận halo).']
            for i, (p, pct) in enumerate(zip(self.run_paths, report['contribution_percent'])):
                lines.append(f'Ảnh {i+1} · {Path(p).name}: {pct}% vùng chọn')
            uncertain = [r for r in report['regions'] if r['uncertain_percent'] >= 50]
            lines.append('Vùng cần kiểm tra (lưới 8×8): ' + (', '.join(f'h{r["row"]} c{r["column"]}' for r in uncertain) or 'Không có vùng vượt ngưỡng.'))
            lines.extend(report['warnings'])
            lines.append('Phân tích độ nét cục bộ, không phải AI. Không bảo đảm chất lượng thị giác tuyệt đối.')
            self.summary.setPlainText('\n'.join(lines))
            self.auto_reveal_pending = True
            self.show_result()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.result = None; self.report = None
            self.result_button.setEnabled(False); self.export_button.setEnabled(False)
            self.status.setText(str(exc)); self.log.appendPlainText(str(exc))

    def cancel(self):
        if self.proc:
            self.cancelled = True; self.status.setText('Đang hủy…'); self.proc.kill()

    def show_result(self):
        if self.result: self.request_preview(str(self.result))

    def replay_reveal(self):
        if self.reveal_image is None or not self.report: return
        import cv2
        import numpy as np
        small = self.reveal_image.scaled(1000, 1000, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGBA8888)
        h, w = small.height(), small.width()
        self.reveal_pixels = np.frombuffer(small.bits(), np.uint8).reshape(h, w, 4).copy()
        depth = cv2.imread(str(self.depth_path), cv2.IMREAD_UNCHANGED)
        if depth is None:
            self.log.appendPlainText('Không đọc được bản đồ để phát lại.'); return
        depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_NEAREST)
        self.reveal_depth = np.rint(depth.astype(np.float32) * (len(self.run_paths)-1) / 65535).astype(np.int32)
        self.reveal_index = 0
        self.reveal_timer.start(); self.reveal_step()

    def reveal_step(self):
        import cv2
        import numpy as np
        if self.reveal_image is None or self.reveal_index >= len(self.run_paths):
            self.reveal_timer.stop()
            if self.reveal_image is not None:
                self.preview.show_image(self.reveal_image)
                self.preview_label.setText('Kết quả ghép · độ phân giải gốc')
            return
        h, w = self.reveal_depth.shape
        y, x = np.indices((h, w))
        grid = np.where(((x // 16 + y // 16) % 2)[..., None], 210, 235).astype(np.uint8)
        pixels = np.empty((h, w, 4), np.uint8)
        pixels[..., :3] = grid; pixels[..., 3] = 255
        mask = self.reveal_depth <= self.reveal_index
        pixels[mask] = self.reveal_pixels[mask]
        current = (self.reveal_depth == self.reveal_index).astype(np.uint8)
        contours, _ = cv2.findContours(current, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(pixels, contours, -1, (0, 190, 255, 255), 1)
        self.preview.show_image(QImage(pixels.data, w, h, w*4, QImage.Format.Format_RGBA8888).copy())
        self.preview_label.setText(f'Vùng đóng góp {self.reveal_index+1}/{len(self.run_paths)} · {Path(self.run_paths[self.reveal_index]).name} (minh họa)')
        self.reveal_index += 1

    def show_map(self):
        self.reveal_timer.stop()
        if self.report and self.map_path.exists():
            self.current_preview = None
            image = QImage(str(self.map_path))
            self.preview.show_image(image)
            self.preview_label.setText('Bản đồ vùng lấy pixel từ các ảnh nguồn · xem số ảnh và % trong báo cáo. Không phải khoảng cách vật lý.')
            self.legend.setText(' &nbsp; '.join(
                f'<span style="color:rgb({(i*67+45)%256},{(i*131+100)%256},{(i*193+180)%256})">■</span> Ảnh {i+1}'
                for i in range(self.report['input_count'])))

    def export(self):
        if not self.result or not self.report: return
        name, selected_filter = QFileDialog.getSaveFileName(self, 'Lưu ảnh và báo cáo', 'stack.tif',
            'TIFF 16-bit (*.tif *.tiff);;PNG 16-bit (*.png);;JPEG 8-bit (*.jpg *.jpeg)')
        if not name: return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix('.png' if selected_filter.startswith('PNG') else '.jpg' if selected_filter.startswith('JPEG') else '.tif')
        report_path = path.with_suffix(path.suffix+'.focusstack.json')
        try:
            if path.exists() or report_path.exists(): raise ValueError('File đã tồn tại; hãy chọn tên mới.')
            result = export_image(self.result, path)
            report = dict(self.report); report['output'] = result
            with report_path.open('x', encoding='utf-8') as f: json.dump(report, f, ensure_ascii=False, indent=2)
            self.status.setText(f'Đã lưu và xác minh: {path.name} + báo cáo.')
            self.log.appendPlainText(f'Đã lưu: {path}\nBáo cáo: {report_path}')
        except Exception as exc: QMessageBox.warning(self, 'Không lưu được đầy đủ ảnh/báo cáo', str(exc))

    def closeEvent(self, event):
        self.reveal_timer.stop()
        if self.proc:
            self.cancel(); event.ignore()
            self.log.appendPlainText('Đang hủy. Đóng lại sau khi tiến trình dừng.'); return
        if self.result:
            answer = QMessageBox.question(self, 'Đóng FocusStack', 'Đảm bảo đã lưu TIFF và báo cáo. Đóng sẽ xóa kết quả tạm. Tiếp tục?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: event.ignore(); return
        self.cancel_import_alignment()
        self.alignment_pool.clear(); self.alignment_pool.waitForDone()
        for job in self.alignment_jobs:
            if job.cache: job.cache.cleanup()
        self.alignment_jobs.clear()
        self.pool.clear(); self.pool.waitForDone()
        if self.temp: self.temp.cleanup()
        if self.settings is not None: save_window(self, self.settings)
        event.accept()


