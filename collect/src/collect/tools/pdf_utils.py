# collect/src/collect/tools/pdf_utils.py

from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path, page_number=0):
    """
    Extracts text from a single page of a PDF.
    :param pdf_path: Path to the PDF file.
    :param page_number: The page number to extract (0-indexed).
    :return: Extracted text as a string.
    """
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        if page_number < len(reader.pages):
            return reader.pages[page_number].extract_text()
        else:
            raise IndexError(f"Page {page_number} out of range for {pdf_path}")
