"""Local OCR via RapidOCR (PaddleOCR models on ONNX; Chinese + English). Imported lazily."""
import io

_engine = None


def _get():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_lines(pages_png: list[bytes]) -> tuple[list[str], float]:
    """Return (text lines top-to-bottom, mean confidence 0..1)."""
    import numpy as np
    from PIL import Image
    lines, confs = [], []
    for png in pages_png:
        arr = np.array(Image.open(io.BytesIO(png)).convert("RGB"))
        res, _ = _get()(arr)
        for box, txt, conf in res or []:
            lines.append((box[0][1], txt))
            confs.append(float(conf))
    lines.sort(key=lambda t: t[0])
    return [t for _, t in lines], (sum(confs) / len(confs) if confs else 0.0)
