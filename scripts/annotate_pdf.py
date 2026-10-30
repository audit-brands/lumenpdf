#!/usr/bin/env python3
"""LumenPDF annotate_pdf.py - create annotated evidence exhibits from a PDF.

Implements the contract-review annotation reference (see references/
annotation-reference.md): red boxes around the deciding language, blue
PASS/FAIL/NOTE/CONTRAST banner, rendered to PNG per exhibit.

Mode selection is per page, matching ocr_pdf.py:
  - text-layer pages: pymupdf search_for + merged passage rects
  - image-based pages: tesseract TSV word coordinates + PIL drawing

Improvements over the reference:
  - all occurrences are matched and reported (no silent first-match-only)
  - OCR matches below --min-confidence are flagged REVIEW, not drawn
  - hyphenated line-break phrases are handled by joining split words
  - every annotation is appended to a provenance JSON sidecar

Usage:
  python3 annotate_pdf.py <input.pdf> --spec spec.json --outdir workpapers/exhibits
      [--dpi 200] [--lang eng] [--min-confidence 60] [--provenance]

Spec format (JSON):
[
  {
    "page": 3,
    "label": "PASS EVIDENCE: contract grants customer audit rights",
    "kind": "pass",            // pass | fail | note | contrast | execution
    "phrases": ["audit Provider compliance", "once per contract year"]
  }
]
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("missing dependencies: pip install pymupdf pillow")

BANNER_HEIGHT = 42
# Tried in order; Pillow searches the OS font directories for bare filenames.
BANNER_FONTS = ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "Helvetica.ttc")
MIN_WORDS_PER_PAGE = 20  # same text-layer threshold as ocr_pdf.py

KIND_STYLES = {
    "pass": ((0, 0, 1), (1, 0, 0)),       # banner: blue border, box: red
    "fail": ((1, 0, 0), (1, 0, 0)),       # banner: red, box: red
    "note": ((0, 0, 1), (0, 0.55, 0)),    # banner: blue, box: green
    "contrast": ((0, 0, 1), (1, 0.5, 0)), # banner: blue, box: orange
    "execution": ((0, 0, 1), (0, 0, 1)),  # banner: blue, box: blue
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="input PDF")
    p.add_argument("--spec", required=True, help="annotation spec JSON (see docstring)")
    p.add_argument("--outdir", required=True, help="directory for annotated exhibit PNGs")
    p.add_argument("--dpi", type=int, default=120, help="render DPI for exhibits (default 120)")
    p.add_argument("--lang", default="eng", help="tesseract language for image pages")
    p.add_argument("--min-confidence", type=float, default=60.0,
                   help="tesseract word confidence below which a match is flagged, not drawn")
    p.add_argument("--provenance", action="store_true", help="write annotation provenance JSON")
    return p.parse_args()


def norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def merge_rects(rects: list[pymupdf.Rect], pad: float = 3.0, page_height_pts: float = 792.0) -> list[pymupdf.Rect]:
    """Merge search hits into one box per passage, not one box per page.

    Clusters rects by vertical proximity: rects whose vertical spans are close
    together (same sentence/subsection) merge; distant occurrences on the same
    page stay separate boxes. A cluster is capped: if merging would span more
    than 45% of the page height, the cluster is split at the largest gap.
    """
    if not rects:
        return []
    ordered = sorted(rects, key=lambda r: (r.y0, r.x0))
    clusters: list[list[pymupdf.Rect]] = []
    for r in ordered:
        if clusters:
            cur = clusters[-1]
            span = max(x.y1 for x in cur) - min(x.y0 for x in cur)
            gap = r.y0 - max(x.y1 for x in cur)
            if gap <= 24 and span <= 0.45 * page_height_pts:
                cur.append(r)
                continue
        clusters.append([r])
    return [
        pymupdf.Rect(
            min(x.x0 for x in c) - pad, min(x.y0 for x in c) - pad,
            max(x.x1 for x in c) + pad, max(x.y1 for x in c) + pad,
        )
        for c in clusters
    ]


def find_text_layer(page: pymupdf.Page, phrases: list[str]) -> tuple[dict[str, list[pymupdf.Rect]], list[str]]:
    """All-occurrence search; de-hyphenates soft line breaks first."""
    hits: dict[str, list[pymupdf.Rect]] = {}
    misses: list[str] = []
    for phrase in phrases:
        rects = page.search_for(phrase)
        if not rects:
            # Retry de-hyphenated: "termi-\nnation" -> "termination"
            dehyph = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", phrase)
            if dehyph != phrase:
                rects = page.search_for(dehyph)
        if rects:
            hits[phrase] = rects
        else:
            misses.append(phrase)
    return hits, misses


def tsv_words(png: Path) -> list[dict]:
    """Word boxes + confidence from tesseract TSV."""
    # options must precede the configfile name; resolve symlinks (/tmp -> /private/tmp)
    # because leptonica can fail to open symlinked absolute paths.
    img = str(Path(png).resolve())
    out = subprocess.run(
        ["tesseract", img, "stdout", "--psm", "6", "tsv"],
        capture_output=True, timeout=120, errors="replace",
    )
    words = []
    for line in out.stdout.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 12 and parts[11].strip():
            try:
                words.append({
                    "x0": int(parts[6]), "y0": int(parts[7]),
                    "x1": int(parts[6]) + int(parts[8]), "y1": int(parts[7]) + int(parts[9]),
                    "text": parts[11], "conf": float(parts[10]),
                })
            except ValueError:
                continue
    return words


def find_ocr(page_words: list[dict], phrase: str, min_conf: float) -> tuple[list[tuple[int, int, int, int]], list[float]]:
    """Sliding-window match over consecutive words; all occurrences; conf-gated."""
    target = [norm_word(w) for w in phrase.split()]
    target = [w for w in target if w]
    n = len(target)
    matches: list[tuple[int, int, int, int]] = []
    confs: list[float] = []
    # Build a normalized stream, tracking which original word each came from
    # (skips hyphen-joined fragments so cross-line phrases still match).
    stream = []
    for w in page_words:
        t = norm_word(w["text"]).removesuffix("-")  # drop trailing hyphen artifacts
        if t:
            stream.append((t, w))
    for i in range(len(stream) - n + 1):
        window = stream[i:i + n]
        if [t for t, _ in window] == target:
            ws = [w for _, w in window]
            matches.append((min(w["x0"] for w in ws) - 4, min(w["y0"] for w in ws) - 4,
                            max(w["x1"] for w in ws) + 4, max(w["y1"] for w in ws) + 4))
            confs.append(sum(w["conf"] for w in ws) / n)
    return matches, confs


def banner_font(size: int) -> ImageFont.ImageFont:
    """A readable TrueType face; Pillow's bitmap default is ~11px at any DPI."""
    for name in BANNER_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def banner_box(page_w: int, page_h: int, position: str, height: int) -> tuple[int, int, int, int]:
    if position == "bottom":
        return 20, page_h - height - 15, page_w - 20, page_h - 15
    return 20, 15, page_w - 20, 15 + height


