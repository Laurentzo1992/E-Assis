import os
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

BASE_URL = "https://www.dgcmef.gov.bf"
PDF_DIR = "data/pdfs"
PROCESSED_DIR = "data/processed"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def scrape_pdf_links():
    print("Scraping PDF links...")
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    pdf_links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".pdf"):
            if href.startswith("http"):
                pdf_links.append(href)
            else:
                pdf_links.append(BASE_URL + href)
    print(f"Found {len(pdf_links)} PDF links.")
    return pdf_links

def download_pdfs(pdf_links):
    print("Downloading PDFs...")
    for url in pdf_links:
        filename = os.path.join(PDF_DIR, os.path.basename(url))
        if not os.path.exists(filename):
            print(f"Downloading {url}...")
            r = requests.get(url)
            with open(filename, "wb") as f:
                f.write(r.content)
        else:
            print(f"Already downloaded: {filename}")

def remove_first_last(input_path, output_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    num_pages = len(reader.pages)
    if num_pages <= 2:
        print(f"File {input_path} too short to process.")
        return False
    for i in range(1, num_pages - 1):
        writer.add_page(reader.pages[i])
    with open(output_path, "wb") as out_f:
        writer.write(out_f)
    return True

def split_pdf_pages(input_path, output_dir):
    reader = PdfReader(input_path)
    os.makedirs(output_dir, exist_ok=True)
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        page_path = os.path.join(output_dir, f"page_{i+1}.pdf")
        with open(page_path, "wb") as out_f:
            writer.write(out_f)

def preprocess_pdfs():
    print("Preprocessing PDFs...")
    for pdf_file in os.listdir(PDF_DIR):
        if not pdf_file.endswith(".pdf"):
            continue
        input_path = os.path.join(PDF_DIR, pdf_file)
        processed_pdf_path = os.path.join(PROCESSED_DIR, pdf_file)
        # Remove first and last page
        if remove_first_last(input_path, processed_pdf_path):
            # Split remaining pages
            split_dir = os.path.join(PROCESSED_DIR, pdf_file.replace(".pdf", ""))
            split_pdf_pages(processed_pdf_path, split_dir)
            print(f"Processed and split: {pdf_file}")
        else:
            print(f"Skipped: {pdf_file}")

if __name__ == "__main__":
    pdf_links = scrape_pdf_links()
    download_pdfs(pdf_links)
    preprocess_pdfs()
