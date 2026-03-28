# PDF to Markdown Converter

**[English](#english) | [中文](#中文)**

---

<a id="english"></a>

## English

Convert scanned PDFs to Markdown with OCR text extraction. Tables and figures are preserved as original cropped images. Supports generating TTS-friendly PDFs in light/dark mode.

### Requirements

- Python 3.10+
- GPU (recommended, CUDA support)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install marker-pdf fpdf2
```

### Usage

#### 1. PDF to Markdown

**Single conversion (specify page range):**

```bash
python pdf_to_md.py <input.pdf> <page_range> <output_dir>

# Example: convert pages 100-110
python pdf_to_md.py book.pdf "100-110" ./output
```

**Full book batch conversion:**

```bash
python pdf_to_md_batch.py <input.pdf> <output_dir>

# Example
python pdf_to_md_batch.py book.pdf ./output
```

Processes 50 pages per batch with automatic progress saving. Safe to interrupt.

#### 2. Markdown to PDF

```bash
python md_to_pdf.py <input.md> [output.pdf]

# Dark mode
python md_to_pdf.py <input.md> --dark
```

### Output Structure

```
output_dir/
├── output.md          # Markdown text
├── output.pdf         # Light mode PDF
├── output_dark.pdf    # Dark mode PDF
└── images/            # Cropped tables and figures
    ├── page0_FigureGroup_1.png
    ├── page1_TableGroup_2.png
    └── ...
```

### Features

- **Body text** → OCR text output
- **Tables, figures, captions** → Cropped from original PDF pages, preserving original appearance
- **Misdetected region recovery** → Narrow regions misclassified as images are auto-OCR'd and merged back into text
- **OCR spacing cleanup** → Removes extra spaces between CJK characters
- **Non-breaking terms in parentheses** → e.g. `(Local Area Network, LAN)` won't break across lines
- **No page numbers** → TTS/screen reader friendly
- **Dark mode** → `--dark` flag for dark background PDF

### Tech Stack

- [marker-pdf](https://github.com/datalab-to/marker) — Layout detection + OCR
- [surya-ocr](https://github.com/VikParuchuri/surya) — Text recognition engine
- [fpdf2](https://github.com/py-pdf/fpdf2) — PDF generation
- [pypdfium2](https://github.com/nicegui-dev/pypdfium2) — PDF page rendering & cropping

---

<a id="中文"></a>

## 中文

将扫描版 PDF 转换为 Markdown，表格和图片保留为原始截图，正文通过 OCR 提取为文字。支持将 Markdown 再转为适合朗读的 PDF（亮色/暗色模式）。

### 依赖

- Python 3.10+
- GPU（推荐，CUDA 支持）

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install marker-pdf fpdf2
```

### 使用

#### 1. PDF 转 Markdown

**单次转换（指定页码范围）：**

```bash
python pdf_to_md.py <input.pdf> <page_range> <output_dir>

# 示例：转换第 100-110 页
python pdf_to_md.py book.pdf "100-110" ./output
```

**全书分批转换：**

```bash
python pdf_to_md_batch.py <input.pdf> <output_dir>

# 示例
python pdf_to_md_batch.py book.pdf ./output
```

每批处理 50 页，每批完成后自动保存进度，中断不丢失。

#### 2. Markdown 转 PDF

```bash
python md_to_pdf.py <input.md> [output.pdf]

# 暗色模式
python md_to_pdf.py <input.md> --dark
```

### 输出结构

```
output_dir/
├── output.md          # Markdown 正文
├── output.pdf         # 亮色 PDF
├── output_dark.pdf    # 暗色 PDF
└── images/            # 截取的表格和图片
    ├── page0_FigureGroup_1.png
    ├── page1_TableGroup_2.png
    └── ...
```

### 特性

- **正文** → OCR 文字输出
- **表格、图片、图注** → 从 PDF 原页面截取，保留原始样式
- **窄区域误判修复** → 被布局模型误判为图片的文字自动 OCR 补回并拼接到上文
- **OCR 空格清理** → 去除中文字间的多余空格
- **括号内术语不断行** → 如 `(Local Area Network, LAN)` 不会在中间换行
- **无页码** → 适合 TTS 朗读器使用
- **暗色模式** → `--dark` 参数生成深色背景 PDF

### 技术栈

- [marker-pdf](https://github.com/datalab-to/marker) — 布局检测 + OCR
- [surya-ocr](https://github.com/VikParuchuri/surya) — 文字识别引擎
- [fpdf2](https://github.com/py-pdf/fpdf2) — PDF 生成
- [pypdfium2](https://github.com/nicegui-dev/pypdfium2) — PDF 页面渲染与裁剪
