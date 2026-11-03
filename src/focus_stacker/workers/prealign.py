"""Cancellable alignment on import, stored in an isolated temporary cache."""
import json
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable
from focus_stacker.core.align.ecc import align
from focus_stacker.core.io.formats import RAW
from focus_stacker.core.io.loader import load_stack


class AlignmentSignals(QObject):
    progress = Signal(str)
    done = Signal(object, str)


class PrealignJob(QRunnable):
    def __init__(self, paths, workers, resize, rendered_only):
        super().__init__()
        self.paths = [Path(p) for p in paths]
        self.workers, self.resize, self.rendered_only = workers, resize, rendered_only
        self.signals = AlignmentSignals()
        self.cancelled = False
        self.cache = None
        self.setAutoDelete(False)

    def cancel(self): self.cancelled = True

    def run(self):
        try:
            from focus_stacker.core.workflow import validate_rendered
            if self.rendered_only: validate_rendered(self.paths)
            raw = [p.suffix.lower() in RAW for p in self.paths]
            if any(raw) and not all(raw): raise ValueError('Không trộn RAW và ảnh đã render.')
            wb = None
            if all(raw):
                import rawpy
                with rawpy.imread(str(self.paths[0])) as source:
                    wb = list(source.camera_whitebalance)
                    if len(wb) != 4 or not all(np.isfinite(x) and x > 0 for x in wb[:3]):
                        raise ValueError('RAW đầu không có cân bằng trắng hợp lệ')
                    if not np.isfinite(wb[3]) or wb[3] <= 0: wb[3] = wb[1]
            self.signals.progress.emit(f'Đang nạp {len(self.paths)} ảnh để căn chỉnh…')
            loaded = load_stack(self.paths, max_workers=self.workers, auto_resize_mismatched=self.resize,
                                raw_wb=wb, verify_files=True)
            if self.cancelled: self.signals.done.emit(self, 'cancelled'); return
            self.cache = tempfile.TemporaryDirectory(prefix='focusstack-alignment-')
            folder = Path(self.cache.name)
            reference = loaded.items[0].image
            for index, item in enumerate(loaded.items):
                if self.cancelled: self.signals.done.emit(self, 'cancelled'); return
                self.signals.progress.emit(f'Căn chỉnh khi nhập {index+1}/{len(self.paths)}: {item.path.name}')
                image = item.image
                if index: image, mask, score = align(reference, image)
                else: mask, score = np.ones(image.shape[:2], dtype=bool), 1.0
                np.savez(folder / f'{index}.npz', image=image, mask=mask, score=score)
            manifest = {'sources': [str(p.resolve()) for p in self.paths],
                        'sha256': [x.sha256 for x in loaded.items], 'resize': self.resize,
                        'rendered_only': self.rendered_only}
            (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.signals.done.emit(self, '')
        except Exception as exc:
            self.signals.done.emit(self, str(exc))
