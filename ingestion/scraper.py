"""Decouverte des bulletins "Quotidien" sur le site DGCMEF (marches publics du Burkina Faso).

Le flux RSS du site (/fr/taxonomy/term/16/feed) est casse : il ne contient qu'un seul item
perime datant de 2020, verifie en reel le 2026-08-01, alors que la page HTML de la meme
taxonomie liste correctement les bulletins courants. On scrape donc directement cette page HTML.
"""

import re

import requests

from ingestion import config

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Verifie en reel le 2026-08-01 sur https://www.dgcmef.gov.bf/fr/taxonomy/term/16 : chaque ligne
# du tableau a un lien direct vers le PDF ("type=\"application/pdf\"") juste avant son nom de
# fichier "Quotidien n°XXXX.pdf" (casse de la casse du "n"/"N" variable selon les publications).
PDF_LINK_PATTERN = re.compile(
    r'href="(http://www\.dgcmef\.gov\.bf/sites/default/files/[^"]+\.pdf)"'
    r'\s+type="application/pdf">\s*Quotidien\s*[nN]?[°ºo]\s*(\d{3,5})',
    re.IGNORECASE,
)


def list_bulletins() -> list[dict]:
    """Numero + URL de chaque bulletin "Quotidien" liste sur la page taxonomie (les autres
    publications de la meme page, ex. "SITUATION DES MARCHES DE VIVRES...", sont ignorees : elles
    ne correspondent pas au motif "Quotidien n°...")."""
    response = requests.get(config.DGCMEF_TAXONOMY_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    seen: set[str] = set()
    bulletins = []
    for match in PDF_LINK_PATTERN.finditer(response.text):
        numero = match.group(2)
        if numero in seen:
            continue
        seen.add(numero)
        bulletins.append({"numero": numero, "url": match.group(1)})
    return bulletins


def latest_bulletin() -> dict:
    bulletins = list_bulletins()
    if not bulletins:
        raise ValueError("Aucun bulletin 'Quotidien' trouve sur la page taxonomie DGCMEF")
    return max(bulletins, key=lambda b: int(b["numero"]))


def download_pdf(url: str) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=120)
    response.raise_for_status()
    return response.content
