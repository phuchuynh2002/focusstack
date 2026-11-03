"""Local focus diagnostics and verifiable records, not AI judgements."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image, ImageCms

from focus_stacker.core.io.images import load, profile

MARKER = 'focusstack-result-v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stack_record(path):
    """Only recognize our explicit provenance; absence does not mean unstacked."""
    if Path(path).suffix.lower() not in {'.tif', '.tiff'}:
        return None
    try:
        with tifffile.TiffFile(path) as tif:
            record = json.loads(tif.pages[0].description or '{}')
        if isinstance(record, dict) and record.get('format') == MARKER:
            return record
    except (ValueError, OSError, TypeError):
        pass
    return None


def validate_rendered(paths):
    for path in paths:
        if path.suffix.lower() not in {'.tif', '.tiff'}:
            raise ValueError(f'{path.name}: cần TIFF 16-bit đã xuất từ Capture One, không dùng RAW gốc.')
        with tifffile.TiffFile(path) as tif:
            p = tif.pages[0]
            if len(tif.pages) != 1 or p.dtype != np.uint16 or p.photometric != 2 or p.samplesperpixel != 3 or p.planarconfig != 1:
                raise ValueError(f'{path.name}: cần TIFF RGB 16-bit, một trang, không alpha.')
        if not profile(path):
            raise ValueError(f'{path.name}: thiếu ICC. Xuất lại TIFF và nhúng cùng ICC trong Capture One.')


def preview_rgb(path, size=1600):
    """Decode with the same TIFF loader as stacking, independently of Qt codecs."""
    pixels = load(Path(path))
    image = Image.fromarray(np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8))
    if size is not None:
        image.thumbnail((size, size))
    icc = profile(Path(path))
    if icc:
        import io
        image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                         ImageCms.createProfile('sRGB'), outputMode='RGB')
    return image


def focus_summary(depth, best, second, paths):
    h, w = depth.shape
    # Relative confidence cannot distinguish flat surfaces from defocus.
    ambiguous = (best <= 1e-12) | ((best - second) <= .1 * np.maximum(best, 1e-12))
    # A depth transition combined with low confidence marks an area to inspect,
    # not proof of a halo.
    import cv2
    boundary = np.zeros((h, w), dtype=np.uint8)
    boundary[:, 1:] |= (depth[:, 1:] != depth[:, :-1])
    boundary[1:, :] |= (depth[1:, :] != depth[:-1, :])
    risk = cv2.dilate(boundary, np.ones((7, 7), np.uint8)).astype(bool) & ambiguous
    regions = []
    for row, ys in enumerate(np.array_split(np.arange(h), min(8, h))):
        for col, xs in enumerate(np.array_split(np.arange(w), min(8, w))):
            y0, y1, x0, x1 = int(ys[0]), int(ys[-1])+1, int(xs[0]), int(xs[-1])+1
            tile = depth[y0:y1, x0:x1]
            counts = np.bincount(tile.ravel(), minlength=len(paths))
            regions.append({'row': row+1, 'column': col+1, 'bounds': [x0,y0,x1,y1],
                            'source_index': int(counts.argmax()),
                            'uncertain_percent': round(float(ambiguous[y0:y1,x0:x1].mean()*100), 2),
                            'seam_risk_percent': round(float(risk[y0:y1,x0:x1].mean()*100), 2)})
    counts = np.bincount(depth.ravel(), minlength=len(paths))
    used = int(np.count_nonzero(counts))
    warnings = []
    if used < 2:
        warnings.append('Chỉ một ảnh đóng góp pixel. Chưa có bằng chứng ghép nhiều vùng nét; kiểm tra bộ ảnh và tham số.')
    warnings.append('Vùng ít chênh lệch nét có thể là nền trơn hoặc mờ. Kiểm tra ảnh ở 100%; số đo không bảo đảm mọi vùng đã nét.')
    return {'sources_used': used, 'contribution_definition': 'winner-map area; multiband blending also mixes neighbouring pixels', 'contribution_percent': [round(float(n/depth.size*100),4) for n in counts],
            'uncertain_percent': round(float(ambiguous.mean()*100),2),
            'seam_risk_percent': round(float(risk.mean()*100),2), 'regions': regions,
            'warnings': warnings, 'analysis': 'local-multiscale-laplacian-sobel-focus; seam risk heuristic; not AI',
            'history_note': 'Không thể xác định lịch sử stacking của ảnh không có bản ghi FocusStack chỉ từ pixel.'}


def save_focus_map(path, depth):
    # Stable colors correspond to numbered inputs, not physical depth.
    ids = np.arange(int(depth.max())+1, dtype=np.uint32)
    palette = np.stack(((ids*67+45)%256, (ids*131+100)%256, (ids*193+180)%256), axis=1).astype(np.uint8)
    Image.fromarray(palette[depth]).save(path)
