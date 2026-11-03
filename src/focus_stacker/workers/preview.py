"""Decode and color-convert previews outside the GUI thread."""
from PySide6.QtCore import QObject, Signal, QRunnable
from PySide6.QtGui import QImage
from focus_stacker.core.workflow import preview_rgb

class PreviewSignals(QObject):
    done = Signal(str, int, QImage, str)


class PreviewJob(QRunnable):
    def __init__(self, path, token, full_resolution=False):
        super().__init__()
        self.path, self.token = path, token
        self.full_resolution = full_resolution
        self.signals = PreviewSignals()

    def run(self):
        try:
            image = preview_rgb(self.path, size=None if self.full_resolution else 1600)
            data = image.tobytes()
            qimage = QImage(data, image.width, image.height, image.width*3, QImage.Format.Format_RGB888).copy()
            self.signals.done.emit(self.path, self.token, qimage, '')
        except Exception as exc:
            self.signals.done.emit(self.path, self.token, QImage(), str(exc))


