"""文档解析：PDF / Word / Excel / MD / TXT + OCR 兜底。

OCR 依赖（pytesseract + poppler）为可选安装，未安装时扫描件给出明确提示——见《未完成清单.txt》。
"""
from pathlib import Path


def parse_file(path: str | Path, file_type: str) -> str:
    ft = (file_type or "").lower().lstrip(".")
    path = str(path)
    if ft == "pdf":
        return _parse_pdf(path)
    if ft in ("docx", "doc"):
        return _parse_docx(path)
    if ft in ("xlsx", "xls"):
        return _parse_xlsx(path)
    if ft in ("md", "txt", "markdown", "csv", "log"):
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    # 未知类型按文本兜底
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def _parse_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        pages.append((p.extract_text() or "").strip())
    text = "\n\n".join(pages).strip()
    if not text:
        # 扫描件：尝试 OCR（可选依赖）
        text = _ocr_pdf(path)
    return text


def _ocr_pdf(path: str) -> str:
    """OCR 兜底：需要 pytesseract + tesseract-ocr-chi-sim + poppler（Docker 镜像内已装）。
    本机未安装时抛出可读提示。"""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pytesseract import Output

        images = convert_from_path(path, dpi=200)
        out = []
        for img in images:
            out.append(pytesseract.image_to_string(img, lang="chi_sim+eng", output=Output.STRING))
        return "\n\n".join(out).strip()
    except ImportError:
        raise RuntimeError(
            "该 PDF 无文字层（扫描件）。OCR 组件未安装：请安装 pytesseract、pdf2image、"
            "tesseract-ocr(-chi-sim) 与 poppler-utils 后重试（Docker 镜像内已内置）。"
        )


def _parse_docx(path: str) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(path)
    parts = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_xlsx(path: str) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"## Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v).strip() for v in row]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def sniff_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in ("pdf", "docx", "xlsx", "md", "txt", "csv"):
        return "docx" if suffix == "doc" else suffix
    if suffix in ("xls",):
        return "xlsx"
    return suffix or "txt"
