import re
from backend.models import Publication

def normaliser_date(date_str):
    mois_fr = {
        'janvier': '01', 'février': '02', 'fevrier': '02', 'mars': '03', 'avril': '04',
        'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08', 'aout': '08',
        'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12', 'decembre': '12'
    }
    match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', date_str, re.IGNORECASE)
    if match:
        jour, mois, annee = match.groups()
        mois_num = mois_fr.get(mois.lower(), '01')
        return f"{annee}-{mois_num}-{int(jour):02d}"
    return None

def get_or_create_publication(texte, filepath):
    pub_num_match = re.search(r'N[°ºo] ?(\d+)', texte)
    pub_num = pub_num_match.group(1) if pub_num_match else os.path.basename(filepath).split('-')[1]
    pub_date_match = re.search(r'(\d{1,2} [a-zéû]+ \d{4})', texte, re.IGNORECASE)
    pub_date = normaliser_date(pub_date_match.group(1)) if pub_date_match else datetime.today().strftime("%Y-%m-%d")
    publication, _ = Publication.objects.get_or_create(
        numero=pub_num,
        defaults={
            "titre": "Quotidien de la DGCMEF",
            "date_publication": pub_date,
            "source": "DGCMEF",
            "url": "",
        }
    )
    return publication
def extract_publication(texte, filepath):
    pub_num_match = re.search(r'N[°ºo] ?(\d+)', texte)
    pub_num = pub_num_match.group(1) if pub_num_match else filepath.split('-')[1]
    pub_date_match = re.search(r'(\d{1,2} [a-zéû]+ \d{4})', texte, re.IGNORECASE)
    pub_date = normaliser_date(pub_date_match.group(1)) if pub_date_match else None
    publication, _ = Publication.objects.get_or_create(
        numero=pub_num,
        defaults={
            "titre": "Quotidien de la DGCMEF",
            "date_publication": pub_date,
            "source": "DGCMEF",
            "url": "",
        }
    )
    return publication, pub_date
