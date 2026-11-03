import cv2
import numpy as np


def measure(image: np.ndarray, radius: float) -> np.ndarray:
    """Combine first/second derivatives at two scales in linear pixel coordinates."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    def energy(im):
        lap = cv2.Laplacian(im, cv2.CV_32F, ksize=3)
        gx = cv2.Sobel(im, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(im, cv2.CV_32F, 0, 1, ksize=3)
        return .65 * lap * lap + .35 * (gx * gx + gy * gy)
    fine = energy(gray)
    if min(gray.shape) >= 4:
        coarse = energy(cv2.pyrDown(gray))
        fine += .25 * cv2.resize(coarse, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(fine, (0, 0), radius) if radius > 0 else fine
