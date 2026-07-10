"""
services/processor.py
----------------------
Turns an uploaded file into clean, chunked text that's ready to be
embedded and stored in the vector database.

This file has exactly two public jobs:

    extract_text_from_file()   -> reads a file, returns its raw text
    split_text_into_chunks()   -> splits that text into overlapping pieces

Everything else in here is a small private helper that supports those
two functions, so each piece of logic only does one thing.
"""

import os
from PyPDF2 import PdfReader
from docx import Document


# ============================================================
# PUBLIC FUNCTION: EXTRACT TEXT FROM ANY SUPPORTED FILE
# ============================================================

def extract_text_from_file(file_path):
    """
    Look at the file's extension and call the right helper function
    to read its text. This is the ONLY function app.py needs to call
    for text extraction — it hides which file type is being handled.
    """
    file_extension = get_file_extension(file_path)

    if file_extension == "pdf":
        return extract_text_from_pdf(file_path)

    if file_extension == "docx":
        return extract_text_from_docx(file_path)

    if file_extension == "txt":
        return extract_text_from_txt(file_path)

    # Markdown is plain text — the formatting characters (#, *, etc.) are
    # left in place rather than stripped, since they still carry meaning
    # (headings, emphasis) that's useful context for the AI to read.
    if file_extension == "md":
        return extract_text_from_txt(file_path)

    # If we somehow got a file type we don't support, fail clearly
    # instead of silently returning nothing.
    raise ValueError("Unsupported file type: " + file_extension)


# ============================================================
# PRIVATE HELPER: FIGURE OUT THE FILE EXTENSION
# ============================================================

def get_file_extension(file_path):
    """Return the lowercase file extension without the leading dot."""
    _, extension_with_dot = os.path.splitext(file_path)
    extension = extension_with_dot.replace(".", "").lower()
    return extension


# ============================================================
# PRIVATE HELPER: READ TEXT FROM A PDF FILE
# ============================================================

def extract_text_from_pdf(file_path):
    """
    Read every page of a PDF and join their text together.
    Pages with no extractable text (e.g. scanned images) are skipped.
    """
    reader = PdfReader(file_path)
    all_pages_text = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            all_pages_text.append(page_text)

    full_text = "\n".join(all_pages_text)
    return full_text


# ============================================================
# PRIVATE HELPER: READ TEXT FROM A WORD (.docx) FILE
# ============================================================

def extract_text_from_docx(file_path):
    """Read every paragraph of a Word document and join them together."""
    document = Document(file_path)
    all_paragraphs_text = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip() != "":
            all_paragraphs_text.append(paragraph.text)

    full_text = "\n".join(all_paragraphs_text)
    return full_text


# ============================================================
# PRIVATE HELPER: READ TEXT FROM A PLAIN .txt FILE
# ============================================================

def extract_text_from_txt(file_path):
    """Read a plain text file using UTF-8 encoding."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as text_file:
        full_text = text_file.read()
    return full_text


# ============================================================
# PUBLIC FUNCTION: SPLIT TEXT INTO OVERLAPPING CHUNKS
# ============================================================

def split_text_into_chunks(text, chunk_size=1000, overlap=200):
    """
    Split a long piece of text into smaller overlapping chunks.

    Why overlap? If we cut chunks with hard edges, a sentence that spans
    the cut point loses context. Overlapping the end of one chunk with
    the start of the next keeps that context intact for better retrieval.

    chunk_size and overlap are measured in characters, which keeps this
    function simple and fast (no extra tokenizer library required).
    """
    text = text.strip()

    if text == "":
        return []

    chunks = []
    start_position = 0
    text_length = len(text)

    while start_position < text_length:
        end_position = start_position + chunk_size
        chunk = text[start_position:end_position]
        chunks.append(chunk.strip())

        # Move the window forward, but step back by "overlap" characters
        # so the next chunk shares some text with this one.
        start_position = end_position - overlap

    return chunks