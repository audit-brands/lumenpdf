# NOTICE

LumenPDF includes:

- `scripts/ocr_pdf.py` - PDF text extraction with per-page hybrid OCR.
  Python implementation of the extraction contract originally developed in the bash-based `ocr-pdf` skill (per-page method selection, page markers, provenance sidecar).

- `scripts/annotate_pdf.py` - Evidence exhibit annotation (pymupdf text mode,
  tesseract OCR mode). Implements the methodology documented in `references/annotation-reference.md`.

- `references/annotation-reference.md` - Annotation methodology from the
  contract review workpaper exhibits. Attribution: Audit Risk Media, LLC, 2026. Licensed CC BY 4.0.

When redistributing LumenPDF or a derivative, retain this NOTICE and the LICENSE file. The SKILL.md `license: MIT` field must not be removed.

## Third-party components

LumenPDF depends on the following third-party software. It does not redistribute any of them; each is installed separately by the user.

| Component | Role | License |
|---|---|---|
| [PyMuPDF](https://pymupdf.readthedocs.io/) (`pymupdf`) | PDF parsing, text extraction, page rendering | GNU AGPL-3.0 or Artifex commercial license |
| [Pillow](https://python-pillow.org/) (`pillow`) | Image drawing for OCR-mode annotation exhibits | MIT-CMU |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | OCR of image-based pages; TSV word coordinates for annotation | Apache-2.0 |

Note on PyMuPDF: it is dual-licensed AGPL-3.0 / commercial. LumenPDF links to it as an unmodified installed dependency. Organizations that cannot accept AGPL obligations should either procure the Artifex commercial license or run PyMuPDF in a way that satisfies AGPL section 13 (e.g., by publishing source of any combined work). See https://pymupdf.readthedocs.io/en/latest/about.html for licensing details.

These components remain under their respective licenses and are not covered by LumenPDF's MIT license.
