from __future__ import annotations

import cv2
import numpy as np


def align(reference: np.ndarray, moving: np.ndarray, levels: int = 3) -> tuple[np.ndarray, np.ndarray, float]:
    """Register to reference using coarse-to-fine affine ECC and return valid support mask."""
    ref = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
    mov = cv2.cvtColor(moving, cv2.COLOR_RGB2GRAY)
    pyramid_ref, pyramid_mov = [ref], [mov]
    for _ in range(levels - 1):
        if min(pyramid_ref[-1].shape) < 128:
            break
        pyramid_ref.append(cv2.pyrDown(pyramid_ref[-1]))
        pyramid_mov.append(cv2.pyrDown(pyramid_mov[-1]))
    # Very coarse levels can lose all usable texture. Retry from a finer level.
    last_error = None
    for start in range(len(pyramid_ref) - 1, -1, -1):
        warp = np.eye(2, 3, dtype=np.float32)
        # Estimate a coarse affine starting point when reliable features exist.
        a = np.uint8(np.clip(pyramid_ref[start], 0, 1) * 255)
        b = np.uint8(np.clip(pyramid_mov[start], 0, 1) * 255)
        try:
            orb = cv2.ORB_create(1500)
            ka, da = orb.detectAndCompute(a, None)
            kb, db = orb.detectAndCompute(b, None)
            if da is not None and db is not None:
                matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(db, da)
                matches = sorted(matches, key=lambda m: m.distance)[:200]
                if len(matches) >= 12:
                    src = np.float32([kb[m.queryIdx].pt for m in matches])
                    dst = np.float32([ka[m.trainIdx].pt for m in matches])
                    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
                    if matrix is not None and inliers is not None and int(inliers.sum()) >= 10:
                        warp = cv2.invertAffineTransform(matrix).astype(np.float32)
        except (cv2.error, ValueError):
            pass
        try:
            for level in range(start, -1, -1):
                if level < start:
                    warp[:, 2] *= 2
                score, warp = cv2.findTransformECC(
                    pyramid_ref[level], pyramid_mov[level], warp, cv2.MOTION_AFFINE,
                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6), None, 5)
            break
        except cv2.error as exc:
            last_error = exc
    else:
        raise ValueError("ECC alignment failed; remove problematic frames or try --no-align") from last_error
    if not np.isfinite(warp).all() or not np.isfinite(score):
        raise ValueError("ECC alignment produced a non-finite transform")
    h, w = ref.shape
    flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
    result = cv2.warpAffine(moving, warp, (w, h), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
    valid = cv2.warpAffine(np.ones((h, w), np.float32), warp, (w, h), flags=flags,
                           borderMode=cv2.BORDER_CONSTANT) >= 0.999
    valid = cv2.erode(valid.astype(np.uint8), np.ones((7, 7), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    return result, valid, float(score)
