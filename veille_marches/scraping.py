import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re

# ... (La fonction parse_french_date et le dictionnaire FRENCH_MONTHS ne changent pas) ...
FRENCH_MONTHS = {
    'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
}

def parse_french_date(date_string):
    # ... (code inchangé) ...
    match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_string, re.IGNORECASE)
    if not match: return None
    day, month_str, year = match.groups()
    month_num = FRENCH_MONTHS.get(month_str.lower())
    if month_num:
        try: return datetime(int(year), month_num, int(day)).date()
        except ValueError: return None
    return None

def scrape_the_very_latest_publication():
    """
    Scrape le site de la DGCMEF et retourne UNIQUEMENT les informations
    de la publication la plus récente trouvée en haut de la liste.
    Retourne un dictionnaire unique, ou None si rien n'est trouvé.
    """
    base_url = "https://www.dgcmef.gov.bf"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur critique lors de l'accès à {base_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="cols-2")
    
    if not table or not table.find("tbody"):
        print("ERREUR: Impossible de trouver la table des publications.")
        return None

    # On ne prend que la toute première ligne 'tr' du corps du tableau 'tbody'
    first_row = table.find("tbody").find("tr")
    if not first_row:
        print("Aucune ligne de publication trouvée dans le tableau.")
        return None

    title_cell = first_row.find("td", class_="views-field-title")
    file_cell = first_row.find("td", class_="views-field-field-fichier")

    if title_cell and file_cell and title_cell.find('a'):
        title = title_cell.get_text(strip=True)
        pdf_link_tag = file_cell.find("a", type="application/pdf", href=True)

        if pdf_link_tag:
            absolute_url = urljoin(base_url, pdf_link_tag['href'])
            date_pub = parse_french_date(title)
            
            if date_pub is None:
                print(f"Avertissement: Impossible d'extraire la date pour '{title}'.")
                return None
            
            numero_revue = None
            match_num = re.search(r'n°\s*(\d+)', title, re.IGNORECASE)
            if match_num:
                numero_revue = match_num.group(1)

            return {
                'title': title,
                'url': absolute_url,
                'numero_revue': numero_revue,
                'date_publication': date_pub,
            }
            
    return None