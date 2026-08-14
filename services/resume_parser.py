"""
services/resume_parser.py
--------------------------
Extracts raw text from an uploaded PDF resume using pdfplumber.

Flow (Section 7 of spec):
    PDF -> pdfplumber -> extracted text -> stored in DB -> sent to NLP/LLM pipeline

The extraction never raises an unhandled exception to the caller; instead it
returns a (text, error_message) tuple so the Flask route can decide how to
respond without crashing the app.
"""

import pdfplumber


def extract_text_from_pdf(file_path):
    """
    Extract text from every page of a PDF.

    Returns:
        (text: str, error: str | None)
    """
    try:
        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                return "", "The uploaded PDF has no pages."
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                pages_text.append(page_text)
        full_text = "\n".join(pages_text).strip()

        if not full_text:
            return "", (
                "No readable text could be extracted from this PDF. "
                "It may be a scanned image without a text layer."
            )
        return full_text, None

    except Exception as exc:  # noqa: BLE001 - we intentionally catch everything here
        return "", f"Could not read this PDF file: {exc}"
