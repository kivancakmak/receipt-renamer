"""Load receipts as page images (read-only; originals are never modified)."""
from pathlib import Path

SUPPORTED = {".pdf", ".jpg", ".jpeg", ".png"}


def iter_receipts(folder: Path):
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            yield p


def load_png_pages(path: Path, max_pages: int = 2, zoom: float = 2.0) -> list[bytes]:
    """Return PNG bytes per page (images -> 1 page)."""
    import fitz  # PyMuPDF
    if path.suffix.lower() == ".pdf":
        out = []
        with fitz.open(path) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                out.append(page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png"))
        return out
    import io
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return [buf.getvalue()]
