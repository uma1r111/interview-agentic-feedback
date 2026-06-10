import io
import logging
from typing import Optional

logger = logging.getLogger("PDFExtractorService")


class PDFExtractorService:
    """
    Single-responsibility service that converts a raw PDF binary blob into a
    clean, normalised plain-text string.

    Sits at the API layer boundary — runs before any pipeline node so that
    every downstream agent only ever sees str, never bytes.
    """

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extracts all readable text from a PDF and returns it as one string.

        Strategy:
          - Open the PDF from an in-memory bytes buffer (no temp files needed).
          - Iterate every page and call pdfplumber's extract_text(), which
            handles multi-column layouts and tables better than pypdf.
          - Collect non-empty page blocks and join them with a double newline
            so section boundaries are preserved for the LLM.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF file.

        Returns:
            A single plain-text string of all extracted content.

        Raises:
            ValueError: If the PDF is empty, corrupted, or yields no text at all.
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber is not installed. "
                "Run: pip install pdfplumber"
            )

        logger.info(f"Starting PDF extraction. Input size: {len(pdf_bytes)} bytes.")

        text_blocks = []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"PDF opened successfully. Total pages: {total_pages}")

            for page_index, page in enumerate(pdf.pages):
                page_text: Optional[str] = page.extract_text()

                if page_text and page_text.strip():
                    text_blocks.append(page_text.strip())
                    logger.debug(f"Page {page_index + 1}/{total_pages}: extracted {len(page_text)} characters.")
                else:
                    logger.warning(f"Page {page_index + 1}/{total_pages}: no extractable text found (may be an image-only page).")

        if not text_blocks:
            raise ValueError(
                "PDF extraction produced no text. The file may be image-only, "
                "password-protected, or corrupted."
            )

        full_text = "\n\n".join(text_blocks)
        logger.info(f"PDF extraction complete. Total characters extracted: {len(full_text)}")
        return full_text
