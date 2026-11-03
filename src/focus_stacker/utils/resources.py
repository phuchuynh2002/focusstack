"""Transparent, conservative heuristics; estimates are not measurements."""
import os
import subprocess
import sys


def automatic_settings(shape):
    # Scale the focus energy window with image width; bounded for predictable runtime.
    radius = min(8.0, max(1.0, round(max(shape[:2]) / 1500, 1)))
    smoothing = min(15, max(3, int(round(radius * 2)) | 1))
    return radius, smoothing


def estimate_resources(shape, count):
    h, w = shape[:2]
    # float RGB images, masks and transient focus/alignment/pyramid/output buffers.
    estimate = h * w * (13 * count + 130) * 1.3
    try:
        if sys.platform == 'darwin':
            total = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True).strip())
        else:
            total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        total = 0
    return {'estimated_gib': estimate / 2**30, 'total_gib': total / 2**30,
            'logical_cpus': os.cpu_count() or 1,
            'note': 'rough estimate, not measured peak; excludes other processes and decoder variation'}
