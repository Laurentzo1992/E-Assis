"""Decoupage du texte d'une page en chunks, avec rattachement au titre de section.

Ce bulletin n'a aucun marqueur structurel fiable pour separer les avis entre eux : les
references "N°2026-xxx/ORG/PRM" apparaissent aussi bien dans les titres que dans le corps
(financements, lettres de convocation...), donc un decoupage par regex sur ces references
casserait au hasard. Le seul signal stable est la ligne de titre en MAJUSCULES (nom d'organisme
ou type d'avis) qui ouvre chaque avis : on l'utilise comme metadonnee de section plutot que
comme frontiere de decoupage, et on chunke par accumulation de paragraphes sous une taille max.
"""

import re

_HEADING_MIN_LEN = 12
_HEADING_MAX_LEN = 200
_HEADING_MIN_WORDS = 3


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not (_HEADING_MIN_LEN <= len(stripped) <= _HEADING_MAX_LEN):
        return False
    if re.match(r"^N[°ºo]", stripped, re.IGNORECASE):
        return False

    non_space = [c for c in stripped if not c.isspace()]
    if not non_space:
        return False
    letters = [c for c in non_space if c.isalpha()]

    if len(letters) < 8 or len(letters) / len(non_space) < 0.8:
        return False
    if sum(1 for c in letters if c.isupper()) / len(letters) < 0.9:
        return False
    return len(stripped.split()) >= _HEADING_MIN_WORDS


def chunk_page(text: str, max_chars: int, overlap_chars: int) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[dict] = []
    current: list[str] = []
    current_len = 0
    current_heading: str | None = None

    def flush() -> None:
        if current:
            chunks.append({"text": "\n\n".join(current), "section_title": current_heading})

    for para in paragraphs:
        # Le nom d'organisme/titre n'est jamais seul dans son paragraphe - il partage un bloc avec
        # la premiere phrase du corps (pas de ligne blanche entre les deux dans l'extraction PDF).
        # Il faut donc tester chaque ligne du paragraphe, pas le bloc entier.
        for line in para.split("\n"):
            if _is_heading(line):
                current_heading = line.strip()
                break

        if current and current_len + len(para) > max_chars:
            flush()
            if overlap_chars > 0:
                tail = chunks[-1]["text"][-overlap_chars:]
                current = [tail]
                current_len = len(tail)
            else:
                current = []
                current_len = 0

        current.append(para)
        current_len += len(para)

    flush()
    return chunks
