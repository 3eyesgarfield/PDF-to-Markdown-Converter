"""
Convert Markdown (with images) to clean PDF for TTS/朗读.
- No page numbers
- Clean up OCR spacing artifacts
- Chinese font support

Usage: python md_to_pdf.py <input.md> [output.pdf]
"""
import sys
import os
import re
from fpdf import FPDF

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]
DARK_MODE = "--dark" in flags
MD_PATH = args[0] if len(args) > 0 else r"C:\Users\H610\Desktop\marker_final_full\output.md"
PDF_PATH = args[1] if len(args) > 1 else None

if not PDF_PATH:
    suffix = "_dark" if DARK_MODE else ""
    PDF_PATH = os.path.splitext(MD_PATH)[0] + suffix + ".pdf"

BASE_DIR = os.path.dirname(os.path.abspath(MD_PATH))


def clean_text(text):
    """Clean up OCR artifacts for TTS readability."""
    # Remove spaces between CJK characters (OCR artifact)
    text = re.sub(r'([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\s+([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])', r'\1\2', text)
    # Run twice to catch overlapping matches like "质 量 反 馈"
    text = re.sub(r'([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\s+([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])', r'\1\2', text)
    text = re.sub(r'([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\s+([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])', r'\1\2', text)
    # Remove spaces between CJK and punctuation
    text = re.sub(r'([\u4e00-\u9fff])\s+([，。、；：！？）》」』】])', r'\1\2', text)
    text = re.sub(r'([（《「『【])\s+([\u4e00-\u9fff])', r'\1\2', text)
    # Normalize multiple spaces to single
    text = re.sub(r'  +', ' ', text)
    # Replace spaces inside parentheses with non-breaking spaces
    # so English terms like "Local Area Network, LAN" don't break across lines
    NBSP = '\u00a0'
    def nbspify_parens(m):
        return m.group(0).replace(' ', NBSP)
    text = re.sub(r'\([^)]{1,80}\)', nbspify_parens, text)
    text = re.sub(r'（[^）]{1,80}）', nbspify_parens, text)
    return text.strip()


class MarkdownPDF(FPDF):
    def __init__(self, dark_mode=False):
        super().__init__()
        self.dark_mode = dark_mode
        self.add_font("msyh", "", r"C:\Windows\Fonts\msyh.ttc")
        self.add_font("msyh", "B", r"C:\Windows\Fonts\msyhbd.ttc")
        self.set_auto_page_break(auto=True, margin=15)
        # Colors
        if dark_mode:
            self.bg_color = (30, 30, 30)
            self.head_color = (230, 230, 230)
            self.body_color = (200, 200, 200)
        else:
            self.bg_color = None
            self.head_color = (0, 0, 0)
            self.body_color = (51, 51, 51)

    def header(self):
        if self.dark_mode:
            self.set_fill_color(*self.bg_color)
            self.rect(0, 0, self.w, self.h, "F")

    def write_heading(self, level, text):
        sizes = {1: 18, 2: 15, 3: 13, 4: 11}
        size = sizes.get(level, 11)
        self.set_font("msyh", "B", size)
        self.set_text_color(*self.head_color)
        self.ln(3)
        self.multi_cell(0, size * 0.55, clean_text(text))
        self.ln(2)

    def write_paragraph(self, text):
        self.set_font("msyh", "", 10.5)
        self.set_text_color(*self.body_color)
        self.multi_cell(0, 6.5, clean_text(text), align="L")
        self.ln(2)

    def write_list_item(self, text):
        self.set_font("msyh", "", 10.5)
        self.set_text_color(*self.body_color)
        self.cell(6, 6.5, " \u2022 ")
        self.multi_cell(0, 6.5, clean_text(text), align="L")
        self.ln(1)

    def write_image(self, img_path):
        full_path = os.path.join(BASE_DIR, img_path)
        if not os.path.exists(full_path):
            return
        try:
            from PIL import Image as PILImage
            with PILImage.open(full_path) as im:
                img_w, img_h = im.size

            max_w = self.w - self.l_margin - self.r_margin
            max_h = self.h - self.t_margin - 20

            display_w = img_w * 25.4 / 200
            display_h = img_h * 25.4 / 200

            if display_w > max_w:
                ratio = max_w / display_w
                display_w *= ratio
                display_h *= ratio
            if display_h > max_h:
                ratio = max_h / display_h
                display_w *= ratio
                display_h *= ratio

            if self.get_y() + display_h > self.h - 20:
                self.add_page()

            x = self.l_margin + (max_w - display_w) / 2
            self.image(full_path, x=x, y=self.get_y(), w=display_w, h=display_h)
            self.set_y(self.get_y() + display_h + 3)
        except Exception:
            pass


def parse_and_render(md_text, pdf):
    lines = md_text.split("\n")
    i = 0
    total = len(lines)
    last_pct = -1

    while i < total:
        pct = i * 100 // total
        if pct != last_pct and pct % 10 == 0:
            print(f"  Progress: {pct}%")
            last_pct = pct

        line = lines[i].rstrip()

        if not line:
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            pdf.write_heading(level, text)
            i += 1
            continue

        # Image
        m = re.match(r"^!\[.*?\]\((.*?)\)", line)
        if m:
            pdf.write_image(m.group(1))
            i += 1
            continue

        # List item
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            pdf.write_list_item(m.group(1).strip())
            i += 1
            continue

        # Regular paragraph
        para_lines = []
        while i < total and lines[i].strip() and not re.match(r"^(#{1,4}\s|!\[|[-*]\s)", lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            pdf.write_paragraph(" ".join(para_lines))
            continue

        i += 1


with open(MD_PATH, "r", encoding="utf-8") as f:
    md_text = f.read()

print(f"Converting {MD_PATH} -> {PDF_PATH}")

pdf = MarkdownPDF(dark_mode=DARK_MODE)
pdf.add_page()
parse_and_render(md_text, pdf)
pdf.output(PDF_PATH)

print(f"Done! Output: {PDF_PATH}")
