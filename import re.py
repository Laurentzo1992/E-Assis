import re
import json
import os
import spacy
import openai
from dotenv import load_dotenv
from backend.models import TypeProcedure, AppelOffre

# Charger variables d'environnement
load_dotenv()
openai.api_key = os.getenv('APIKEy')

# Charger modèle spaCy français
nlp = spacy.load("fr_core_news_md")

def normaliser_date(date_str):
    mois_fr = {
        'janvier': '01', 'février': '02', 'fevrier': '02', 'mars': '03', 'avril': '04',
        'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08', 'aout': '08',
        'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12', 'decembre': '12'
    }
    if not date_str:
        return None
    match = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', date_str)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', date_str, re.IGNORECASE)
    if match:
        jour, mois, annee = match.groups()
        mois_num = mois_fr.get(mois.lower(), '01')
        return f"{annee}-{mois_num}-{int(jour):02d}"
    return None

def extract_appel_offre_blocks(text):
    motifs = [
        r"- Marchés de fournitures et services courants",
        r"- Marchés de travaux",
        r"- Marchés de prestations intellectuelles"
    ]
    positions = []
    for motif in motifs:
        for m in re.finditer(motif, text):
            positions.append((m.start(), motif))
    positions.sort()
    blocs = []
    for i, (start, motif) in enumerate(positions):
        end = positions[i+1][0] if i+1 < len(positions) else len(text)
        bloc = text[start:end].strip()
        type_proc = motif.replace("-", "").strip()
        appels = re.split(r"(?:Avis de demande de prix *:|[\n\r]+n[°ºo] *20\d{2}-)", bloc, flags=re.IGNORECASE)
        for a in appels:
            a = a.strip()
            if len(a) > 50:
                blocs.append((type_proc, a if a.startswith("n°") else "n°" + a))
    return blocs

def extract_infos_appel_regex(texte_bloc, type_proc_label, pub_date):
    lignes = [l.strip() for l in texte_bloc.split('\n') if l.strip()]
    autorite = ""
    if lignes and lignes[0].isupper() and len(lignes[0]) > 5:
        autorite = lignes[0]

    objet = ""
    for l in lignes:
        if re.search(r"(acquisition|travaux|construction|prestation|réalisation|fourniture|réhabilitation)", l, re.IGNORECASE):
            objet = l
            break

    num_match = re.search(r"n[°ºo]\s*([0-9A-Za-z/\-]+)", texte_bloc, re.IGNORECASE)
    numero = num_match.group(1).strip() if num_match else ""

    budget_match = re.search(r"(budget prévisionnel|montant|budget)[^\d]{0,20}([0-9][0-9 \.]{5,})", texte_bloc, re.IGNORECASE)
    montant = None
    if budget_match:
        montant_str = budget_match.group(2).replace(" ", "").replace(".", "")
        try:
            montant = float(montant_str)
        except Exception:
            montant = None

    devise = "XOF"
    devise_match = re.search(r"(FCFA|F CFA|CFA|EURO|EUR|XOF)", texte_bloc, re.IGNORECASE)
    if devise_match:
        devise = devise_match.group(1)

    date_limite_match = re.search(r"(date limite|remise des offres|dépôt des offres|au plus tard le)[^\d]{0,20}([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|[0-9]{1,2}\s+[a-zéû]+\s+[0-9]{4})", texte_bloc, re.IGNORECASE)
    date_limite = normaliser_date(date_limite_match.group(2)) if date_limite_match else None

    type_proc_match = re.search(r"(avis de|type de procédure|procédure)[^\n:]*:?\s*([^\n\.]+)", texte_bloc, re.IGNORECASE)
    type_procedure = type_proc_match.group(2).strip() if type_proc_match else type_proc_label

    # Fallback NLP
    if not autorite or not objet:
        doc = nlp(texte_bloc)
        orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        if not autorite and orgs:
            autorite = orgs[0]
        if not objet:
            for sent in doc.sents:
                if any(word in sent.text.lower() for word in ["acquisition", "travaux", "construction", "fourniture"]):
                    objet = sent.text.strip()
                    break

    return {
        "objet": objet,
        "autorite_contractante": autorite,
        "numero": numero,
        "montant_estime": montant,
        "devise": devise,
        "date_limite": date_limite,
        "type_procedure": type_procedure,
        "date_publication": pub_date
    }

def extract_infos_appel_llm(texte_bloc, pub_date, type_proc_label):
    prompt = f"""
You are an expert assistant specialized in extracting structured data from public procurement notices in Burkina Faso.

Given the following raw text excerpt from an official publication, extract the following fields as JSON:


- objet: The description or object of the procurement.
- numero_avis: The official reference number of the notice.
- montant: The estimated budget or amount (as a number).
- devise: The currency (e.g., FCFA, EUR).
- date_limite: The deadline date for submission in ISO format (YYYY-MM-DD).
- type_procedure: The type of procurement procedure.

Text:
\"\"\"{texte_bloc}\"\"\"

Please respond only with a valid JSON object containing these fields. If a field is not present in the text, use null for its value.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512
        )
        content = response.choices[0].message.content
        try:
            data = json.loads(content)
        except Exception:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
        data["date_publication"] = pub_date
        data["type_procedure"] = data.get("type_procedure", type_proc_label)
        return data
    except Exception as e:
        print(f"Erreur GPT : {e}")
        return extract_infos_appel_regex(texte_bloc, type_proc_label, pub_date)

def store_appel_offre(publication, infos):
    type_proc, _ = TypeProcedure.objects.get_or_create(libelle=infos.get("type_procedure") or "Non précisé")
    AppelOffre.objects.create(
        publication=publication,
        type_procedure=type_proc,
        referenceDossier=infos.get("numero") or infos.get("numero_avis") or "",
        objet=infos.get("objet", ""),
        #autorite_contractante=infos.get("autorite_contractante", ""),
        #montant_estime=infos.get("montant_estime"),
        #devise=infos.get("devise"),
        #date_publication=infos.get("date_publication"),
        dateDepot=infos.get("date_limite"),
        lieuDepot=infos.get("lieuDepot", ""),
        conditionsParticipation=infos.get("conditionsParticipation", ""),
        criteresSelection=infos.get("criteresSelection", ""),
        cautionnement=infos.get("cautionnement"),
        dureeValiditeOffres=infos.get("dureeValiditeOffres", ""),
    )
