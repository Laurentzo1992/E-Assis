import pdfplumber

def extract_text_from_pdf(pdf_path, page_number=0):
    with pdfplumber.open(pdf_path) as pdf:
        if page_number < 0 or page_number >= len(pdf.pages):
            raise IndexError(f"Page {page_number} out of range for {pdf_path}")
        return pdf.pages[page_number].extract_text()
