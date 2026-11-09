"""Build safe target filenames."""
import re
from pathlib import Path

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str, max_len: int = 40) -> str:
    s = _ILLEGAL.sub("", name)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s).strip("-._")
    return s[:max_len] or "Unknown"


def build_name(date: str, merchant: str, currency: str, total: str, ext: str) -> str:
    return f"{date}_{sanitize(merchant)}_{currency}{total}{ext.lower()}"


def unique_path(directory: Path, filename: str) -> Path:
    p = directory / filename
    n = 2
    while p.exists():
        p = directory / f"{Path(filename).stem}_{n}{Path(filename).suffix}"
        n += 1
    return p
