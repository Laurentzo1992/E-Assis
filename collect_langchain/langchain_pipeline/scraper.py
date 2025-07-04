import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, unquote

def download_pdfs(url, download_folder):
    os.makedirs(download_folder, exist_ok=True)  # Crée le dossier s’il n’existe pas
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    pdf_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].lower().endswith('.pdf')]
    print(f"Found {len(pdf_links)} PDF links.")
    for href in pdf_links:
        pdf_url = urljoin(url, href)
        pdf_url = unquote(pdf_url)  # Décode les caractères spéciaux dans l’URL
        filename = os.path.join(download_folder, os.path.basename(href))
        if os.path.exists(filename):
            print(f"{filename} already exists, skipping.")
            continue
        try:
            print(f"Downloading {pdf_url} to {filename}")
            r = requests.get(pdf_url)
            r.raise_for_status()
            with open(filename, 'wb') as f:
                f.write(r.content)
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] Failed to download {pdf_url}: {e}")
            continue

if __name__ == "__main__":
    site_url = "http://www.dgcmef.gov.bf/"  # Remplace par l’URL réelle
    download_folder = "./collect_langchain/downloaded_pdfs"
    download_pdfs(site_url, download_folder)
