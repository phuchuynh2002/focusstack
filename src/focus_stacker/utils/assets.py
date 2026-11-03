"""Resolve assets in a source checkout, installed wheel or PyInstaller bundle."""
from pathlib import Path
import sys


def asset_path(name):
    if Path(name).name != name:
        raise ValueError('Asset name must be a filename')
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys._MEIPASS)/'assets'/name)
    candidates.extend((Path(__file__).resolve().parents[3]/'assets'/name,
                       Path(sys.prefix)/'share/focusstack/assets'/name))
    return next((path for path in candidates if path.is_file()), None)
