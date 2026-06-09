"""
Standalone test for PDFExtractorService.
No server or LangGraph needed — run this directly.

Usage:
    python tests/test_pdf_extractor.py <path_to_any_cv.pdf>

Example:
    python tests/test_pdf_extractor.py fixtures/sample_cv.pdf
"""
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf_extractor import PDFExtractorService


def test_pdf_extraction(pdf_path: str):
    print(f"\n{'='*60}")
    print("PDF EXTRACTOR — Isolation Test")
    print(f"{'='*60}")
    print(f"Target file : {pdf_path}")

    # Check the file actually exists
    if not os.path.exists(pdf_path):
        print(f"\n[Error] File not found: {pdf_path}")
        print("Provide a path to a real PDF. Example:")
        print("    python tests/test_pdf_extractor.py C:/Users/you/cv.pdf")
        sys.exit(1)

    # Read the PDF as raw bytes (same as what FastAPI's UploadFile gives us)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"File size   : {len(pdf_bytes):,} bytes")

    # Run the extractor
    extractor = PDFExtractorService()
    try:
        extracted_text = extractor.extract_text(pdf_bytes)

        print(f"\n[SUCCESS] Extraction successful!")
        print(f"Characters extracted : {len(extracted_text):,}")
        print(f"Lines extracted      : {extracted_text.count(chr(10)):,}")
        print(f"\n--- First 500 characters of extracted text ---")
        print(extracted_text[:500])
        print("--- End preview ---")

    except ValueError as e:
        print(f"\n[Error] Extraction failed (empty/image PDF): {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"\n[Error] Missing dependency: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_pdf_extractor.py <path_to_pdf>")
        sys.exit(1)

    test_pdf_extraction(sys.argv[1])
