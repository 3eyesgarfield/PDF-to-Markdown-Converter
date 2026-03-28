"""
PDF to Markdown converter:
- Text blocks → OCR text
- Tables, Figures, Captions → cropped images from PDF pages
"""
import json
import os
import sys
import subprocess
import pypdfium2 as pdfium
from PIL import Image

# ---- Config ----
PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\H610\Desktop\信息系统项目管理师第四版.pdf"
PAGE_RANGE = sys.argv[2] if len(sys.argv) > 2 else None  # e.g. "616-617"
OUTPUT_DIR = sys.argv[3] if len(sys.argv) > 3 else r"C:\Users\H610\Desktop\marker_final"
RENDER_DPI = 200  # DPI for cropping images from PDF
IMAGE_BLOCK_TYPES = {"Table", "TableGroup", "FigureGroup", "Figure", "Picture", "Caption"}
TEXT_BLOCK_TYPES = {"Text", "SectionHeader", "ListGroup", "TextInlineMath"}
NARROW_PICTURE_THRESHOLD = 25  # PDF points, ~8mm. Pictures shorter than this are likely misdetected text

# ---- Step 1: Run marker to get JSON with layout + OCR ----
os.makedirs(OUTPUT_DIR, exist_ok=True)
json_dir = os.path.join(OUTPUT_DIR, "_json_tmp")
os.makedirs(json_dir, exist_ok=True)

cmd = [
    "marker_single", PDF_PATH,
    "--output_dir", json_dir,
    "--force_ocr",
    "--output_format", "json",
]
if PAGE_RANGE:
    cmd += ["--page_range", PAGE_RANGE]

print("Running marker OCR...")
subprocess.run(cmd, check=True)

# Find the JSON output
json_subdir = os.listdir(json_dir)[0]
json_path = None
for f in os.listdir(os.path.join(json_dir, json_subdir)):
    if f.endswith(".json") and not f.endswith("_meta.json"):
        json_path = os.path.join(json_dir, json_subdir, f)
        break

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# ---- Step 2: Open PDF for rendering ----
pdf = pdfium.PdfDocument(PDF_PATH)

# Parse page range
if PAGE_RANGE:
    pages = []
    for part in PAGE_RANGE.split(","):
        if "-" in part:
            a, b = part.split("-")
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
else:
    pages = list(range(len(pdf)))

# ---- Step 3: Process blocks ----
img_dir = os.path.join(OUTPUT_DIR, "images")
os.makedirs(img_dir, exist_ok=True)
md_lines = []
img_counter = 0


def get_block_text(block):
    """Recursively extract text from a block's HTML content."""
    html = block.get("html", "")
    if html:
        # Strip HTML tags to get plain text, but keep structure
        import re
        # For section headers, keep markdown heading
        bt = block.get("block_type", "")
        if bt == "SectionHeader":
            # Extract heading level and text
            m = re.search(r"<h(\d)>(.*?)</h\d>", html, re.DOTALL)
            if m:
                level = int(m.group(1))
                text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                return "#" * level + " " + text
        # For list groups
        if bt == "ListGroup":
            items = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
            result = []
            for item in items:
                clean = re.sub(r"<[^>]+>", "", item).strip()
                if clean:
                    result.append("- " + clean)
            return "\n".join(result)
        # General text
        text = re.sub(r"<[^>]+>", "", html).strip()
        return text
    # Try children
    children = block.get("children", [])
    if children:
        parts = []
        for child in children:
            t = get_block_text(child)
            if t:
                parts.append(t)
        return "\n".join(parts)
    return ""


def get_rec_model():
    """Lazy-load the surya recognition model (shared across calls)."""
    if not hasattr(get_rec_model, "_model"):
        from marker.models import create_model_dict
        models = create_model_dict()
        get_rec_model._model = models["recognition_model"]
    return get_rec_model._model


