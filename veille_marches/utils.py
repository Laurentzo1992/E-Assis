import requests
import json
from django.conf import settings

def call_gemini_api(prompt: str) -> str | None:
    """
    Appelle l'API Google Gemini avec le prompt fourni et retourne la réponse textuelle.

    Cette fonction gère la construction de la requête, l'appel HTTP, et l'extraction sécurisée de la réponse. Elle s'appuie sur lesconfigurations GEMINI_API_KEY et GEMINI_MODEL définies dans settings.py.
    :param prompt: Le prompt complet à envoyer à l'API.
    :return: La réponse textuelle de l'IA, ou None en cas d'erreur.
    """
    # Vérifie que les configurations nécessaires sont présentes dans les settings.
    if not hasattr(settings, 'GEMINI_API_KEY') or not hasattr(settings, 'GEMINI_MODEL'):
        error_msg = "GEMINI_API_KEY et GEMINI_MODEL doivent être configurés dans les settings Django."
        print(error_msg)
        raise ValueError(error_msg)

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        # Ajout de paramètres de sécurité pour éviter les réponses inappropriées
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
        # Configuration de la génération pour favoriser la précision
        "generationConfig": {
            "temperature": 0.2, # Réduit le caractère "créatif" pour des résultats plus déterministes
            "topP": 0.95,
            "topK": 40,
        }
    }

    try:
        # L'appel à l'API est une opération réseau qui peut échouer.
        # Un timeout est essentiel pour éviter que la tâche Celery ne reste bloquée indéfiniment.
        response = requests.post(api_url, headers=headers, json=data, timeout=120) # Timeout de 2 minutes
        
        # Lève une exception si la réponse HTTP est une erreur (4xx ou 5xx).
        response.raise_for_status()
        
        response_data = response.json()
        
        # --- Extraction sécurisée de la réponse ---
        # On utilise .get() pour éviter les KeyErrors si la structure de la réponse change.
        candidates = response_data.get('candidates', [])
        if candidates:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts and 'text' in parts[0]:
                return parts[0]['text']

        # Cas où la réponse est valide mais vide ou bloquée pour des raisons de sécurité.
        print(f"Réponse reçue de Gemini mais sans contenu textuel valide : {response_data}")
        return None

    except requests.exceptions.RequestException as e:
        # Gère les erreurs réseau (timeout, problème DNS, etc.).
        print(f"Erreur de connexion lors de l'appel à l'API Gemini : {e}")
        return None
    except json.JSONDecodeError:
        # Gère le cas où la réponse du serveur n'est pas un JSON valide.
        print(f"Erreur de décodage JSON. Réponse reçue : {response.text}")
        return None
    except Exception as e:
        # Gère toutes les autres erreurs imprévues.
        print(f"Erreur inattendue lors de l'appel à l'API Gemini : {e}")
        return None