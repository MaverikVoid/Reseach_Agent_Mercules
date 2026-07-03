import fitz  # PyMuPDF
import logging
from typing import BinaryIO

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_source: str | bytes | BinaryIO) -> str:
    """
    Extract text content from a PDF using PyMuPDF (fitz).
    Accepts file path, raw bytes, or a file-like stream object.
    """
    text_content = []
    try:
        if isinstance(pdf_source, str):
            doc = fitz.open(pdf_source)
        elif isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            # File-like object
            pdf_bytes = pdf_source.read()
            if not pdf_bytes and hasattr(pdf_source, "seek"):
                pdf_source.seek(0)
                pdf_bytes = pdf_source.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for page in doc:
            text_content.append(page.get_text())
        doc.close()
        
        return "\n".join(text_content).strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""
