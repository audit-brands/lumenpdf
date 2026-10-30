# LumenPDF

PDF text extraction and evidence annotation for AI coding agents. Per-page
hybrid OCR (exact text layer where present, tesseract OCR where not), page-marked
Markdown transcripts, annotated PASS/FAIL evidence exhibits, and machine-readable
provenance for every artifact.

Built for audit and contract-review work: every extraction and annotation is
reproducible: per-page method, word counts, tool versions, matched phrases with
OCR confidence, and optional rendered page images.

## Contents

```
SKILL.md                      # agent-facing skill instructions (portable format)
scripts/ocr_pdf.py            # extraction: per-page hybrid, --provenance, --keep-images
scripts/annotate_pdf.py       # annotation: pymupdf text mode + tesseract OCR mode
references/annotation-reference.md   # the annotation methodology (from the
                                     # 2026 Data Privacy audit contract reviews)
install.sh                    # deploy to agent skill directories
```

## Install the skill

```bash
./install.sh          # all detected runtimes (pi: ~/.agents/skills, Claude Code: ~/.claude/skills)
./install.sh claude   # Claude Code only
./install.sh pi       # pi only
./install.sh --uninstall
```

## Runtime dependencies

```bash
pip install pymupdf pillow
```

Plus tesseract (only needed for scanned pages / image-mode annotation):

| OS | Command |
|---|---|
| macOS | `brew install tesseract` |
| Debian/Ubuntu | `sudo apt install tesseract-ocr` |
| Fedora/RHEL | `sudo dnf install tesseract` |
| Windows | `winget install UB-Mannheim.TesseractOCR` |

## Quick start

```bash
# Extract text (hybrid, with full provenance)
python3 scripts/ocr_pdf.py contract.pdf contract.md --provenance --keep-images

# Screen the transcript, then annotate the deciding passages
cat > spec.json <<'EOF'
[{"page": 4, "kind": "pass",
  "label": "PASS EVIDENCE: Provider data protection obligations",
  "phrases": ["Data protection", "Security Requirements"]}]
EOF
python3 scripts/annotate_pdf.py contract.pdf --spec spec.json --outdir exhibits --provenance
```

## Acknowledgments

LumenPDF stands on third-party tools: [PyMuPDF](https://pymupdf.readthedocs.io/)
for PDF parsing and rendering, [Pillow](https://python-pillow.org/) for image
drawing, and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for
optical character recognition. See `NOTICE.md` for component roles and
licensing (PyMuPDF is AGPL-3.0 or commercial - check the note there if your
organization licenses installed dependencies strictly).

The annotation methodology comes from the 2026 Data Privacy audit contract
reviews, contributed by Audit Risk Media, LLC (CC BY 4.0). The extraction
design originates in the bash-based `ocr-pdf` skill.

## License

MIT for the scripts and skill (see `LICENSE`); CC BY 4.0 for the annotation
methodology in `references/annotation-reference.md` (see
`references/annotation-reference.LICENSE`). Attribution requirements are
summarized in `NOTICE.md` - retain LICENSE and NOTICE when redistributing.

## Design notes

- **Cross-platform by construction**: pymupdf/pillow are pure-pip wheels on
  macOS, Linux, and Windows; the only external binary is tesseract. No poppler,
  no coreutils, no WSL required on Windows.
- **Provenance ladder**: page markers → per-page method comments → optional
  page images → provenance JSON. `--provenance` alone is enough for
  machine-checkable lineage; add `--keep-images` when pixel-level verification
  matters.
- **Model-agnostic**: no LLM or decision-model dependency. Classification and
  screening workflows consume the transcript; this skill only handles documents.
- There is an older bash implementation of the extractor (`ocr-pdf` skill,
  macOS/Linux-oriented). LumenPDF is the portable Python line; outputs match
  (per-page methods agree) though pymupdf's text ordering can differ slightly
  from `pdftotext -layout`.