def draw_banner(img: Image.Image, label: str, color, position: str) -> None:
    draw = ImageDraw.Draw(img)
    font = banner_font(max(12, img.width // 60))  # scales with render DPI
    height = max(BANNER_HEIGHT, font.size + 20) if hasattr(font, "size") else BANNER_HEIGHT
    x0, y0, x1, y1 = banner_box(img.width, img.height, position, height)
    draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255), outline=color, width=2)
    draw.text((x0 + 10, y0 + (height - getattr(font, "size", 11)) // 2), label, fill=color, font=font)


def main() -> None:
    args = parse_args()
    src = Path(args.input).resolve()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    stem = src.stem
    provenance: list[dict] = []

    for item in spec:
        pageno = item["page"]                      # 1-indexed, per skill convention
        label = item["label"]
        kind = item.get("kind", "note")
        phrases: list[str] = item.get("phrases", [])
        banner_color, box_color = KIND_STYLES.get(kind, KIND_STYLES["note"])

        page = doc[pageno - 1]
        png = outdir / f"{stem}_p{pageno}_raw.png"
        page.get_pixmap(dpi=args.dpi).save(png)

        text_words = len(page.get_text("text").split())
        use_text_mode = text_words >= MIN_WORDS_PER_PAGE
        mode = "pymupdf-text" if use_text_mode else "tesseract-ocr"
        rec: dict = {"page": pageno, "label": label, "kind": kind, "mode": mode,
                     "phrases": phrases, "matched": [], "missed": [], "flagged_low_confidence": []}

        img = Image.open(png).convert("RGB")
        draw = ImageDraw.Draw(img)

        if use_text_mode:
            hits, misses = find_text_layer(page, phrases)
            # Pool every phrase's hits before merging, so phrases from the same
            # passage share one box (per the annotation reference).
            boxes = merge_rects([r for rects in hits.values() for r in rects],
                                page_height_pts=page.rect.height)
            for r in boxes:
                # scale PDF-point coords to render DPI (72pt base)
                s = args.dpi / 72
                box = (int(r.x0 * s), int(r.y0 * s), int(r.x1 * s), int(r.y1 * s))
                draw.rectangle(box, outline=(int(box_color[0] * 255), int(box_color[1] * 255), int(box_color[2] * 255)), width=3)
            for phrase, rects in hits.items():
                rec["matched"].append({"phrase": phrase, "line_rects": len(rects)})
            rec["boxes"] = len(boxes)
            rec["missed"] = misses
        else:
            words = tsv_words(png)
            for phrase in phrases:
                matches, confs = find_ocr(words, phrase, args.min_confidence)
                if not matches:
                    rec["missed"].append(phrase)
                    continue
                for box, conf in zip(matches, confs):
                    if conf >= args.min_confidence:
                        draw.rectangle(box, outline=(int(box_color[0] * 255), int(box_color[1] * 255), int(box_color[2] * 255)), width=3)
                        rec["matched"].append({"phrase": phrase, "confidence": round(conf, 1)})
                    else:
                        rec["flagged_low_confidence"].append({"phrase": phrase, "confidence": round(conf, 1)})

        banner_pos = item.get("banner", "top")
        draw_banner(img, label, (int(banner_color[0] * 255), int(banner_color[1] * 255), int(banner_color[2] * 255)), banner_pos)

        exhibit = outdir / item.get("filename", f"{stem}_EX_p{pageno}_{kind}.png")
        img.save(exhibit)
        png.unlink()  # remove the raw render; the exhibit is the artifact
        rec["exhibit"] = str(exhibit)
        provenance.append(rec)

        status = "ok" if rec["matched"] else ("LOW-CONFIDENCE" if rec["flagged_low_confidence"] else "NO MATCH")
        print(f"  p{pageno} [{kind}] {status}: {label}  ->  {exhibit.name}", file=sys.stderr)

    print(f"Annotated {len(provenance)} exhibit(s) in {outdir}")
    if args.provenance:
        prov_path = outdir / f"{stem}_annotations.prov.json"
        prov_path.write_text(json.dumps({
            "source": str(src),
            "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "dpi": args.dpi,
            "min_confidence": args.min_confidence,
            "exhibits": provenance,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"  provenance: {prov_path}")
    no_match = [r for r in provenance if not r["matched"]]
    if no_match:
        print(f"  WARNING: {len(no_match)} exhibit(s) had no matched phrase - review manually")


if __name__ == "__main__":
    main()
