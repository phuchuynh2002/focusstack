from __future__ import annotations

import numpy as np
import cv2
from scipy.ndimage import median_filter

from focus_stacker.core.focus.measure import measure


def fuse(images: list[np.ndarray], masks: list[np.ndarray], radius: float = 3,
         smoothing: int = 5, *, progress=None, diagnostics=None, scan_only=False, preview=None) -> tuple[np.ndarray | None, np.ndarray]:
    if not np.isfinite(radius) or radius < 0 or smoothing < 1 or smoothing % 2 == 0:
        raise ValueError("radius must be nonnegative and smoothing must be a positive odd integer")
    h, w = images[0].shape[:2]
    best = np.full((h, w), -np.inf, dtype=np.float32)
    second = np.full((h, w), -np.inf, dtype=np.float32) if diagnostics is not None else None
    depth = np.zeros((h, w), dtype=np.int32)
    preview_image = None
    for i, (image, mask) in enumerate(zip(images, masks)):
        if progress: progress(i, len(images))
        score = measure(image, radius)
        support = int(np.ceil(4 * radius)) + 5
        safe = cv2.erode(mask.astype(np.uint8), np.ones((2*support+1, 2*support+1), np.uint8),
                         borderType=cv2.BORDER_REPLICATE).astype(bool)
        score[~safe] = -np.inf
        better = score > best
        if second is not None:
            second = np.where(better, best, np.maximum(second, score))
        depth[better] = i
        best[better] = score[better]
        if preview is not None:
            scale = min(1.0, 1000 / max(h, w))
            size = (max(1, round(w * scale)), max(1, round(h * scale)))
            thumb = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
            selected = cv2.resize(better.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)
            if preview_image is None: preview_image = thumb.copy()
            else: preview_image[selected] = thumb[selected]
            preview(preview_image, i, len(images), 'fusion')
    if not np.isfinite(best).all():
        raise ValueError("No source image covers some pixels")
    if smoothing > 1:
        smoothed = median_filter(depth, size=smoothing, mode="nearest")
        # Do not choose pixels outside the valid footprint of a registered frame.
        for i, mask in enumerate(masks):
            invalid = (smoothed == i) & ~mask
            smoothed[invalid] = depth[invalid]
        depth = smoothed
    if diagnostics is not None:
        from focus_stacker.core.workflow import focus_summary
        diagnostics.update(focus_summary(depth, best, second, images))
    if scan_only:
        return None, depth
    from focus_stacker.core.fusion.pyramid import fuse_pyramid
    result = fuse_pyramid(images, masks, depth)
    return result, depth
