"""Plain-text extraction from uploaded reference documents (PDF, Word)."""
import os

import pypdf
from docx import Document

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _extract_pdf_text(file_storage) -> str:
    reader = pypdf.PdfReader(file_storage.stream)

    locked_error = ValueError(
        "This PDF is password-protected and can't be opened automatically. "
        "Please upload an unprotected PDF, or remove the password first."
    )

    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
        except Exception as e:
            raise locked_error from e
        if not result:
            # Empty-password decrypt didn't unlock it -- a real password is required.
            raise locked_error

    try:
        pages = [page.extract_text() or "" for page in reader.pages]
    except pypdf.errors.FileNotDecryptedError as e:
        raise locked_error from e
    except pypdf.errors.DependencyError as e:
        raise ValueError(
            "This PDF uses encryption that couldn't be read (missing the 'cryptography' package "
            "on the server). Try re-saving the PDF without security/encryption, or contact the app "
            "maintainer to install the missing dependency."
        ) from e

    return "\n".join(pages)


def _extract_docx_text(file_storage) -> str:
    document = Document(file_storage.stream)
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(file_storage) -> str:
    """Extract plain text from an uploaded .pdf or .docx file.

    Raises ValueError for unsupported file types.
    """
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return _extract_pdf_text(file_storage)
    if ext == ".docx":
        return _extract_docx_text(file_storage)
    raise ValueError(f"Unsupported document type '{ext or filename}'. Please upload a PDF or Word (.docx) file.")
