from entreprise.models import Domaine

def create_extraction_prompt(notice_text: str) -> str:
    """
    Génère le prompt détaillé pour Gemini, demandant des clés en snake_case
    pour correspondre directement aux modèles Django.
    """
    #  Récupération de tous les domaines disponibles
    domaines_disponibles = list(Domaine.objects.values_list('libelle', flat=True))
    domaines_str = ", ".join([f'"{d}"' for d in domaines_disponibles])
    
    json_schema = """
    {
      "estComplet": true,
      "type_procedure": "string",
      "domaine_identifie": "string | null",
      "marche": {
        "ministere": "string | null",
        "region": "string | null",
        "objet": "string",
        "budget_min": "decimal | null",
        "budget_max": "decimal | null"
      },
      "appel_offre": {
        "date_depot": "YYYY-MM-DD HH:MM:SS | null",
        "reference_dossier": "string | null",
        "lieu_depot": "string | null",
        "cautionnement": "decimal | null",
        "duree_validite_offres": "string | null"
      },
      "resultat": {
        "date_attribution": "YYYY-MM-DD | null",
        "reference_decision": "string | null",
        "nombre_offres_recues": "integer | null",
        "delai_execution": "string | null"
      },
      "lots": [
        {
          "numero_lot": "string | null",
          "description": "string | null",
          "nom_entreprise": "string",
          "montant_propose": "decimal | null",
          "statut": "string",
          "rang": "string | null",
          "motif": "string | null"
        }
      ]
    }
    """

    prompt = f"""
**TÂCHE :** Tu es un assistant expert en analyse de documents administratifs spécialisé dans les marchés publics du Burkina Faso. Ta mission est d'extraire les informations structurées du texte d'une notice de marché public fournie ci-dessous.

**INSTRUCTIONS EN DEUX PHASES :**

**Phase 1 : Évaluation de la Complétude**
- Analyse attentivement si le texte de la notice semble complet. Une notice est considérée **incomplète** si elle se termine brusquement.
- Si le texte est jugé incomplet, ta seule et unique réponse doit être le JSON suivant :
  `{{"estComplet": false, "raison": "La notice semble être coupée."}}`

**Phase 2 : Extraction des Données (si la notice est complète)**
- Si la notice est complète, extrais les informations et retourne-les **exclusivement** sous la forme d'un objet JSON unique et valide.

**IDENTIFICATION DU DOMAINE D'ACTIVITÉ :**
- Analyse l'objet du marché et identifie le domaine d'activité correspondant parmi cette liste EXACTE : [{domaines_str}]
- Le champ `domaine_identifie` doit contenir EXACTEMENT l'un des domaines de la liste ci-dessus, ou `null` si aucun ne correspond
- Base ton choix sur l'objet du marché, les mots-clés techniques, et le type de prestations demandées

**RÈGLES D'EXTRACTION STRICTES :**
1.  **Format des Clés :** Toutes les clés du JSON doivent être en **snake_case** (ex: `type_procedure`, `nom_entreprise`).
2.  **Schéma JSON :** Respecte impérativement le schéma ci-dessous.
3.  **Tableaux de Résultats :** Chaque ligne du tableau des soumissionnaires doit correspondre à un objet dans la liste `"lots"`.
4.  **Champ `statut` :** La valeur doit être l'une des suivantes : `RETENU`, `NON_CONFORME`, `ANORMALEMENT_BASSE`, `REJETE`, `AUTRE`.
5.  **Champs Numériques :** Doivent être des nombres (`decimal` ou `integer`), sans devise ni séparateur de milliers. Utilise `null` si non trouvé.
6.  **Dates :** Utilise le format `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM:SS`.
7.  **Valeurs Nulles :** Utilise `null` pour toute information non présente.

**SCHÉMA JSON DE SORTIE ATTENDU (avec clés en snake_case) :**
```json
{json_schema}
    TEXTE DE LA NOTICE À ANALYSER :
    {notice_text}
    """
    return prompt