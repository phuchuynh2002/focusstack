"""Compatibility entry point. Use focus_stacker.main for new integrations."""
from focus_stacker.main import Application, main
from focus_stacker.ui.main_window import MainWindow as Window
from focus_stacker.ui.canvas import Preview
from focus_stacker.workers.preview import PreviewJob, PreviewSignals

if __name__ == '__main__':
    raise SystemExit(main())
