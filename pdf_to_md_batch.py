"""
PDF to Markdown converter (batch version):
- Processes PDF in batches to avoid memory/timeout issues
- Text blocks -> OCR text
- Tables, Figures, Captions -> cropped images from PDF pages
"""
import json
import os
import sys
import subprocess
import shutil
import pypdfium2 as pdfium
from PIL import Image

# ---- Config ----
PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\H610\Desktop\信息系统项目管理师第四版.pdf"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\H610\Desktop\marker_final_full"
BATCH_SIZE = 50  # pages per batch
RENDER_DPI = 200
IMAGE_BLOCK_TYPES = {"Table", "TableGroup", "FigureGroup", "Figure", "Picture", "Caption"}
TEXT_BLOCK_TYPES = {"Text", "SectionHeader", "ListGroup", "TextInlineMath"}
NARROW_PICTURE_THRESHOLD = 25

os.makedirs(OUTPUT_DIR, exist_ok=True)
img_dir = os.path.join(OUTPUT_DIR, "images")
os.makedirs(img_dir, exist_ok=True)

# Get total pages
pdf = pdfium.PdfDocument(PDF_PATH)
total_pages = len(pdf)
pdf.close()

print(f"Total pages: {total_pages}, batch size: {BATCH_SIZE}")
print(f"Estimated batches: {(total_pages + BATCH_SIZE - 1) // BATCH_SIZE}")

# Lazy-loaded rec model
_rec_model = None

def get_rec_model():
    global _rec_model
    if _rec_model is None:
        from marker.models import create_model_dict
        models = create_model_dict()
        _rec_model = models["recognition_model"]
    return _rec_model


img_counter = 0
all_md_lines = []


def get_block_text(block):
    import re
    html = block.get("html", "")
    if html:
        bt = block.get("block_type", "")
        if bt == "SectionHeader":
            m = re.search(r"<h(\d)>(.*?)</h\d>", html, re.DOTALL)
            if m:
                level = int(m.group(1))
                text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                return "#" * level + " " + text
        if bt == "ListGroup":
            items = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
            result = []
            for item in items:
                clean = re.sub(r"<[^>]+>", "", item).strip()
                if clean:
                    result.append("- " + clean)
            return "\n".join(result)
        text = re.sub(r"<[^>]+>", "", html).strip()
        return text
    children = block.get("children") or []
    if children:
        parts = []
        for child in children:
            t = get_block_text(child)
            if t:
                parts.append(t)
        return "\n".join(parts)
    return ""


def get_combined_polygon(block):
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


def crop_block_image(pdf_doc, page_idx, polygon, label):
    global img_counter
    img_counter += 1
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 5
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max += pad
    y_max += pad
    page = pdf_doc[page_idx]
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
    filename = f"page{page_idx}_{label}_{img_counter}.png"
    filepath = os.path.join(img_dir, filename)
    cropped.save(filepath, "PNG")
    return f"images/{filename}"


def ocr_region(pdf_doc, page_idx, polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 5
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max += pad
    y_max += pad
    page = pdf_doc[page_idx]
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


def process_batch(start_page, end_page):
    """Run marker on a batch of pages and process the JSON output."""
    page_range = f"{start_page}-{end_page}"
    json_dir = os.path.join(OUTPUT_DIR, "_json_tmp")
    if os.path.exists(json_dir):
        shutil.rmtree(json_dir)
    os.makedirs(json_dir)

    cmd = [
        "marker_single", PDF_PATH,
        "--output_dir", json_dir,
        "--force_ocr",
        "--output_format", "json",
        "--page_range", page_range,
    ]

    try:
        subprocess.run(cmd, check=True, timeout=600)
    except Exception as e:
        print(f"  Marker failed for pages {start_page}-{end_page}: {e}")
        return []

    # Find JSON output
    json_path = None
    for subdir in os.listdir(json_dir):
        subdir_path = os.path.join(json_dir, subdir)
        if os.path.isdir(subdir_path):
            for f in os.listdir(subdir_path):
                if f.endswith(".json") and not f.endswith("_meta.json"):
                    json_path = os.path.join(subdir_path, f)
                    break
    if not json_path:
        print(f"  No JSON output for pages {start_page}-{end_page}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    shutil.rmtree(json_dir, ignore_errors=True)

    # Open PDF for cropping
    pdf_doc = pdfium.PdfDocument(PDF_PATH)
    md_lines = []

    for page_data in data.get("children", []):
        page_id = page_data.get("id", "")
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
            if bt in ("PageHeader", "PageFooter"):
                continue

            if bt in IMAGE_BLOCK_TYPES:
                polygon = get_combined_polygon(block)
                if polygon:
                    ys = [p[1] for p in polygon]
                    height = max(ys) - min(ys)
                    if bt == "Picture" and height < NARROW_PICTURE_THRESHOLD:
                        text = get_block_text(block)
                        if not text:
                            text = ocr_region(pdf_doc, page_idx, polygon)
                        if text:
                            if md_lines and not md_lines[-1].strip().startswith("!"):
                                prev = md_lines[-1].rstrip("\n")
                                md_lines[-1] = prev + text + "\n"
                            else:
                                md_lines.append(f"\n{text}\n")
                        continue
                    img_path = crop_block_image(pdf_doc, page_idx, polygon, bt)
                    md_lines.append(f"\n![]({img_path})\n")
            elif bt in TEXT_BLOCK_TYPES or bt == "SectionHeader":
                text = get_block_text(block)
                if text:
                    md_lines.append(f"\n{text}\n")
            else:
                text = get_block_text(block)
                if text:
                    md_lines.append(f"\n{text}\n")

    pdf_doc.close()
    return md_lines


# ---- Main: process in batches ----
import time
start_time = time.time()

for batch_start in range(0, total_pages, BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE - 1, total_pages - 1)
    batch_num = batch_start // BATCH_SIZE + 1
    total_batches = (total_pages + BATCH_SIZE - 1) // BATCH_SIZE
    elapsed = time.time() - start_time

    if batch_num > 1:
        avg_per_batch = elapsed / (batch_num - 1)
        remaining = avg_per_batch * (total_batches - batch_num + 1)
        print(f"\n[Batch {batch_num}/{total_batches}] Pages {batch_start}-{batch_end} "
              f"(elapsed: {elapsed/60:.1f}min, est remaining: {remaining/60:.1f}min)")
    else:
        print(f"\n[Batch {batch_num}/{total_batches}] Pages {batch_start}-{batch_end}")

    batch_lines = process_batch(batch_start, batch_end)
    all_md_lines.extend(batch_lines)

    # Save progress after each batch
    md_path = os.path.join(OUTPUT_DIR, "output.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_md_lines))

total_time = time.time() - start_time
print(f"\nAll done! Total time: {total_time/60:.1f} minutes")
print(f"Output: {os.path.join(OUTPUT_DIR, 'output.md')}")
print(f"Images: {img_dir}")
