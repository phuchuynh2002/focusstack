"""Accepted file extensions; decoding individual cameras depends on LibRaw."""

RAW = {
    ".3fr", ".arw", ".cr2", ".cr3", ".crw", ".dcr", ".dng", ".erf",
    ".fff", ".iiq", ".kdc", ".mef", ".mos", ".mrw", ".nef", ".nrw",
    ".orf", ".pef", ".raf", ".raw", ".rw2", ".rwl", ".sr2", ".srf",
    ".srw", ".x3f",
}
RASTER = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
FORMATS = RAW | RASTER


def file_filter() -> str:
    def patterns(extensions):
        return " ".join(f"*{ext} *{ext.upper()}" for ext in sorted(extensions))
    return (f"Ảnh và RAW ({patterns(FORMATS)});;"
            f"Camera RAW ({patterns(RAW)});;Ảnh RGB ({patterns(RASTER)})")
