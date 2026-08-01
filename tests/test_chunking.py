from ingestion.chunking import chunk_page

ORGANISME_1 = "SOCIETE NATIONALE D'AMENAGEMENT DES TERRAINS URBAINS (SONATUR)"
ORGANISME_2 = "AUTORITE DE REGULATION DES COMMUNICATIONS ELECTRONIQUES (ARCEP)"


def test_chunk_page_rattache_le_dernier_titre_en_majuscules():
    text = "\n\n".join(
        [
            ORGANISME_1,
            "Demande de prix n°2026-006/DG-SONATUR/PRM pour l'acquisition de logiciels.",
            "Nombre de plis recus : quatre.",
            ORGANISME_2,
            "Fiche de synthese du dossier de demande de prix n°2026-003/DPX/ARCEP/SE/PRM.",
        ]
    )

    chunks = chunk_page(text, max_chars=10_000, overlap_chars=0)

    assert len(chunks) == 1
    assert chunks[0]["section_title"] == ORGANISME_2


def test_chunk_page_decoupe_au_dela_de_max_chars_sans_perdre_le_titre():
    text = "\n\n".join([ORGANISME_1, "Paragraphe A." * 20, "Paragraphe B." * 20])

    chunks = chunk_page(text, max_chars=100, overlap_chars=0)

    assert len(chunks) > 1
    assert all(c["section_title"] == ORGANISME_1 for c in chunks)


def test_titre_colle_a_la_premiere_ligne_du_corps_est_quand_meme_detecte():
    # Cas reel du bulletin : le nom d'organisme et la premiere phrase du corps sont dans le meme
    # paragraphe (pas de ligne blanche entre les deux), separes seulement par un saut de ligne.
    text = f"{ORGANISME_1}\nDemande de prix n°2026-006/DG-SONATUR/PRM pour l'acquisition de logiciels."

    chunks = chunk_page(text, max_chars=10_000, overlap_chars=0)

    assert chunks[0]["section_title"] == ORGANISME_1


def test_ligne_de_reference_nest_pas_traitee_comme_un_titre():
    # Une ligne de reference ("N°2026-xxx/ORG/PRM") a beaucoup de lettres majuscules mais peu de
    # texte reel : sans le filtre alpha_ratio elle serait a tort prise pour un titre de section.
    text = "\n\n".join([ORGANISME_1, "Reference : N°2026-006/DG-SONATUR/PRM", "Suite du texte."])

    chunks = chunk_page(text, max_chars=10_000, overlap_chars=0)

    assert chunks[0]["section_title"] == ORGANISME_1
