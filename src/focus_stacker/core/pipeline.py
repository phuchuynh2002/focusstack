from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import cv2

from focus_stacker.core.align.ecc import align
from focus_stacker.core.fusion.depth import fuse
from focus_stacker.core.io.images import load, save, profile
from focus_stacker.core.io.loader import load_stack
from focus_stacker.core.workflow import MARKER, digest, stack_record, validate_rendered, save_focus_map

from focus_stacker.core.task import StackTask
from focus_stacker.core.io.formats import RAW
from focus_stacker.utils.resources import estimate_resources, automatic_settings

LOG = logging.getLogger(__name__)


def run_task(task: StackTask, progress=None, preview=None) -> None:
    """Execute a validated task through import, alignment, fusion and export."""
    settings = task.settings
    return run(list(task.sources), task.output, do_align=settings.align, radius=settings.radius,
               smoothing=settings.smoothing, quality=settings.quality,
               depth_output=task.depth_output, report_output=task.report_output,
               map_output=task.map_output, scan_only=task.scan_only,
               rendered_only=settings.rendered_only, automatic=settings.automatic, desktop_inputs=settings.desktop_inputs, load_workers=settings.load_workers,
               auto_resize_mismatched=settings.auto_resize_mismatched, progress=progress, preview=preview, prealigned_cache=task.prealigned_cache)


