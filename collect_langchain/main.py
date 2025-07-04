import os
from langchain_pipeline.loader import load_pdf_text
from langchain_pipeline.sommaire_extractor import extract_sommaire_structure
from langchain_pipeline.chunker import chunk_document

def get_first_pdf_file(folder_path):
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Le dossier {folder_path} n'existe pas. Veuillez lancer le scraping d'abord.")
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    if not pdf_files:
        raise FileNotFoundError(f"Aucun fichier PDF trouvé dans {folder_path}")
    pdf_files.sort()
    return os.path.join(folder_path, pdf_files[0])

def run_collection(pdf_path):
    print(f"[INFO] Chargement du PDF : {pdf_path}")
    full_text = load_pdf_text(pdf_path)

    print("[INFO] Extraction de la structure du sommaire...")
    sommaire_json_str = extract_sommaire_structure(full_text)
    print(f"[DEBUG] Sommaire JSON brut : {sommaire_json_str}")

    print("[INFO] Découpage du document en chunks...")
    chunks = chunk_document(full_text, sommaire_json_str)

    print(f"[INFO] Nombre de chunks générés : {len(chunks)}")
    for i, chunk in enumerate(chunks, 1):
        print(f"--- Chunk {i} ---")
        print(chunk[:500])  # Affiche un extrait des 500 premiers caractères

if __name__ == "__main__":
    documents_folder = "./langchain_pipeline/collect_langchain/downloaded_pdfs"

    first_pdf = get_first_pdf_file(documents_folder)
    run_collection(first_pdf)
