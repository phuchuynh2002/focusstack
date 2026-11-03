"""Own only this task's temporary directory; never sweep other jobs' files."""
from tempfile import TemporaryDirectory


def create_task_cache():
    return TemporaryDirectory(prefix='focusstack-')
