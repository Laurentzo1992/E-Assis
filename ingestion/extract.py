"""Extraction du texte d'un PDF, page par page.
Les bulletins DGCMEF sont en texte natif sur l'ecrasante majorite des pages, mais melangent
ponctuellement des pages scannees (annexes, cachets, signatures) : sans fallback, ces pages
resteraient totalement invisibles. En cas de texte natif quasi-vide, un fallback leger
base sur docTr (python-doctr) est applique localement sans conteneur lourd externe.
"""

import logging
import re
from pathlib import Path

import fitz

from ingestion import config

logger = logging.getLogger(__name__)

_doctr_predictor = None


def _get_doctr_predictor():
    global _doctr_predictor
    if _doctr_predictor is None:
        try:
            from doctr.models import ocr_predictor
            _doctr_predictor = ocr_predictor(pretrained=True, assume_straight_pages=True)
        except Exception as exc:
            logger.warning("Initialisation de python-doctr impossible : %s", exc)
            _doctr_predictor = False
    return _doctr_predictor if _doctr_predictor is not False else None


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
    predictor = _get_doctr_predictor()
    if predictor is None:
        return None
    try:
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        from doctr.io import DocumentFile

        doc = DocumentFile.from_images([png_bytes])
        result = predictor(doc)

        text_blocks = []
        for page_res in result.pages:
            for block in page_res.blocks:
                block_lines = []
                for line in block.lines:
                    line_words = [word.value for word in line.words]
                    if line_words:
                        block_lines.append(" ".join(line_words))
                if block_lines:
                    text_blocks.append("\n".join(block_lines))
        return "\n\n".join(text_blocks)
    except Exception as exc:
        logger.warning("Erreur OCR docTr sur la page : %s", exc)
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
