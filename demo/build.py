#!/usr/bin/env python3
"""Build the LumenPDF demo from the same PDF the Slipsheet demo uses.

Everything the demo page shows is produced here by the real scripts, so the
demo can be rebuilt and checked rather than taken on faith:

  tracemonkey.pdf         Mozilla's PDF.js sample paper (also Slipsheet's)
  tracemonkey.md          ocr_pdf.py transcript, one method comment per page
  tracemonkey.prov.json   ocr_pdf.py provenance
  exhibits/               annotate_pdf.py exhibit PNG + provenance JSON
  exhibit.pdf             the exhibit PNG wrapped as a PDF, so Slipsheet can
                          display it

Absolute paths in the outputs are trimmed to this folder before publishing;
nothing else in them is changed.

Usage:
  python3 demo/build.py      (needs pymupdf and pillow)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pymupdf

DEMO = Path(__file__).resolve().parent
SCRIPTS = DEMO.parent / "scripts"
SOURCE = "tracemonkey.pdf"

# The Abstract wraps across lines with hyphenated words and fi/fl ligatures,
# so it is anchored by clean phrases spread through the paragraph. annotate_pdf
# pools their hits into one box around the passage.
SPEC = [
    {
        "page": 1,
        "kind": "pass",
        "label": "PASS EVIDENCE: Abstract states the method and the measured result (10x speedups)",
        "phrases": [
            "Abstract",
            "Since no concrete type information is available, traditional compilers need to emit generic code that can handle all possible type combinations at runtime",
            "generates machine code on the",
            "method provides cheap inter-procedural type specialization",
            "we have measured speedups of 10x and more for certain benchmark programs",
        ],
        "filename": "tracemonkey_EX1_abstract.png",
    },
]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True, cwd=DEMO)


def wrap_exhibit() -> None:
    out = pymupdf.open()
    for item in SPEC:
        png = DEMO / "exhibits" / item["filename"]
        with pymupdf.open(png) as img:
            rect = img[0].rect
        out.new_page(width=rect.width, height=rect.height).insert_image(rect, filename=str(png))
    out.set_metadata({"title": "LumenPDF demo exhibit: tracemonkey abstract"})
    out.save(DEMO / "exhibit.pdf", garbage=4, deflate=True)


def trim_paths(path: Path) -> None:
    path.write_text(path.read_text(encoding="utf-8").replace(str(DEMO) + "/", ""), encoding="utf-8")


def main() -> None:
    run(str(SCRIPTS / "ocr_pdf.py"), SOURCE, "tracemonkey.md", "--provenance")
    (DEMO / "spec.json").write_text(json.dumps(SPEC, indent=2) + "\n", encoding="utf-8")
    run(str(SCRIPTS / "annotate_pdf.py"), SOURCE, "--spec", "spec.json", "--outdir", "exhibits", "--provenance")
    wrap_exhibit()
    for p in ("tracemonkey.md", "tracemonkey.prov.json", "exhibits/tracemonkey_annotations.prov.json"):
        trim_paths(DEMO / p)


if __name__ == "__main__":
    main()