def run(paths: list[Path], output: Path, *, do_align: bool = True, radius: float = 3,
        smoothing: int = 5, depth_output: Path | None = None, quality: int = 95,
        report_output: Path | None = None, map_output: Path | None = None,
        scan_only: bool = False, rendered_only: bool = False, automatic: bool = False, desktop_inputs: bool = False, load_workers: int = 2, auto_resize_mismatched: bool = False, progress=None, preview=None, prealigned_cache=None) -> None:
    if len(paths) < 2:
        raise ValueError('At least two images are required')
    if scan_only and report_output is None:
        raise ValueError('Scan requires a report path')
    if report_output and not scan_only and output.suffix.lower() not in {'.tif', '.tiff'}:
        raise ValueError('Verified stack reports require TIFF output')
    destinations = [p.resolve() for p in (output, depth_output, report_output, map_output) if p]
    if len(set(destinations)) != len(destinations) or set(destinations) & {p.resolve() for p in paths}:
        raise ValueError('Output paths must be distinct and must not overwrite an input image')

    def emit(percent, message):
        LOG.info('%s', message)
        if progress: progress(percent, message)

    emit(1, f'Kiểm tra {len(paths)} ảnh đầu vào')
    if rendered_only:
        validate_rendered(paths)
    if any(p.suffix.lower() in RAW for p in paths) and not all(p.suffix.lower() in RAW for p in paths):
        raise ValueError('Không trộn RAW và ảnh đã render trong cùng stack: hãy dùng cùng định dạng để đảm bảo màu nhất quán.')
    images, masks = [], []
    report = {'format': MARKER, 'status': 'scanned' if scan_only else 'completed',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'input_count': len(paths), 'sources': [],
              'settings': {'align': do_align, 'radius': radius, 'smoothing': smoothing},
              'rendered_tiff_validation': rendered_only,
              'capture_one_adjustments': 'RAW sidecar edits are not applied; TIFF provenance not independently verified.'}
    reference = None
    raw_wb = None
    if all(p.suffix.lower() in RAW for p in paths):
        try:
            import rawpy
            with rawpy.imread(str(paths[0])) as raw:
                wb = list(raw.camera_whitebalance)
                if len(wb) != 4 or not all(np.isfinite(x) and x > 0 for x in wb[:3]):
                    raise ValueError('RAW không có cân bằng trắng máy ảnh hợp lệ')
                wb[3] = wb[3] if np.isfinite(wb[3]) and wb[3] > 0 else wb[1]
                raw_wb = wb
        except Exception as exc:
            raise ValueError(f'Cannot decode RAW {paths[0]}: {exc}. Try exporting RGB 16-bit TIFF.') from exc
        report['raw_development'] = {'color_space': 'sRGB', 'white_balance': raw_wb,
                                     'source': 'first RAW camera white balance; applied to entire stack',
                                     'capture_one_adjustments': 'not applied'}
    emit(5, f'Nạp ảnh song song: tối đa {load_workers} luồng')
    loaded = load_stack(paths, max_workers=load_workers, auto_resize_mismatched=auto_resize_mismatched,
                        raw_wb=raw_wb, verify_files=bool(report_output),
                        progress_callback=lambda i,n,message: emit(5+int(20*i/n), message))
    profiles = [item.icc for item in loaded.items]
    report['loading'] = {'workers': min(load_workers, len(paths)), 'mode': loaded.target_mode,
                         'resize_mismatched': auto_resize_mismatched,
                         'source_bit_depth': loaded.reference_dtype.itemsize * 8}
    reference = loaded.items[0].image
    estimate = estimate_resources(reference.shape, len(paths))
    report['resources'] = estimate
    emit(25, f"Ước lượng RAM xử lý: {estimate['estimated_gib']:.2f} GiB; chưa gồm bộ đệm giải mã song song.")
    if automatic:
        radius, smoothing = automatic_settings(reference.shape)
        report['settings'].update(radius=radius, smoothing=smoothing, automatic=True)
        emit(25, f'Tự động: radius {radius}, smoothing {smoothing}.')
    cached = False
    if prealigned_cache and do_align and report_output:
        try:
            manifest = json.loads((prealigned_cache / 'manifest.json').read_text(encoding='utf-8'))
            cached = (manifest['sources'] == [str(p.resolve()) for p in paths]
                      and manifest['sha256'] == [item.sha256 for item in loaded.items]
                      and manifest['resize'] == auto_resize_mismatched
                      and manifest['rendered_only'] == rendered_only)
        except (OSError, ValueError, KeyError, TypeError):
            cached = False
        if cached: emit(25, 'Dùng căn chỉnh đã kiểm tra từ lúc nhập.')
    for index, item in enumerate(loaded.items):
        image = item.image
        if report_output:
            report['sources'].append({'path': str(item.path.resolve()), 'sha256': item.sha256,
                                      'prior_stack_record': stack_record(item.path) is not None,
                                      'original_dtype': str(item.original_dtype),
                                      'original_shape': list(item.shape), 'transformations': item.changes})
        for change in item.changes:
            emit(25+int(15*index/len(paths)), f'{item.path.name}: {change}')
        mask = np.ones(image.shape[:2], dtype=bool)
        if cached:
            try:
                with np.load(prealigned_cache / f'{index}.npz', allow_pickle=False) as record:
                    image, mask = record['image'], record['mask']
                    if image.shape != reference.shape or image.dtype != np.float32 or mask.shape != reference.shape[:2] or mask.dtype != bool:
                        raise ValueError('Invalid cached alignment')
            except (OSError, ValueError, KeyError) as exc:
                raise ValueError('Bộ đệm căn chỉnh lỗi; hãy nhập lại ảnh.') from exc
        elif index and do_align:
            emit(25+int(15*index/len(paths)), f'Căn chỉnh ảnh {index+1}/{len(paths)}: {item.path.name}')
            image, mask, score = align(reference, image)
            LOG.info('ECC correlation: %.4f', score)
        # Release the unaligned array as soon as the replacement is available.
        item.image = image
        images.append(image)
        masks.append(mask)
        if preview is not None:
            scale = min(1.0, 1000 / max(image.shape[:2]))
            thumb = cv2.resize(image, (max(1, round(image.shape[1]*scale)), max(1, round(image.shape[0]*scale))), interpolation=cv2.INTER_AREA)
            preview(thumb, index, len(paths), 'alignment')
    diagnostics = {} if report_output else None
    result, depth = fuse(images, masks, radius, smoothing, diagnostics=diagnostics, scan_only=scan_only,
                         progress=lambda i,n: emit(40+int(35*i/n), f'Quét độ nét toàn ảnh {i+1}/{n}: {paths[i].name}'),
                         preview=preview)
    emit(78, 'Tổng hợp vùng nét và mức đóng góp từng ảnh')
    if diagnostics is not None:
        report.update(diagnostics)
        report['width'], report['height'] = int(depth.shape[1]), int(depth.shape[0])
    if map_output:
        save_focus_map(map_output, depth)
    if not scan_only:
        emit(85, 'Ghép vùng nét và ghi TIFF')
        metadata = json.dumps({'format': MARKER, 'input_count': len(paths),
                               'created_utc': report['created_utc'],
                               'sources_used': report.get('sources_used')}) if report_output else None
        save(output, result, quality, icc=profiles[0], description=metadata)
        if depth_output:
            save(depth_output, depth.astype(np.float32)/(len(images)-1))
        if report_output:
            emit(94, 'Đọc lại TIFF: kiểm tra pixel, kích thước và ICC')
            check = load(output)
            expected = np.rint(np.clip(result, 0, 1)*65535).astype(np.float32)/65535
            if not np.array_equal(check, expected) or profile(output) != profiles[0]:
                raise ValueError('TIFF verification failed: pixels or ICC differ')
            report['output'] = {'path': str(output.resolve()), 'sha256': digest(output),
                                'verified': True, 'bit_depth': 16,
                                'icc_preserved': profile(output) == profiles[0]}
    if report_output:
        report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    emit(100, 'Quét hoàn tất — chưa ghép ảnh' if scan_only else 'Ghép hoàn tất — TIFF đã được tạo')
