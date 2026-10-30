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

## Reference: all parameters

Every parameter of both scripts is documented here. Anything not listed in
this section does not exist: no hidden flags, no environment-variable
overrides, no config files.

### `scripts/ocr_pdf.py` - text extraction

```
python3 scripts/ocr_pdf.py <input.pdf> [output.md] [options]
```

| Parameter | Type / default | Description |
|---|---|---|
| `input` (positional) | path, required | Input PDF. Must exist and be readable (decrypt encrypted PDFs first). |
| `output` (positional) | path, optional | Output Markdown transcript. Default: `<input-stem>_text.md` next to the input. |
| `--dpi N` | int, `200` | Render DPI for pages sent to tesseract. Raise to 300 for faint scans or small fonts. Ignored when no page needs OCR and `--keep-images` is off. |
| `--range N-M` | string, all pages | 1-indexed inclusive page range. `5` means page 5 only; `5-` and `-9` are accepted by the bash skill but **must be written `5-9` here** (open-ended forms are not parsed). Invalid ranges exit with an error. |
| `--force-ocr` | flag, off | OCR every page in range, including pages with a healthy text layer. |
| `--no-ocr` | flag, off | Never invoke tesseract. Pages below the word threshold are passed through with their (sparse) text and listed as `thin pages` in the report. |
| `--min-words N` | int, `20` | Per-page text-layer word count below which a page is OCR'd instead. Raise (e.g. 50) for PDFs whose text layer is fragmentary. |
| `--lang CODES` | string, `eng` | Tesseract language(s), `+`-joined (e.g. `eng+deu`). Extra languages require the corresponding tesseract language pack. Also recorded in provenance. |
| `--psm N` | int, `6` | Tesseract page segmentation mode passed to OCR calls. `6` = assume a uniform block of text (good for contracts); `3` is the fully automatic default. OCR falls back to psm 3 automatically if the requested mode fails. |
| `--keep-images` | flag, off | Save each rendered page PNG to `<input-dir>/<stem>_pages/page-NN.png`. Applies to OCR'd pages always, and to text-layer pages too (as pixel-level provenance). |
| `--provenance` | flag, off | Write a sidecar JSON next to the output: `<output>.prov.json`. |

Exit codes: `0` success; non-zero on missing dependencies, missing input, or an invalid page range. Progress is printed per page to stderr; the summary report goes to stdout.

Provenance JSON contents (`<output>.prov.json`): `transcript`, `source`,
`extracted_utc`, `pages_total`, `page_range`, `pages_text_layer`, `pages_ocr`,
`min_words_threshold`, `force_ocr`, `no_ocr`, `images_kept`, `output_words`,
`output_bytes`, `tools` (pymupdf and tesseract versions), and per-page records
(`page`, `method`, `pdftotext_words`, `chars`, plus `image`/`dpi`/`ocr_lang`
where applicable).

### `scripts/annotate_pdf.py` - evidence exhibits

```
python3 scripts/annotate_pdf.py <input.pdf> --spec spec.json --outdir DIR [options]
```

| Parameter | Type / default | Description |
|---|---|---|
| `input` (positional) | path, required | Input PDF to annotate. |
| `--spec FILE` | path, required | Annotation spec JSON (fields below). |
| `--outdir DIR` | path, required | Directory for exhibit PNGs (created if missing). Intermediate raw renders are removed after each exhibit is saved. |
| `--dpi N` | int, `120` | Render DPI for exhibit images. 120 is readable for workpapers; raise for print quality. |
| `--lang CODES` | string, `eng` | Tesseract language for OCR-mode pages. |
| `--min-confidence N` | float, `60.0` | Minimum average tesseract word confidence (0-100) for an OCR match to be drawn. Matches below it are listed under `flagged_low_confidence` in the provenance instead. Text-layer matches are never confidence-gated. |
| `--provenance` | flag, off | Write `<stem>_annotations.prov.json` into `--outdir`. |

Annotation spec JSON fields (one object per exhibit):

| Field | Required | Description |
|---|---|---|
| `page` | yes | 1-indexed page number to annotate. |
| `label` | yes | Banner text. Convention: `PASS EVIDENCE: ...`, `FAIL EVIDENCE: ...`, `NOTE: ...`, `CONTRAST: ...`, `EXECUTION: ...`. |
| `kind` | no, default `note` | `pass` (blue banner, red boxes), `fail` (red banner, red boxes), `note` (blue banner, green boxes), `contrast` (blue banner, orange boxes), `execution` (blue banner, blue boxes). |
| `phrases` | no | List of phrases to search for and box. 3-8 distinctive words each works best. All occurrences are matched; hits are clustered into one box per passage. |
| `banner` | no, default `top` | `top` or `bottom`. Use `bottom` when the top of the page has no whitespace. |
| `filename` | no, default `<stem>_EX_p<page>_<kind>.png` | Output exhibit filename inside `--outdir`. |

Mode selection per page: pages with >= 20 words of extractable text are
annotated with pymupdf (`search_for` + merged passage rects); sparser pages
are rendered and annotated from tesseract TSV word coordinates. The provenance
records `mode`, per-phrase `occurrences`/`confidence`, `missed` phrases, and
`flagged_low_confidence` entries. Exhibits with zero matches print a WARNING
to stderr and are still saved (banner only) so the gap is visible.

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
