"""Extraction du texte d'un PDF, page par page.

Les bulletins DGCMEF sont en texte natif sur l'ecrasante majorite des pages, mais melangent
ponctuellement des pages scannees (annexes, cachets, signatures) : sans fallback, ces pages
resteraient totalement invisibles pour la recherche semantique plutot que juste moins bien
indexees. D'ou le bascule vers vision-ocr (DeepSeek-OCR) uniquement quand le texte natif d'une
page est quasi vide.
"""

import re
from pathlib import Path

import fitz  # pymupdf
import httpx

from ingestion import config


def extract_pages(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    try:
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if len(text) < config.OCR_MIN_CHARS:
                text = _ocr_page(page) or text
            pages.append({"page_number": i + 1, "text": text})
        return pages
    finally:
        doc.close()


def _ocr_page(page: "fitz.Page") -> str | None:
    pix = page.get_pixmap(dpi=200)
    png_bytes = pix.tobytes("png")
    try:
        response = httpx.post(
            f"{config.VISION_OCR_URL}/ocr",
            files={"file": ("page.png", png_bytes, "image/png")},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("markdown", "")
    except httpx.HTTPError:
        return None


def parse_doc_metadata(pdf_path: str, pages: list[dict]) -> tuple[str | None, str | None]:
    """Numero et date de parution du bulletin, extraits du nom de fichier + de l'en-tete.

    Les pages contiennent aussi d'anciens numeros de bulletin en en-tete residuel (artefact du
    gabarit source) : on ancre la recherche de la date sur le numero du fichier, seul reperage
    fiable du numero *courant*, plutot que sur le premier "N°..." trouve dans le texte.
    """
    filename = Path(pdf_path).stem
    number_match = re.search(r"(\d{3,5})", filename)
    doc_number = number_match.group(1) if number_match else None
    if doc_number is None:
        return None, None

    haystack = "\n".join(p["text"] for p in pages[:3])
    date_match = re.search(
        rf"N[°ºo]\s?{doc_number}\D{{0,15}}"
        r"((?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*\d{1,2}\s+\w+\s+\d{4})",
        haystack,
        re.IGNORECASE,
    )
    doc_date = date_match.group(1).strip() if date_match else None
    return doc_number, doc_date
