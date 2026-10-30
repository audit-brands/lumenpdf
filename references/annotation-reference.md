# PDF Annotation Reference -- Contract Review Workpaper Exhibits

This document describes the PDF annotation approach used in the 2026 Data Privacy audit contract reviews. It is intended as a reference for implementing annotation in an OCR/PDF skill.

## Overview

Two annotation modes, selected by whether the PDF has a text layer:

| Mode | Tool | Use when |
|---|---|---|
| **Text-layer** | pymupdf (`search_for` + `draw_rect` + `insert_textbox`) | PDF has extractable text (most modern contracts) |
| **Image-based (OCR)** | tesseract TSV word coordinates + PIL `ImageDraw` | PDF is scanned/image-based (no text layer) |

## Dependencies

```
pip install pymupdf pillow
# plus the tesseract binary (brew install tesseract on macOS; see SKILL.md
# for per-OS install commands)
```

---

## Mode 1: Text-layer annotation (pymupdf)

### Pattern

1. Open the PDF with `pymupdf.open(path)`
2. Select the page (0-indexed: `doc[page_num - 1]`)
3. For each phrase to highlight, call `page.search_for(phrase)` to get word-level rects
4. **Merge rects into a single passage-level bounding box** (critical: do NOT draw one box per word)
5. Draw a red rectangle around the merged area: `page.draw_rect(merged_rect, color=(1,0,0), width=1.5)`
6. Add a blue banner at the top or bottom with the finding label
7. Render to PNG: `page.get_pixmap(dpi=120).save(output_path)`

### Merging rects into passage boxes

```python
import pymupdf

def merged_rect(page, phrases):
    """Search for multiple phrases, merge all resulting rects into one bounding box."""
    rects = []
    for phrase in phrases:
        for r in page.search_for(phrase):
            rects.append(r)
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return pymupdf.Rect(x0 - 3, y0 - 3, x1 + 3, y1 + 3)
```

**Key rule:** one box per applicable subsection or sentence. Do NOT draw a rect around each individual word -- it becomes unreadable. Group all search hits for a passage into one merged rect.

### Adding the banner

```python
# Place the banner in whitespace (top of page 1, bottom of continuation pages,
# or in the left margin if the top is occupied). Check the page layout first.
rect = pymupdf.Rect(30, 25, 580, 48)  # top banner (adjust for page size)
page.draw_rect(rect, fill=(1, 1, 1), color=(0, 0, 1))  # white fill, blue border
page.insert_textbox(rect, "PASS EVIDENCE: <finding label>", fontsize=9, color=(0, 0, 1))
```

**Banner placement rules:**
- Page 1 of a contract: top banner (y=25-48) usually has whitespace above the title
- Continuation pages (mid-document): use the bottom margin (y=742-770 for letter-size) or the left margin
- If the top-left is blank on a dense page, use Rect(40, 45, 400, 75)
- If the banner overlaps body text, move it to a whitespace area
- Always use `fill=(1,1,1)` (white) so the banner doesn't obscure text behind it

### Banner text conventions

- `PASS EVIDENCE: <what the highlighted text demonstrates>` (blue text, blue border)
- `FAIL EVIDENCE: <what the highlighted text demonstrates>` (red text, blue border)
- `NOTE: <contextual observation>` (blue text, blue border)
- `CONTRAST: <comparison with another document>` (blue text, blue border)

### Rendering

```python
page.get_pixmap(dpi=120).save(output_path)  # 120 dpi is sufficient for readability
```

---

## Mode 2: Image-based PDF annotation (OCR + PIL)

For scanned/image-based PDFs with no text layer, use tesseract's TSV output to get word bounding-box coordinates, then match phrases and draw rectangles with PIL.

### Pattern

1. Render the PDF page to PNG with `pdftoppm` (or extract with pymupdf)
2. Run tesseract with TSV output: `tesseract image.png stdout tsv`
3. Parse the TSV to get word-level bounding boxes: `(x, y, width, height, text)` per word
4. Find the target phrase by matching consecutive words in the TSV
5. Compute the bounding rect for the matched phrase
6. Draw a red rectangle with PIL `ImageDraw`
7. Add the banner with PIL

### Code

