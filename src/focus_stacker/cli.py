from __future__ import annotations

import argparse
import logging
import json
from pathlib import Path

from focus_stacker.utils.logging import setup_logging
from focus_stacker.core.io.images import discover
from focus_stacker.core.pipeline import run_task
from focus_stacker.core.task import RenderSettings, StackTask


def main() -> int:
    parser = argparse.ArgumentParser(description="Stack images using a depth map (M1)")
    parser.add_argument("inputs", nargs="+", help="Image files and/or directories")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .tif, .png or .jpg")
    parser.add_argument("--depth", type=Path, help="Optional depth-map .png or .tif")
    parser.add_argument("--sort", choices=["name", "time"], default="name")
    parser.add_argument("--no-align", action="store_true")
    parser.add_argument("--radius", type=float, default=3, help="Gaussian focus-energy sigma in pixels")
    parser.add_argument("--smoothing", type=int, default=5, help="Odd median-filter window in pixels")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality 1–100")
    parser.add_argument('--report', type=Path, help='Write scan/verified stack report JSON')
    parser.add_argument('--focus-map', type=Path, help='Source-region visualization PNG')
    parser.add_argument('--scan-only', action='store_true')
    parser.add_argument('--rendered-only', action='store_true', help='Require RGB 16-bit TIFF with ICC')
    parser.add_argument('--desktop-inputs', action='store_true', help='Desktop input mode (all supported image formats)')
    parser.add_argument('--load-workers', type=int, default=2, help='Parallel image decoders (1–8)')
    parser.add_argument('--resize-mismatched', action='store_true', help='Explicitly resize mismatched images to the first image')
    parser.add_argument('--automatic', action='store_true', help='Select radius and smoothing from image dimensions')
    parser.add_argument('--prealigned-cache', type=Path, help='Temporary verified import alignment cache')
    parser.add_argument('--preview-output', type=Path, help='Temporary progressive preview for desktop')
    parser.add_argument('--events', action='store_true', help='Emit progress records for the desktop UI')
    args = parser.parse_args()
    setup_logging()
    try:
        if args.depth and args.depth.suffix.lower() not in {".png", ".tif", ".tiff"}:
            raise ValueError("Depth map must be PNG or TIFF")
        paths = discover(args.inputs, args.sort)
        settings = RenderSettings(align=not args.no_align, radius=args.radius,
                                  smoothing=args.smoothing, quality=args.quality,
                                  rendered_only=args.rendered_only, automatic=args.automatic, desktop_inputs=args.desktop_inputs,
                                  load_workers=args.load_workers, auto_resize_mismatched=args.resize_mismatched)
        task = StackTask(tuple(paths), args.output, settings, depth_output=args.depth,
                         report_output=args.report, map_output=args.focus_map, scan_only=args.scan_only, prealigned_cache=args.prealigned_cache)
        def preview(image, index, count, stage):
            if not args.preview_output: return
            import cv2
            import numpy as np
            import os
            import io
            from PIL import Image, ImageCms
            from focus_stacker.core.io.images import profile
            temp = args.preview_output.with_suffix('.tmp.png')
            pixels = np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8)
            icc = profile(paths[0])
            if icc:
                converted = ImageCms.profileToProfile(Image.fromarray(pixels), ImageCms.ImageCmsProfile(io.BytesIO(icc)), ImageCms.createProfile('sRGB'), outputMode='RGB')
                pixels = np.asarray(converted)
            if not cv2.imwrite(str(temp), cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)):
                raise OSError('Cannot write progressive preview')
            os.replace(temp, args.preview_output)
            print('FOCUSSTACK_PREVIEW ' + json.dumps({'path': str(args.preview_output), 'index': index + 1, 'count': count, 'stage': stage}), flush=True)
        run_task(task, progress=(lambda percent, message: print('FOCUSSTACK_EVENT ' + json.dumps(
            {'percent': percent, 'message': message}, ensure_ascii=False), flush=True)) if args.events else None,
            preview=preview if args.preview_output else None)
    except (ValueError, OSError, MemoryError) as exc:
        logging.error("%s", exc or "Not enough memory; use smaller images")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
