#!/usr/bin/env python
"""Rename scanned receipts to YYYY-MM-DD_Merchant_CurrencyAmount.ext (copies; originals untouched)."""
import argparse
import csv
import os
import shutil
from pathlib import Path

from receipt_pipeline.loader import iter_receipts, load_png_pages
from receipt_pipeline.namer import build_name, unique_path
from receipt_pipeline.parser import parse_receipt


def process(path, use_ocr, use_llm, min_conf):
    pages = load_png_pages(path)
    parsed, conf, method = None, 0.0, ""
    llm_err = None
    # 1) LLM first (most accurate); 2) local OCR + rules as offline fallback.
    if use_llm:
        from receipt_pipeline.llm import available_provider, extract
        try:
            parsed, conf = extract(pages)
            method = available_provider()
            if conf < 0.7:
                parsed.issues.append(f"low confidence {conf:.2f}")
            return parsed, conf, method
        except Exception as e:
            llm_err = f"LLM failed ({e}); "
    if use_ocr:
        from receipt_pipeline.ocr import ocr_lines
        lines, conf = ocr_lines(pages)
        parsed, method = parse_receipt(lines), "local"
        if conf < min_conf:
            parsed.issues.append(f"low OCR confidence {conf:.2f}")
        if llm_err:
            parsed.issues.append(llm_err.rstrip("; "))
    return parsed, conf, method


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("output"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="offline only; never send data out")
    ap.add_argument("--llm-only", action="store_true", help="skip local OCR")
    ap.add_argument("--min-conf", type=float, default=0.85)
    a = ap.parse_args()

    from receipt_pipeline.llm import available_provider
    use_llm = not a.no_llm and available_provider() is not None
    if not a.no_llm and not use_llm:
        print("No LLM provider configured (GEMINI_API_KEY / RECEIPT_PROVIDER=ollama): running offline.")
    elif use_llm:
        print(f"LLM fallback: {available_provider()}")
    ren, rev = a.out / "renamed", a.out / "review"
    if not a.dry_run:
        ren.mkdir(parents=True, exist_ok=True)
        rev.mkdir(parents=True, exist_ok=True)

    rows = []
    for f in iter_receipts(a.input_dir):
        err = "no extractor available (OCR failed to load, no API key)"
        try:
            p, conf, method = process(f, not a.llm_only, use_llm, a.min_conf)
        except Exception as e:  # never guess on failure
            p, conf, method = None, 0.0, "error"
            err = f"error: {e}"
        ok = p is not None and p.complete
        if ok:
            new = build_name(p.date, p.merchant, p.currency, p.total, f.suffix)
            dest = unique_path(ren, new)
            status, reason = "renamed", ""
        else:
            dest = unique_path(rev, f.name)
            status = "review"
            reason = "; ".join(p.issues) if p else err
        if not a.dry_run:
            shutil.copy2(f, dest)
        rows.append([f.name, dest.name, status, method, getattr(p, "date", ""),
                     getattr(p, "merchant", ""), getattr(p, "currency", ""),
                     getattr(p, "total", ""), f"{conf:.2f}", reason])
        print(f"[{status}] {f.name} -> {dest.name} {reason}")

    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "log.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["original_name", "new_name", "status", "method", "date", "merchant",
                    "currency", "amount", "confidence", "review_reason"])
        w.writerows(rows)
    print(f"Done: {sum(r[2]=='renamed' for r in rows)} renamed, "
          f"{sum(r[2]=='review' for r in rows)} for review. Log: {a.out/'log.csv'}")


if __name__ == "__main__":
    main()
