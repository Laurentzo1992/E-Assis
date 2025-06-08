# crewai_pipeline/llm_extractor.py

import requests
import json

from .config import OLLAMA_API_URL, LLM_MODEL

def extract_info_with_llm(text, model=LLM_MODEL):
    """
    Calls the LLM API to extract structured information from a section of text.
    Returns the extracted information as a JSON object, or None if extraction fails.
    """
    prompt = (
        "Voici un extrait d'un bulletin de marchés publics. "
        "Extrais toutes les informations structurées pertinentes (résultats, appels d'offres, lots, etc.) "
        "et retourne-les au format JSON.\n\n" + text
    )
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120  # Increase timeout for long texts
        )
        response.raise_for_status()
        data = response.json()
        if "response" in data:
            return data["response"]
        else:
            print("⚠️ LLM API returned unexpected response:", data)
            return None
    except Exception as e:
        print(f"❌ LLM extraction error: {e}")
        return None

def extract_all_infos(sections):
    """
    Processes all sections, sending each to the LLM for extraction.
    Returns a list of dictionaries with section info and extracted data.
    """
    results = []
    for section in sections:
        print(f"🔎 Extracting info from section: {section['titre']} (pages {section['page_debut']}–{section['page_fin']})")
        info = extract_info_with_llm(section["text"])
        if info is None:
            print(f"⚠️ Skipping section '{section['titre']}' due to LLM extraction error.")
            continue
        # Attempt to parse the LLM output as JSON
        try:
            info_json = json.loads(info)
        except Exception:
            print(f"⚠️ LLM output for section '{section['titre']}' is not valid JSON. Raw output:\n{info}\n")
            info_json = info  # Fallback: return raw string
        results.append({
            "section": section["titre"],
            "page_debut": section["page_debut"],
            "page_fin": section["page_fin"],
            "data": info_json
        })
    return results
