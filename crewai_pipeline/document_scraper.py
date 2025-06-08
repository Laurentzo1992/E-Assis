import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse

class DocumentScraper:
    def __init__(self, url, download_path='./revues'):
        self.url = url
        self.download_path = download_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; Scraper/1.0; +https://example.com)'
        })
        os.makedirs(self.download_path, exist_ok=True)

    def download_file(self, file_url):
        file_name = os.path.join(self.download_path, os.path.basename(urlparse(file_url).path))
        if not os.path.exists(file_name):
            response = self.session.get(file_url, stream=True)
            if response.status_code == 200:
                with open(file_name, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"Téléchargé : {file_name}")
            else:
                print(f"Erreur ({response.status_code}) : {file_url}")
        else:
            print(f"Déjà existant : {file_name}")

    def scrape(self):
        soup = BeautifulSoup(self.session.get(self.url).content, 'html.parser')
        for item in soup.find_all('a', href=True):
            if any(ext in item['href'].lower() for ext in ['.pdf', '.docx']):
                file_url = urljoin(self.url, item['href'])
                self.download_file(file_url)

# Example usage:
# scraper = DocumentScraper("https://www.dgcmef.gov.bf", "./revues")
# scraper.scrape()
