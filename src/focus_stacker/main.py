"""Desktop entry point, settings, resources and macOS file-open events."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import QEvent, QTimer, QSettings, QStandardPaths
from PySide6.QtWidgets import QApplication
from focus_stacker.ui.main_window import MainWindow
from focus_stacker.utils.assets import asset_path
from focus_stacker.utils.logging import setup_logging

class Application(QApplication):
    def __init__(self, args):
        self.window = None
        self.pending = []
        super().__init__(args)
        self.open_timer = QTimer(self)
        self.open_timer.setSingleShot(True)
        self.open_timer.timeout.connect(self.deliver_files)

    def deliver_files(self):
        if self.window and self.pending:
            paths, self.pending = self.pending, []
            self.window.add_paths(paths)
            self.window.show(); self.window.raise_()

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            self.pending.append(event.file())
            if hasattr(self, 'open_timer'): self.open_timer.start(300)
            return True
        return super().event(event)


def main():
    if '--worker' in sys.argv:
        sys.argv.remove('--worker')
        from focus_stacker.cli import main as cli_main
        return cli_main()
    app = Application(sys.argv)
    app.setOrganizationName('FocusStack'); app.setApplicationName('FocusStack')
    setup_logging(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'logs')
    theme = asset_path('theme.qss')
    if theme is not None: app.setStyleSheet(theme.read_text(encoding='utf-8'))
    window = MainWindow(settings=QSettings()); app.window = window
    app.pending.extend(arg for arg in sys.argv[1:] if not arg.startswith('-'))
    window.show(); app.deliver_files()
    if os.environ.get('FOCUSSTACK_SMOKE_TEST') == '1': QTimer.singleShot(1000, app.quit)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
