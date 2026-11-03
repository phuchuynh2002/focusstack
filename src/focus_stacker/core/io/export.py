"""Export verified TIFF results with explicit bit depth and ICC preservation."""
from pathlib import Path
import io
import struct
import zlib
import cv2
import numpy as np
from PIL import Image
from .images import load, profile
from focus_stacker.core.workflow import digest


def export_image(source: Path, destination: Path):
    ext = destination.suffix.lower()
    if ext not in {'.tif', '.tiff', '.png', '.jpg', '.jpeg'}:
        raise ValueError('Chọn TIFF, PNG hoặc JPEG')
    if ext in {'.tif', '.tiff'}:
        data = source.read_bytes()
    else:
        pixels = load(source)
        icc = profile(source)
        if ext in {'.jpg', '.jpeg'}:
            array = np.rint(np.clip(pixels, 0, 1)*255).astype(np.uint8)
            buffer = io.BytesIO()
            Image.fromarray(array).save(buffer, format='JPEG', quality=100, subsampling=0, icc_profile=icc)
            data = buffer.getvalue()
        else:
            array = np.rint(np.clip(pixels, 0, 1)*65535).astype(np.uint16)
            ok, encoded = cv2.imencode('.png', cv2.cvtColor(array, cv2.COLOR_RGB2BGR))
            if not ok: raise ValueError('Không thể mã hóa PNG')
            data = encoded.tobytes()
            if icc:
                payload = b'ICC\x00\x00' + zlib.compress(icc)
                chunk_type = b'iCCP'
                chunk = struct.pack('>I', len(payload)) + chunk_type + payload + struct.pack('>I', zlib.crc32(chunk_type + payload))
                data = data[:33] + chunk + data[33:]
    with destination.open('xb') as stream:
        stream.write(data)
    actual = load(destination)
    if actual.shape != load(source).shape or profile(destination) != profile(source):
        raise ValueError('Không xác minh được kích thước hoặc ICC của file xuất')
    if ext not in {'.jpg', '.jpeg'} and not np.array_equal(actual, load(source)):
        raise ValueError('Pixel file xuất không khớp TIFF kết quả')
    return {'path': str(destination.resolve()), 'sha256': digest(destination), 'verified': True,
            'verification': 'dimensions and ICC' if ext in {'.jpg', '.jpeg'} else 'pixels, dimensions and ICC',
            'bit_depth': 8 if ext in {'.jpg', '.jpeg'} else 16,
            'lossy': ext in {'.jpg', '.jpeg'}}
