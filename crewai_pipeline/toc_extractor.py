import pdfplumber
import requests

def extract_toc_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return pdf.pages[1].extract_text()

def parse_toc_with_llm(toc_text, model="deepseek:r1"):
    prompt = (
        "Voici le sommaire d'un bulletin des marchés publics. "
        "Pour chaque section et sous-section, extrais le titre, la page de début et la page de fin. "
        "Retourne la réponse sous forme de liste JSON avec les champs : titre, page_debut, page_fin, sous_sections.\n\n"
        + toc_text
    )
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    data = response.json()
    if "response" in data:
        return data["response"]
    else:
        print("LLM API returned:", data)
        return None

def get_toc_structure(pdf_path):
    toc_text = extract_toc_text(pdf_path)
    toc_structure = parse_toc_with_llm(toc_text)
    return toc_structure
