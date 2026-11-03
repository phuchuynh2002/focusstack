"""Persist window geometry; per-run render settings remain explicit in the UI."""
from PySide6.QtCore import QByteArray


def restore_window(window, settings):
    geometry = settings.value('window/geometry')
    if isinstance(geometry, QByteArray):
        window.restoreGeometry(geometry)


def save_window(window, settings):
    settings.setValue('window/geometry', window.saveGeometry())
    settings.sync()
