import os
import re
import os
from backend.extraction.publication import extract_publication

import spacy
from datetime import datetime
from backend.models import Publication, Marche, Lot, Entreprise

# Charger le modèle spaCy français
nlp = spacy.load("fr_core_news_md")

DOSSIER = "./extracts/extracted_text/"  # Dossier contenant tous tes fichiers texte
#/home/ye/E-Assis/extracts/extracted_text/


from backend.extraction.publication import extract_publication
from backend.extraction.appel_offre import extract_appel_offre_blocks, extract_infos_appel_llm, store_appel_offre

def process_all():
    #@DOSSIER = "./documents/"
    for fname in os.listdir(DOSSIER):
        if fname.endswith(".txt"):
            with open(os.path.join(DOSSIER, fname), encoding="utf-8") as f:
                texte = f.read()
            publication, pub_date = extract_publication(texte, fname)
            blocs = extract_appel_offre_blocks(texte)
            if not blocs:
                print(f"[WARN] Aucun bloc Appel d'Offre trouvé dans {fname}")
                continue
            for type_proc_label, bloc in blocs:
                infos = extract_infos_appel_llm(bloc, pub_date, type_proc_label)
                print("EXTRAIT :", infos)  # Pour debug
                if infos["objet"]:
                    store_appel_offre(publication, infos)
            print(f"Appels d'offres importés pour {fname}")

process_all()
