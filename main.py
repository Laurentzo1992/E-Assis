from scrapers.FilesDowloadModule import DocumentScraper
from extracts.pdf_extractor import PDFExtractor


if __name__ == "__main__":
    url = 'https://www.dgcmef.gov.bf/index.php/fr/document'
    download_path = './downloads'

    # Scraping des documents
    scraper = DocumentScraper(url, download_path)
    scraper.scrape()

    # Extraction de texte des PDF
    extractor = PDFExtractor(download_path)
    extractor.extract_all()
