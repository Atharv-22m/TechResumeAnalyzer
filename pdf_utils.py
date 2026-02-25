from pypdf import PdfReader

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()