def ocr_region(page_idx, polygon):
    """OCR a small region from the PDF page using surya."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 5
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max += pad
    y_max += pad

    page = pdf[page_idx]
    scale = RENDER_DPI / 72
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    crop_box = (
        max(0, int(x_min * scale)),
        max(0, int(y_min * scale)),
        min(pil_image.width, int(x_max * scale)),
        min(pil_image.height, int(y_max * scale)),
    )
    cropped = pil_image.crop(crop_box)

    try:
        rec = get_rec_model()
        w, h = cropped.size
        results = rec([cropped], bboxes=[[[0, 0, w, h]]])
        if results and results[0].text_lines:
            return " ".join(line.text for line in results[0].text_lines)
    except Exception as e:
        print(f"  OCR fallback failed: {e}")
    return ""


def crop_block_image(page_idx, polygon, label):
    """Crop a region from the PDF page and save as image."""
    global img_counter
    img_counter += 1

    # Polygon is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] in PDF points
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Add padding
    pad = 5
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max += pad
    y_max += pad

    # Render full page at high DPI
    page = pdf[page_idx]
    scale = RENDER_DPI / 72  # PDF points are 72 DPI
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()

    # Crop
    crop_box = (
        int(x_min * scale),
        int(y_min * scale),
        int(x_max * scale),
        int(y_max * scale),
    )
    # Clamp to image bounds
    crop_box = (
        max(0, crop_box[0]),
        max(0, crop_box[1]),
        min(pil_image.width, crop_box[2]),
        min(pil_image.height, crop_box[3]),
    )
    cropped = pil_image.crop(crop_box)

    filename = f"page{page_idx}_{label}_{img_counter}.png"
    filepath = os.path.join(img_dir, filename)
    cropped.save(filepath, "PNG")
    return f"images/{filename}"


def is_image_block(block_type):
    return block_type in IMAGE_BLOCK_TYPES


def get_combined_polygon(block):
    """Get the bounding polygon that covers this block and all its children."""
    polygons = []
    if block.get("polygon"):
        polygons.append(block["polygon"])
    for child in (block.get("children") or []):
        if child.get("polygon"):
            polygons.append(child["polygon"])
    if not polygons:
        return None
    all_xs = [p[0] for poly in polygons for p in poly]
    all_ys = [p[1] for poly in polygons for p in poly]
    return [
        [min(all_xs), min(all_ys)],
        [max(all_xs), min(all_ys)],
        [max(all_xs), max(all_ys)],
        [min(all_xs), max(all_ys)],
    ]


# Process each page
for page_data in data.get("children", []):
    page_id = page_data.get("id", "")
    # Extract page number from id like "/page/616/Page/81"
    parts = page_id.split("/")
    page_idx = None
    for i, p in enumerate(parts):
        if p == "page" and i + 1 < len(parts):
            page_idx = int(parts[i + 1])
            break
    if page_idx is None:
        continue

    for block in page_data.get("children", []):
        bt = block.get("block_type", "")

        # Skip headers/footers
        if bt in ("PageHeader", "PageFooter"):
            continue

        if is_image_block(bt):
            polygon = get_combined_polygon(block)
            if polygon:
                ys = [p[1] for p in polygon]
                height = max(ys) - min(ys)
                # Narrow "Picture" is likely misdetected text — OCR it and
                # append to the previous text paragraph
                if bt == "Picture" and height < NARROW_PICTURE_THRESHOLD:
                    text = get_block_text(block)
                    if not text:
                        # Marker didn't OCR it; do our own OCR via cropping
                        text = ocr_region(page_idx, polygon)
                    if text:
                        # Merge with previous paragraph if it exists
                        if md_lines and not md_lines[-1].strip().startswith("!"):
                            prev = md_lines[-1].rstrip("\n")
                            md_lines[-1] = prev + text + "\n"
                        else:
                            md_lines.append(f"\n{text}\n")
                    continue
                # Crop from PDF as image (include children like Caption)
                img_path = crop_block_image(page_idx, polygon, bt)
                md_lines.append(f"\n![]({img_path})\n")
        elif bt in TEXT_BLOCK_TYPES or bt == "SectionHeader":
            text = get_block_text(block)
            if text:
                md_lines.append(f"\n{text}\n")
        else:
            # Other block types - try to get text
            text = get_block_text(block)
            if text:
                md_lines.append(f"\n{text}\n")

# ---- Step 4: Write output ----
md_path = os.path.join(OUTPUT_DIR, "output.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"\nDone! Output: {md_path}")
print(f"Images: {img_dir}")
# Cleanup
import shutil
shutil.rmtree(json_dir, ignore_errors=True)
