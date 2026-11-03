"""Parallel, ordered input validation adapted from the supplied Image Loader notebook.

Unlike the notebook's BGR interface, this application consistently uses RGB.
Callbacks run on the caller thread; the desktop invokes this from its worker process.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

import cv2
import numpy as np

from .formats import RAW
from .images import read_pixels, profile


@dataclass
class LoadedImage:
    path: Path
    image: np.ndarray
    original_dtype: np.dtype
    shape: tuple[int, int, int]
    icc: bytes | None = None
    sha256: str | None = None
    changes: list[str] = field(default_factory=list)


@dataclass
class LoadedStack:
    items: list[LoadedImage]
    reference_dtype: np.dtype
    target_mode: str

    @property
    def images(self):
        return [item.image for item in self.items]


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def load_single_image(file_path, allow_raw=True, *, raw_wb=None, verify_files=False):
    path = Path(file_path)
    if not allow_raw and path.suffix.lower() in RAW:
        raise ValueError(f'{path.name}: direct RAW input is disabled; export a rendered image first')
    before = _digest(path) if verify_files else None
    pixels, changes = read_pixels(path, raw_wb=raw_wb)
    icc = profile(path)
    if verify_files and _digest(path) != before:
        raise ValueError(f'{path.name}: input changed while reading; wait for export to finish')
    return LoadedImage(path, pixels, pixels.dtype, pixels.shape, icc, before, changes)


def load_stack(file_paths, target_mode='float32', auto_resize_mismatched=False,
               max_workers=2, progress_callback=None, *, allow_raw=True, raw_wb=None, verify_files=False):
    paths = [Path(p) for p in file_paths]
    if len(paths) < 2: raise ValueError('At least two images are required')
    if target_mode not in {'float32', 'preserve', 'uint8'}:
        raise ValueError(f'Invalid target_mode: {target_mode}')
    if not isinstance(max_workers, int) or not 1 <= max_workers <= 8:
        raise ValueError('load_workers must be between 1 and 8')
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError('Duplicate source images are not allowed')
    workers = min(max_workers, len(paths))
    items = [None] * len(paths)

    def task(index):
        item = load_single_image(paths[index], allow_raw, raw_wb=raw_wb, verify_files=verify_files)
        # Convert in each worker and release the integer decode buffer immediately.
        if target_mode == 'float32':
            item.image = item.image.astype(np.float32)/np.iinfo(item.original_dtype).max
        elif target_mode == 'uint8' and item.original_dtype == np.uint16:
            item.image = np.rint(item.image.astype(np.float32)/257).astype(np.uint8)
            item.changes.append('16-bit reduced to 8-bit')
        return item

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='focusstack-load') as executor:
        pending = {executor.submit(task, i): i for i in range(len(paths))}
        try:
            for completed, future in enumerate(as_completed(pending), 1):
                i = pending.pop(future)
                items[i] = future.result()
                if progress_callback:
                    progress_callback(completed, len(paths), f'Đã nạp {completed}/{len(paths)}: {paths[i].name}')
        except BaseException:
            for future in pending: future.cancel()
            raise
    ref_shape = items[0].shape
    reference_dtype = np.dtype(np.uint16 if any(it.original_dtype == np.uint16 for it in items) else np.uint8)
    for item in items:
        if item.icc != items[0].icc:
            raise ValueError(f'{item.path.name}: Input ICC profiles differ. Export all inputs with the same profile first.')
        if item.shape[:2] != ref_shape[:2]:
            if not auto_resize_mismatched:
                raise ValueError(f'Image dimensions do not match: {item.path.name} {item.shape[:2]} vs {paths[0].name} {ref_shape[:2]}')
            interpolation = cv2.INTER_AREA if item.shape[0]>=ref_shape[0] and item.shape[1]>=ref_shape[1] else cv2.INTER_LINEAR
            item.image = cv2.resize(item.image, (ref_shape[1],ref_shape[0]), interpolation=interpolation)
            item.changes.append(f'resized from {item.shape[1]}x{item.shape[0]} to {ref_shape[1]}x{ref_shape[0]}')
        if target_mode == 'preserve' and reference_dtype == np.uint16 and item.original_dtype == np.uint8:
            item.image = item.image.astype(np.uint16)*257
        item.image = np.ascontiguousarray(item.image)
    return LoadedStack(items, reference_dtype, target_mode)


def validate_and_load_stack(file_paths, target_mode='float32', auto_resize_mismatched=False,
                            max_workers=2, progress_callback=None, **kwargs):
    """Notebook-compatible return tuple, but arrays use the app's RGB convention."""
    stack = load_stack(file_paths, target_mode, auto_resize_mismatched, max_workers, progress_callback, **kwargs)
    return stack.images, stack.reference_dtype


def convert_result_for_saving(image, target_dtype=np.uint8):
    dtype = np.dtype(target_dtype)
    if dtype not in (np.dtype('uint8'), np.dtype('uint16')):
        raise ValueError('Output dtype must be uint8 or uint16')
    if image.dtype in (np.uint8, np.uint16):
        if image.dtype == dtype: return image.copy()
        normalized = image.astype(np.float64)/np.iinfo(image.dtype).max
    elif image.dtype in (np.float32, np.float64):
        if not np.isfinite(image).all(): raise ValueError('Output contains non-finite pixels')
        normalized = image
    else:
        raise ValueError('Unsupported input dtype for output conversion')
    return np.rint(np.clip(normalized,0,1)*np.iinfo(dtype).max).astype(dtype)