```python
import subprocess
from PIL import Image, ImageDraw

def annotate_image_page(png_path, phrases, output_path, label):
    """Annotate an image-based PDF page using OCR word coordinates."""
    # Get word-level bounding boxes from tesseract TSV
    result = subprocess.run(['tesseract', png_path, 'stdout', 'tsv'],
                            capture_output=True, text=True)
    boxes = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split('\t')
        if len(parts) >= 12 and parts[11].strip():
            x = int(parts[6]); y = int(parts[7])
            w = int(parts[8]); h = int(parts[9])
            boxes.append((x, y, x + w, y + h, parts[11]))

    img = Image.open(png_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    W, H = img.size

    for phrase in phrases:
        # Normalize the target phrase into a word list
        words = [w.lower().strip('.,;:"()') for w in phrase]
        n = len(words)
        # Sliding window: find consecutive boxes matching the phrase
        for i in range(len(boxes) - n + 1):
            seq = [b[4].lower().strip('.,;:"()') for b in boxes[i:i + n]]
            if seq == words:
                x0 = min(b[0] for b in boxes[i:i + n])
                y0 = min(b[1] for b in boxes[i:i + n])
                x1 = max(b[2] for b in boxes[i:i + n])
                y1 = max(b[3] for b in boxes[i:i + n])
                draw.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4],
                               outline=(255, 0, 0), width=4)
                break  # first match only

    # Banner (top of page, white fill, blue border, red text)
    draw.rectangle([20, 15, W - 20, 55], fill=(255, 255, 255), outline=(0, 0, 255))
    draw.text((30, 25), label, fill=(200, 0, 0))
    img.save(output_path)
```

**Notes:**
- Tesseract TSV columns: `level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text`
- The sliding-window match is case-insensitive and strips punctuation for robustness
- OCR quality affects matching: if the OCR misreads a word, the phrase won't match. Test with short phrases (3-6 words) for reliability
- The image dimensions from PIL will be larger than the PDF points (dpi scaling), so the TSV coordinates (which are in pixel space at the render resolution) map directly

---

## Workflow for creating annotated exhibits

1. **Read the contract** and identify the passages that support (or fail) each determination
2. **Select the pages** containing those passages
3. **Choose the annotation mode** based on whether the PDF has a text layer:
   - Test with `pdftotext -layout <pdf> -` -- if it returns meaningful text, use Mode 1 (pymupdf)
   - If it returns empty or garbage, use Mode 2 (OCR + PIL)
4. **Identify the search phrases** -- short, distinctive phrases (3-8 words) that uniquely identify the passage
5. **Annotate and render** each page
6. **Save annotated exhibits** to `workpapers/<vendor>_exhibits/` with naming convention: `<Vendor>_EX<N>_<description>_annotated.png`
7. **Reference in the workpaper** with source citation (document name, page number, what the red boxes show)

---

## Example: annotated exhibit set for a vendor workpaper

A typical vendor workpaper has 3-5 annotated exhibits, one per determination:

| Exhibit | Page | What's highlighted | Banner |
|---|---|---|---|
| 1 | Contract p.X | The key clause (e.g., no-training, ZDR, term) | PASS/FAIL EVIDENCE: <label> |
| 2 | Contract p.Y | The supporting or contrasting clause | PASS/FAIL EVIDENCE: <label> |
| 3 | Contract p.Z | The gap (e.g., expiration, missing section, absence) | FAIL EVIDENCE: <label> or NOTE: |
| 4 | Execution page | Signatures and dates | EXECUTION: <label> |

Each exhibit is a single PNG with red boxes on the deciding language and a blue banner stating the finding. The workpaper's determinations table references each exhibit by number.

---

## File conventions

- Annotated exhibits: `workpapers/<vendor>_exhibits/<Vendor>_EX<N>_<description>_annotated.png`
- Pre-annotation renders (if needed): `workpapers/<vendor>_exhibits/<Vendor>_<description>-<page>.png` (no "annotated" suffix)
- Banner: always at the top or bottom of the page in whitespace, never overlapping body text

---

## Common pitfalls

1. **Word-level boxes**: `search_for()` returns one rect per match occurrence. If the phrase appears multiple times or spans a line break, you get multiple rects. Always merge into one bounding box per passage.
2. **Banner overlap**: `insert_textbox` renders text at the rect position. If the rect overlaps existing text, the banner text will collide. Check the page layout and place the banner in whitespace.
3. **Image-based PDFs**: `pymupdf.search_for()` returns nothing on image-based pages because there's no text layer. Use the OCR approach (Mode 2) instead.
4. **OCR accuracy**: tesseract may misread words in low-quality scans. Test with short phrases and fall back to manual coordinate placement if OCR matching fails.
5. **Page numbering**: pymupdf uses 0-indexed pages (`doc[0]` = page 1). Contract citations usually use 1-indexed page numbers. Adjust accordingly.
