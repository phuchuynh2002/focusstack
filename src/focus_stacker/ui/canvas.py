"""Image canvas with zoom/pan and a processing indicator."""
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QLinearGradient
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene


class Preview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def set_processing(self, active):
        if active: self._timer.start()
        else: self._timer.stop()
        self.viewport().update()

    def _tick(self):
        self._phase = (self._phase + 1) % 120
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._timer.isActive(): return
        painter = QPainter(self.viewport())
        r = self.viewport().rect()
        y = r.height() * (self._phase / 119)
        gradient = QLinearGradient(0, y - 20, 0, y + 20)
        gradient.setColorAt(0, QColor(50, 190, 255, 0))
        gradient.setColorAt(.5, QColor(50, 190, 255, 130))
        gradient.setColorAt(1, QColor(50, 190, 255, 0))
        painter.fillRect(QRectF(0, y - 20, r.width(), 40), gradient)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#38bdf8'), 3))
        painter.drawArc(r.width() - 36, 12, 22, 22, -self._phase * 48, 240 * 16)
        painter.end()

    def show_image(self, image):
        self.scene().clear()
        self.scene().addPixmap(QPixmap.fromImage(image))
        self.scene().setSceneRect(self.scene().itemsBoundingRect())
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def fit_image(self):
        if not self.sceneRect().isEmpty():
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def exact_zoom(self, factor):
        self.resetTransform()
        self.scale(factor, factor)

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        if .01 < self.transform().m11()*factor < 30:
            self.scale(factor, factor)
