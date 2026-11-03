"""Multi-band fusion from an already validated depth map and alignment masks."""
import cv2
import numpy as np


def fuse_pyramid(images, masks, depth, levels=5, progress=None):
    h, w = depth.shape
    levels = max(1, min(levels, int(np.floor(np.log2(max(1, min(h, w)))))))
    bands = weights = None
    reference = images[0]
    for i, (image, valid) in enumerate(zip(images, masks)):
        if progress: progress(i, len(images))
        # Reference covers the canvas; never blend black interpolation padding.
        prepared = np.where(valid[..., None], image, reference)
        gaussian = [prepared]
        weight = [((depth == i) & valid).astype(np.float32)]
        for _ in range(levels - 1):
            gaussian.append(cv2.pyrDown(gaussian[-1]))
            weight.append(cv2.pyrDown(weight[-1]))
        laplacian = []
        for level in range(levels - 1):
            shape = (gaussian[level].shape[1], gaussian[level].shape[0])
            laplacian.append(gaussian[level] - cv2.pyrUp(gaussian[level + 1], dstsize=shape))
        laplacian.append(gaussian[-1])
        if bands is None:
            bands = [np.zeros_like(x) for x in laplacian]
            weights = [np.zeros_like(x) for x in weight]
        for level in range(levels):
            bands[level] += laplacian[level] * weight[level][..., None]
            weights[level] += weight[level]
    for i in range(levels):
        bands[i] /= np.maximum(weights[i][..., None], 1e-8)
    result = bands[-1]
    for i in range(levels - 2, -1, -1):
        result = cv2.pyrUp(result, dstsize=(bands[i].shape[1], bands[i].shape[0])) + bands[i]
    return np.clip(result, 0, 1)
