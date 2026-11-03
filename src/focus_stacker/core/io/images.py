from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import tifffile

from focus_stacker.core.io.formats import RAW, FORMATS

LOG = logging.getLogger(__name__)


def discover(inputs: list[str], sort: str = "name") -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        path = Path(item).expanduser()
        if path.is_dir():
            paths.extend(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in FORMATS)
        elif path.is_file() and path.suffix.lower() in FORMATS:
            paths.append(path)
        else:
            raise ValueError(f"Input not found or unsupported: {path}")
    paths = list(dict.fromkeys(p.resolve() for p in paths))
    if sort == "time":
        def key(path: Path) -> tuple[str, str]:
            try:
                with Image.open(path) as image:
                    exif = image.getexif()
                    value = exif.get_ifd(34665).get(36867) or exif.get(36867) or exif.get(306)
                    if value:
                        return str(value), path.name.casefold()
            except Exception:
                pass
            raise ValueError(f"Missing readable EXIF capture time: {path}; use --sort name")
        paths.sort(key=key)
    else:
        paths.sort(key=lambda p: str(p).casefold())
    if len(paths) < 2:
        raise ValueError("At least two supported input images are required")
    return paths


def read_pixels(path: Path, raw_wb=None) -> tuple[np.ndarray, list[str]]:
    """Decode RGB uint8/uint16. Keep TIFF orientation and color profiles intact."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Input not found: {path}")
    if path.suffix.lower() not in FORMATS:
        raise ValueError(f"Unsupported image format: {path}")
    changes = []
    if path.suffix.lower() in RAW:
        try:
            import rawpy
            with rawpy.imread(str(path)) as raw:
                image = raw.postprocess(output_bps=16, use_camera_wb=raw_wb is None,
                                        user_wb=raw_wb, no_auto_bright=True,
                                        output_color=rawpy.ColorSpace.sRGB)
        except Exception as exc:
            raise ValueError(
                f"Cannot decode RAW {path}: {exc}. The file may be damaged or its camera/"
                "compression may not be supported by the installed LibRaw. "
                "Try exporting RGB 16-bit TIFF from Capture One."
            ) from exc
    else:
        icc = None
        try:
            with Image.open(path) as metadata:
                orientation = metadata.getexif().get(274, 1)
                icc = metadata.info.get('icc_profile')
        except Exception:
            orientation = 1
        if icc and icc[16:20] != b'RGB ':
            raise ValueError(f"{path.name}: convert the embedded non-RGB ICC profile to RGB before stacking")
        is_tiff = path.suffix.lower() in {".tif", ".tiff"}
        if is_tiff:
            with tifffile.TiffFile(path) as tiff:
                page = tiff.pages[0]
                if len(tiff.pages) != 1 or page.photometric not in (0, 1, 2) or page.planarconfig != 1:
                    raise ValueError(f"Expected single-page contiguous RGB or grayscale TIFF: {path}")
                if any(int(extra) == 1 for extra in page.extrasamples):
                    raise ValueError(f"{path.name}: TIFF premultiplied alpha is not supported; export RGB first")
                orientation = page.tags[274].value if 274 in page.tags else 1
                image = page.asarray()
                if page.photometric == 0 and image.dtype in (np.uint8, np.uint16):
                    image = np.iinfo(image.dtype).max - image
        else:
            data = np.fromfile(path, dtype=np.uint8)
            try:
                image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
            except cv2.error as exc:
                raise ValueError(f'Cannot decode image: {path}') from exc
        if image is None:
            raise ValueError(f"Cannot decode image: {path}")
        if image.dtype not in (np.uint8, np.uint16):
            raise ValueError(f"Expected 8/16-bit integer image: {path}; got {image.dtype}")
        if image.ndim == 2:
            image = np.repeat(image[:, :, None], 3, axis=2)
            changes.append('grayscale expanded to RGB')
        elif image.ndim == 3 and image.shape[2] in (1, 2):
            if image.shape[2] == 2: changes.append('alpha discarded')
            image = np.repeat(image[:, :, :1], 3, axis=2)
            changes.append('grayscale expanded to RGB')
        elif image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]
            changes.append('alpha discarded')
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected grayscale, RGB or RGBA image: {path}")
        if not is_tiff:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # OpenCV IMREAD_UNCHANGED does not apply EXIF orientation.
        transforms = {2: lambda a: np.fliplr(a), 3: lambda a: np.rot90(a, 2),
                      4: lambda a: np.flipud(a), 5: lambda a: np.transpose(a, (1, 0, 2)),
                      6: lambda a: np.rot90(a, 3), 7: lambda a: np.flip(np.transpose(a, (1, 0, 2)), (0, 1)),
                      8: lambda a: np.rot90(a, 1)}
        if orientation in transforms:
            image = transforms[orientation](image)
    return np.ascontiguousarray(image), changes


def load(path: Path, raw_wb=None) -> np.ndarray:
    """Return RGB float32 in [0,1], without silently converting color profiles."""
    image, _ = read_pixels(path, raw_wb=raw_wb)
    return image.astype(np.float32) / np.iinfo(image.dtype).max


@lru_cache(maxsize=1)
def raw_profile() -> bytes:
    # ICC creation timestamps must not make identical RAW output spaces differ.
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def profile(path: Path) -> bytes | None:
    if path.suffix.lower() in RAW:
        return raw_profile()
    with Image.open(path) as image:
        return image.info.get("icc_profile")


def save(path: Path, image: np.ndarray, quality: int = 95, icc: bytes | None = None,
         description: str | None = None) -> None:
    suffix = path.suffix.lower()
    if suffix not in {".png", ".tif", ".tiff", ".jpg", ".jpeg"}:
        raise ValueError("Output extension must be TIFF, PNG or JPG")
    if not 1 <= quality <= 100:
        raise ValueError("JPEG quality must be between 1 and 100")
    bits = 8 if suffix in {".jpg", ".jpeg"} else 16
    maxval = (1 << bits) - 1
    array = np.rint(np.clip(image, 0, 1) * maxval).astype(np.uint8 if bits == 8 else np.uint16)
    if suffix in {".tif", ".tiff"}:
        tifffile.imwrite(path, array, photometric="rgb" if array.ndim == 3 else "minisblack",
                         metadata=None, description=description,
                         extratags=[(34675, "B", len(icc), icc, False)] if icc else [])
        return
    if icc:
        raise ValueError("Use TIFF output to preserve the embedded ICC profile")
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(suffix, array, [cv2.IMWRITE_JPEG_QUALITY, quality] if bits == 8 else [])
    if not ok:
        raise ValueError(f"Cannot encode output: {path}")
    encoded.tofile(path)
