"""Process-isolated stacking: cancellation cannot leave a thread mutating UI state."""
from pathlib import Path
import sys
from PySide6.QtCore import QProcess, QProcessEnvironment


def worker_command(args):
    if getattr(sys, 'frozen', False):
        return sys.executable, list(args)
    return sys.executable, ['-m', 'focus_stacker.main', *args]


class StackProcess(QProcess):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1')
        if not getattr(sys, 'frozen', False):
            env.insert('PYTHONPATH', str(Path(__file__).resolve().parents[2]))
        self.setProcessEnvironment(env)

    def start_worker(self, args):
        executable, arguments = worker_command(args)
        self.start(executable, arguments)
