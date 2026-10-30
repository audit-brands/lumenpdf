#!/usr/bin/env python3
"""LumenPDF ocr_pdf.py — cross-platform PDF text extraction with per-page hybrid OCR.

Python port of the bash `ocr_pdf.sh` (ocr-pdf skill), built on pymupdf +
tesseract. Same output contract:

  - per-page method selection: pdftotext-equivalent (pymupdf text layer) when
    the page has >= --min-words words, tesseract OCR otherwise
  - `=== PAGE NN ===` markers on every page, 1-indexed
  - `<!-- method: ... -->` provenance comment per page
  - optional sidecar provenance JSON (--provenance)
  - optional rendered page images (--keep-images)

No poppler/coreutils required: pymupdf does extraction and rendering; the only
external binary is tesseract (skipped under --no-ocr).

Usage:
  python3 ocr_pdf.py <input.pdf> [output.md]
      [--dpi 200] [--range N-M] [--force-ocr] [--no-ocr]
      [--min-words 20] [--lang eng] [--keep-images] [--provenance] [--psm N]
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf
except ImportError:
    sys.exit("missing dependency: pip install pymupdf")


def tool_version(cmd: str, args: tuple[str, ...] = ("--version",)) -> str | None:
    if shutil.which(cmd) is None:
        return None
    try:
        out = subprocess.run(
            [cmd, *args], capture_output=True, text=True, timeout=10
        )
        for line in (out.stdout + out.stderr).splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="input PDF")
    p.add_argument("output", nargs="?", help="output Markdown (default: <stem>_text.md)")
    p.add_argument("--dpi", type=int, default=200, help="render DPI for OCR (default 200)")
    p.add_argument("--range", dest="page_range", metavar="N-M", help="1-indexed inclusive page range")
    p.add_argument("--force-ocr", action="store_true", help="OCR every page, even with a text layer")
    p.add_argument("--no-ocr", action="store_true", help="never OCR; sparse pages are passed through and flagged")
    p.add_argument("--min-words", type=int, default=20, help="words/page below which a page is OCR'd (default 20)")
    p.add_argument("--lang", default="eng", help="tesseract language(s), '+'-joined (default eng)")
    p.add_argument("--psm", type=int, default=6, help="tesseract page segmentation mode (default 6)")
    p.add_argument("--keep-images", action="store_true", help="save rendered page PNGs as provenance")
    p.add_argument("--provenance", action="store_true", help="write sidecar provenance JSON")
    return p.parse_args()


def parse_range(spec: str | None, total: int) -> tuple[int, int]:
    if not spec:
        return 1, total
    first, _, last = spec.partition("-")
    first = int(first) if first.strip() else 1
    last = int(last) if last.strip() else total
    if not (1 <= first <= last <= total):
        sys.exit(f"invalid --range {spec} for {total}-page document")
    return first, last


def ocr_page(png: Path, lang: str, psm: int) -> str:
    """OCR one rendered page, with --psm 6 fallback to auto mode."""
    for mode in (psm, 3):
        try:
            out = subprocess.run(
                ["tesseract", str(png), "stdout", "-l", lang, "--psm", str(mode)],
                capture_output=True, text=True, timeout=120,
            )
            if out.returncode == 0:
                return out.stdout
        except FileNotFoundError:
            sys.exit("missing dependency: tesseract (see SKILL.md for per-OS install)")
        except subprocess.TimeoutExpired:
            continue
    return ""


def main() -> None:
    args = parse_args()
    src = Path(args.input).resolve()
    if not src.is_file():
        sys.exit(f"input not found: {src}")
    out = Path(args.output).resolve() if args.output else src.with_name(f"{src.stem}_text.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    total = doc.page_count
    first, last = parse_range(args.page_range, total)
    npages = last - first + 1

    images_dir: Path | None = None
    tmp = None
    if args.keep_images:
        images_dir = src.parent / f"{src.stem}_pages"
        images_dir.mkdir(exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        images_dir = Path(tmp.name)

    lines: list[str] = [
        f"<!-- source: {src}",
        f"     extracted: {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"     pages: {npages} (range {first}-{last} of {total})",
        "",
    ]
    pages_prov: list[dict] = []
    thin_pages: list[int] = []
    text_pages = ocr_pages = 0

    for pageno in range(first, last + 1):
        page = doc[pageno - 1]  # pymupdf is 0-indexed; output stays 1-indexed
        text = page.get_text("text")
        words = len(text.split())
        use_ocr = args.force_ocr or (words < args.min_words and not args.no_ocr)
        if words < args.min_words and args.no_ocr:
            thin_pages.append(pageno)

        png = images_dir / f"page-{pageno}.png"
        if use_ocr:
            if not png.exists():
                page.get_pixmap(dpi=args.dpi).save(png)
            text = ocr_page(png, args.lang, args.psm)
            method = "tesseract"
            ocr_pages += 1
            rec: dict = {"page": pageno, "method": method, "pdftotext_words": words,
                         "image": f"{images_dir.name}/{png.name}", "dpi": args.dpi, "ocr_lang": args.lang}
        else:
            method = "pdftotext"
            text_pages += 1
            rec = {"page": pageno, "method": method, "pdftotext_words": words}
            if args.keep_images:
                if not png.exists():
                    page.get_pixmap(dpi=args.dpi).save(png)
                rec["image"] = f"{images_dir.name}/{png.name}"

        lines += [f"=== PAGE {pageno} ===", f"<!-- method: {method} ({words} words) -->", text, ""]

        rec["chars"] = len(text)
        pages_prov.append(rec)
        print(f"  page {pageno}: {method} ({words} words)", file=sys.stderr)

    out.write_text("\n".join(lines), encoding="utf-8")
    out_words = len("\n".join(lines).split())

    if args.provenance:
        prov = {
            "transcript": str(out),
            "source": str(src),
            "extracted_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pages_total": total,
            "page_range": [first, last],
            "pages_text_layer": text_pages,
            "pages_ocr": ocr_pages,
            "min_words_threshold": args.min_words,
            "force_ocr": args.force_ocr,
            "no_ocr": args.no_ocr,
            "images_kept": args.keep_images,
            "output_words": out_words,
            "output_bytes": out.stat().st_size,
            "tools": {
                "pymupdf": pymupdf.__version__,
                "tesseract": tool_version("tesseract"),
            },
            "pages": pages_prov,
        }
        prov_path = out.with_suffix(".prov.json")  # deterministic: <output>.prov.json
        prov_path.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")

    method_desc = (
        f"hybrid ({text_pages} text-layer pages, {ocr_pages} OCR pages)"
        if text_pages and ocr_pages
        else "tesseract (all pages)" if ocr_pages
        else "pdftotext (all pages)"
    )
    print("OCR-PDF extraction complete")
    print(f"  input        : {src}")
    print(f"  output       : {out}")
    print(f"  pages        : {npages} (range {first}-{last} of {total})")
    print(f"  method       : {method_desc}")
    if args.no_ocr and thin_pages:
        print(f"  thin pages   : {', '.join(map(str, thin_pages))} (had < {args.min_words} words; OCR skipped)")
    if ocr_pages:
        print(f"  dpi          : {args.dpi}")
        print(f"  ocr lang     : {args.lang}")
    if args.keep_images:
        print(f"  images       : {images_dir}")
    if args.provenance:
        print(f"  provenance   : {prov_path}")
    print(f"  output words : {out_words}")
    print(f"  output size  : {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
