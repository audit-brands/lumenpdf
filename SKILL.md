---
name: lumenpdf
description: >
  Extract text from any PDF with per-page hybrid OCR (pymupdf + tesseract),
  and create annotated evidence exhibits (highlighted passages with PASS/FAIL
  banners) for document review and evidence workpapers. Cross-platform: macOS,
  Linux, and native Windows: pure pip dependencies plus one tesseract binary.
  Also writes machine-readable provenance (per-page extraction method, word
  counts, tool versions) and can keep rendered page images. Use when the user
  says "OCR this PDF", "extract text from a PDF", "annotate this document",
  "make an evidence exhibit", "highlight the clause", "LumenPDF", or any
  PDF-to-text or PDF-annotation need.
license: MIT
---

# LumenPDF: PDF text extraction & evidence annotation

Two scripts, one provenance model. Resolve all script paths against this skill's own directory (the directory containing this SKILL.md).

| Script | Purpose |
|---|---|
| `scripts/ocr_pdf.py` | Extract text from any PDF. Per-page hybrid: exact text layer when available, tesseract OCR for scanned pages. Page-marked Markdown transcript, optional rendered images, optional provenance JSON. |
| `scripts/annotate_pdf.py` | Create annotated evidence exhibits: red boxes around deciding language, blue PASS/FAIL/NOTE/CONTRAST banner, PNG per exhibit. Text-layer mode (pymupdf) and OCR mode (tesseract TSV + PIL), chosen per page. |

## Install (per OS)

| Component | Role | License | Install |
|---|---|---|---|
| PyMuPDF (`pymupdf`) | PDF parsing, text extraction, page rendering | AGPL-3.0 or Artifex commercial | `pip install pymupdf` |
| Pillow (`pillow`) | Image drawing for OCR-mode annotation exhibits | MIT-CMU | `pip install pillow` |
| Tesseract OCR | OCR of image-based pages; TSV word coordinates for annotation | Apache-2.0 | per-OS commands below |

One command covers the pip side on every OS (prebuilt wheels, no compiler):

```bash
pip install pymupdf pillow
```

tesseract is the only external binary:

| OS | Install |
|---|---|
| macOS | `brew install tesseract` |
| Debian/Ubuntu | `sudo apt install tesseract-ocr` |
| Fedora/RHEL | `sudo dnf install tesseract` |
| Windows native | installer from UB-Mannheim builds (`winget install UB-Mannheim.TesseractOCR` or download), then add to PATH |
| WSL | use the Linux command inside WSL |

`pymupdf` and `pillow` ship prebuilt wheels for all of the above: no compiler needed.

## Extract text

```bash
python3 <skill-dir>/scripts/ocr_pdf.py document.pdf document.md --provenance --keep-images
```

| Option | Purpose |
|---|---|
| `[output.md]` | Output path (default `<input-stem>_text.md` next to input) |
| `--dpi N` | Render DPI for OCR (default 200; 300 for faint scans) |
| `--range N-M` | Only pages N-M (1-indexed, inclusive; closed ranges only) |
| `--force-ocr` | OCR every page, even with a text layer |
| `--no-ocr` | Never OCR; sparse pages passed through and listed as "thin" |
| `--min-words N` | Words/page below which a page is OCR'd (default 20) |
| `--lang ENG+DEU` | Tesseract language(s), `+`-joined |
| `--psm N` | Tesseract page segmentation mode (default 6; falls back to 3 on failure) |
| `--keep-images` | Save rendered page PNGs to `<stem>_pages/` as provenance |
| `--provenance` | Write `<output>.prov.json` sidecar |

Output: one Markdown transcript, `=== PAGE NN ===` marker per page (1-indexed), `<!-- method: pdftotext (N words) -->` or `<!-- method: tesseract ocr -->` per page, and a metadata header. The provenance JSON adds tool versions, per-page word counts, image refs, and flags.

## Annotate evidence exhibits

Write a spec JSON listing what to highlight and what the banner says (see `references/annotation-reference.md` for the full methodology):

```json
[
  {
    "page": 4,
    "kind": "pass",
    "label": "PASS EVIDENCE: Provider data protection and security obligations",
    "phrases": ["Data protection", "Security Requirements"],
    "filename": "Vendor_MSAdataprotection_annotated.png"
  }
]
```

```bash
python3 <skill-dir>/scripts/annotate_pdf.py document.pdf --spec spec.json --outdir exhibits --provenance
```

| Option | Purpose |
|---|---|
| `--spec` | Required: annotation spec JSON |
| `--outdir` | Required: directory for exhibit PNGs |
| `--dpi N` | Exhibit render DPI (default 120) |
| `--min-confidence N` | Tesseract word confidence below which a match is flagged REVIEW instead of drawn (default 60) |
| `--provenance` | Write `<stem>_annotations.prov.json` |

Kinds: `pass` (blue banner, red boxes), `fail` (red banner, red boxes), `note` (blue banner, green boxes), `contrast` (blue banner, orange boxes), `execution` (blue banner, blue boxes). Set `"banner": "bottom"` for dense pages.

Annotation rules inherited from the reference (do not violate):
- Merge search hits into **one box per passage**, never one box per word; the
  script clusters hits by proximity so repeated phrases on one page stay as separate tight boxes.
- Match **all occurrences**: the script reports counts and flags ambiguity
  rather than silently annotating the first hit.
- OCR matches below `--min-confidence` are listed as
  `flagged_low_confidence` in the provenance instead of drawn.
- Exhibits with zero matches print a WARNING; review them manually.

## Provenance model

Every artifact records how it was made:

- Transcript: per-page method comment + metadata header
- `<output>.prov.json`: per-page method, word counts, image paths, tool versions
- Exhibits: `<stem>_annotations.prov.json` with page, label, kind, mode,
  matched phrases (with occurrence counts / OCR confidence), misses, exhibit path

For audit/review evidence, default to `--provenance --keep-images`: workpapers should be able to verify what was extracted, from which pixels, with which tools.

## Agent guidance

**Installing this skill is your job when asked.** If the user says "install the LumenPDF skill from this folder", copy this whole directory (SKILL.md, scripts/, references/) into your skills directory: `~/.claude/skills/lumenpdf` for Claude Code, `~/.agents/skills/lumenpdf` for pi. Then continue with the dependency step below and report where you installed it.

**Dependencies are your job.** Before the first run in a session, check and install what is missing rather than asking the user to: `pip install pymupdf pillow` covers most cases; install tesseract per the OS table above only when a PDF has image-based pages (or install on failure). Report what you installed.

When the user has not said whether to keep provenance artifacts, **ask before running**: "Keep the page images and/or the provenance JSON?" Default to suggesting both whenever the document is review evidence, a signed agreement, or anything headed for a workpaper. Cost: roughly 0.2-1 MB per page for images. For the JSON sidecar, offer it in the same breath. For review evidence, suggest both.

## Notes

- OCR is near-perfect on clean renders but misreads stamps, tables, and
  handwriting; the per-page method comment tells you which passages to spot-check before quoting verbatim.
- Encrypted PDFs: decrypt first (`qpdf --decrypt` or pymupdf
  `doc.authenticate(password)`).
- This skill does not talk to any LLM or decision model: it is pure document
  tooling. Downstream classification/screening is a separate workflow.
- License: MIT for code and skill; CC BY 4.0 for the annotation methodology
  (references/annotation-reference.md). Retain LICENSE and NOTICE.md when redistributing.
