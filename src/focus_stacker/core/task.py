"""Validated settings for a single stacking job, independent of the UI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math


@dataclass(frozen=True)
class RenderSettings:
    align: bool = True
    radius: float = 3.0
    smoothing: int = 5
    rendered_only: bool = False
    quality: int = 95
    automatic: bool = False
    desktop_inputs: bool = False
    load_workers: int = 2
    auto_resize_mismatched: bool = False

    def __post_init__(self):
        if not isinstance(self.load_workers, int) or not 1 <= self.load_workers <= 8:
            raise ValueError('load_workers must be between 1 and 8')
        if not math.isfinite(self.radius) or self.radius < 0:
            raise ValueError('Radius must be finite and nonnegative')
        if self.smoothing < 1 or self.smoothing % 2 == 0:
            raise ValueError('Smoothing must be a positive odd integer')
        if not 1 <= self.quality <= 100:
            raise ValueError('JPEG quality must be between 1 and 100')

    def worker_args(self) -> list[str]:
        args = ['--radius', str(self.radius), '--smoothing', str(self.smoothing),
                '--quality', str(self.quality)]
        args.extend(['--load-workers', str(self.load_workers)])
        if self.auto_resize_mismatched:
            args.append('--resize-mismatched')
        if not self.align:
            args.append('--no-align')
        if self.desktop_inputs:
            args.append('--desktop-inputs')
        if self.automatic:
            args.append('--automatic')
        if self.rendered_only:
            args.append('--rendered-only')
        return args


@dataclass(frozen=True)
class StackTask:
    sources: tuple[Path, ...]
    output: Path
    settings: RenderSettings = RenderSettings()
    depth_output: Path | None = None
    report_output: Path | None = None
    map_output: Path | None = None
    scan_only: bool = False
    prealigned_cache: Path | None = None

    def __post_init__(self):
        if len(self.sources) < 2:
            raise ValueError('At least two images are required')
        resolved = [p.resolve() for p in self.sources]
        if len(set(resolved)) != len(resolved):
            raise ValueError('Duplicate source images are not allowed')
        destinations = [p.resolve() for p in (self.output, self.depth_output,
                                               self.report_output, self.map_output) if p]
        if len(set(destinations)) != len(destinations) or set(destinations) & set(resolved):
            raise ValueError('Output paths must be distinct and must not overwrite an input image')
        if self.scan_only and self.report_output is None:
            raise ValueError('Scan requires a report path')
        if self.report_output and not self.scan_only and self.output.suffix.lower() not in {'.tif', '.tiff'}:
            raise ValueError('Verified stack reports require TIFF output')
