"""
Convert Markdown (with images) to PDF using fpdf2.
Supports Chinese text rendering.

Usage: python md_to_pdf.py <input.md> [output.pdf]
"""
import sys
import os
import re
from fpdf import FPDF

MD_PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\H610\Desktop\marker_final_full\output.md"
PDF_PATH = sys.argv[2] if len(sys.argv) > 2 else None

if not PDF_PATH:
    PDF_PATH = os.path.splitext(MD_PATH)[0] + ".pdf"

# Base dir for resolving image paths
BASE_DIR = os.path.dirname(os.path.abspath(MD_PATH))


class MarkdownPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Register Chinese font
        self.add_font("msyh", "", r"C:\Windows\Fonts\msyh.ttc", uni=True)
        self.add_font("msyh", "B", r"C:\Windows\Fonts\msyhbd.ttc", uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("msyh", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"{self.page_no()}", align="C")

    def write_heading(self, level, text):
        sizes = {1: 20, 2: 16, 3: 13, 4: 11}
        size = sizes.get(level, 11)
        self.set_font("msyh", "B", size)
        self.set_text_color(0, 0, 0)
        self.ln(4)
        self.multi_cell(0, size * 0.6, text)
        self.ln(2)

    def write_paragraph(self, text):
        self.set_font("msyh", "", 10.5)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 7, text)
        self.ln(2)

    def write_list_item(self, text):
        self.set_font("msyh", "", 10.5)
        self.set_text_color(51, 51, 51)
        x = self.get_x()
        self.cell(8, 7, "  \u2022 ")
        self.multi_cell(0, 7, text)
        self.ln(1)

    def write_image(self, img_path):
        full_path = os.path.join(BASE_DIR, img_path)
        if not os.path.exists(full_path):
            self.write_paragraph(f"[Image not found: {img_path}]")
            return
        try:
            from PIL import Image as PILImage
            with PILImage.open(full_path) as im:
                img_w, img_h = im.size

            # Scale to fit page width (max usable width ~170mm on A4)
            max_w = self.w - self.l_margin - self.r_margin
            max_h = self.h - self.t_margin - 30  # leave room

            # Calculate display size (in mm, assuming 200 DPI source)
            display_w = img_w * 25.4 / 200
            display_h = img_h * 25.4 / 200

            # Scale down if needed
            if display_w > max_w:
                ratio = max_w / display_w
                display_w *= ratio
                display_h *= ratio
            if display_h > max_h:
                ratio = max_h / display_h
                display_w *= ratio
                display_h *= ratio

            # Check if image fits on current page
            if self.get_y() + display_h > self.h - 20:
                self.add_page()

            # Center image
            x = self.l_margin + (max_w - display_w) / 2
            self.image(full_path, x=x, y=self.get_y(), w=display_w, h=display_h)
            self.set_y(self.get_y() + display_h + 3)
        except Exception as e:
            self.write_paragraph(f"[Image error: {e}]")


def parse_and_render(md_text, pdf):
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip empty lines
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
            img_path = m.group(1)
            pdf.write_image(img_path)
            i += 1
            continue

        # List item
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            text = m.group(1).strip()
            pdf.write_list_item(text)
            i += 1
            continue

        # Regular paragraph (collect consecutive non-empty lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|!\[|[-*]\s)", lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            pdf.write_paragraph(" ".join(para_lines))
            continue

        i += 1


# Read markdown
with open(MD_PATH, "r", encoding="utf-8") as f:
    md_text = f.read()

print(f"Converting {MD_PATH} -> {PDF_PATH}")

pdf = MarkdownPDF()
pdf.add_page()
parse_and_render(md_text, pdf)
pdf.output(PDF_PATH)

print(f"Done! Output: {PDF_PATH}")
