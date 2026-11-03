"""Shared logging configuration for the desktop and CLI."""
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(directory=None):
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if directory is None:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        return
    if any(getattr(handler, '_focusstack', False) for handler in root.handlers):
        return
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory/'focusstack.log', maxBytes=2*1024*1024,
                                      backupCount=3, encoding='utf-8')
    except OSError:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning('Cannot open application log directory: %s', directory)
        return
    handler._focusstack = True
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root.addHandler(handler)
