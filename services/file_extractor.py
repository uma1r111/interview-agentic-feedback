import io
import logging
from typing import Tuple

logger = logging.getLogger("FileExtractorService")

# Allowed MIME types per document category
TRANSCRIPT_ALLOWED_TYPES = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",                                                         # .doc (legacy)
    "application/octet-stream",                                                   # fallback binary
}

CV_ALLOWED_TYPES = {
    "application/pdf",
    "application/octet-stream",
}

MCQ_ALLOWED_TYPES = {
    "application/json",
    "text/plain",
    "application/octet-stream",
}


class FileExtractorService:
    """
    Universal text extractor for candidate document uploads.

    Supported formats:
      - .txt  (plain text, any encoding attempted)
      - .pdf  (pdfplumber — same engine used by PDFExtractorService)
      - .docx (python-docx — paragraph-level extraction)

    The extractor selects the correct strategy based on the file's
    content_type header AND the filename extension as a fallback,
    since browsers sometimes send 'application/octet-stream' for
    all binary uploads.
    """

    def extract(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """
        Extracts plain text from an uploaded document.

        Args:
            file_bytes:   Raw bytes of the uploaded file.
            filename:     Original filename (used to infer type by extension).
            content_type: MIME type reported by the browser. May be None when
                          called internally (e.g. from the evaluate endpoint).

        Returns:
            Extracted plain-text string.

        Raises:
            ValueError: If the format is unsupported or extraction produces no text.
        """
        # Normalize None values — callers may pass None when content_type is unknown
        content_type = content_type or ""
        filename = filename or ""

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Route to the correct extractor
        if content_type == "application/pdf" or ext == "pdf":
            return self._extract_pdf(file_bytes, filename)

        if (
            content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or content_type == "application/msword"
            or ext == "docx"
            or ext == "doc"
        ):
            return self._extract_docx(file_bytes, filename)

        if content_type == "text/plain" or ext == "txt":
            return self._extract_txt(file_bytes, filename)

        # Fallback: try extension when browser sends 'application/octet-stream'
        if content_type == "application/octet-stream":
            if ext == "pdf":
                return self._extract_pdf(file_bytes, filename)
            if ext in ("docx", "doc"):
                return self._extract_docx(file_bytes, filename)
            if ext == "txt":
                return self._extract_txt(file_bytes, filename)

        raise ValueError(
            f"Unsupported file format '{content_type}' (extension: '.{ext}'). "
            f"Accepted formats: PDF, TXT, DOCX."
        )

    # ------------------------------------------------------------------
    # Private extraction strategies
    # ------------------------------------------------------------------

    def _extract_txt(self, file_bytes: bytes, filename: str) -> str:
        """Decodes a plain-text file, trying UTF-8 first then latin-1."""
        logger.info(f"Extracting TXT: {filename} ({len(file_bytes)} bytes)")
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                text = file_bytes.decode(encoding).strip()
                if text:
                    logger.info(f"TXT decoded with {encoding}: {len(text)} chars")
                    return text
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode '{filename}' as plain text.")

    def _extract_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Extracts text from a PDF using pdfplumber (multi-page support)."""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")

        logger.info(f"Extracting PDF: {filename} ({len(file_bytes)} bytes)")
        text_blocks = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            logger.info(f"PDF pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_blocks.append(page_text.strip())
                else:
                    logger.warning(f"Page {i+1}: no extractable text (image-only?).")

        if not text_blocks:
            raise ValueError(
                f"PDF '{filename}' yielded no text. "
                f"It may be image-only, password-protected, or corrupted."
            )

        full_text = "\n\n".join(text_blocks)
        logger.info(f"PDF extraction complete: {len(full_text)} chars from {filename}")
        return full_text

    def _extract_docx(self, file_bytes: bytes, filename: str) -> str:
        """Extracts text from a .docx Word document using python-docx."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is not installed. Run: pip install python-docx")

        logger.info(f"Extracting DOCX: {filename} ({len(file_bytes)} bytes)")
        doc = Document(io.BytesIO(file_bytes))

        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise ValueError(
                f"DOCX '{filename}' yielded no text. "
                f"The document may be empty or contain only images/tables."
            )

        full_text = "\n\n".join(paragraphs)
        logger.info(f"DOCX extraction complete: {len(full_text)} chars from {filename}")
        return full_text
