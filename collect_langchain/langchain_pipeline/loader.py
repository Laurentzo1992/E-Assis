import os
from PyPDF2 import PdfReader

def load_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text())
    return "\n".join(texts)

def load_all_pdfs_text(folder_path):
    pdf_texts = {}
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.pdf'):
            path = os.path.join(folder_path, filename)
            print(f"Loading {filename}")
            pdf_texts[filename] = load_pdf_text(path)
    return pdf_texts
