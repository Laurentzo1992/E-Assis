"""Envoi de messages WhatsApp via Meta Cloud API.

Un message "business-initiated" (nous contactons l'entreprise en premier, pas une reponse a un
message recu dans les 24h) DOIT utiliser un modele de message pre-approuve par Meta - le texte
libre est refuse par l'API dans ce cas. `send_whatsapp_template` ne prend donc que le nom d'un
modele deja approuve et les valeurs de ses variables, jamais un corps de message arbitraire.
"""

import logging
import re

import requests

from api.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com"


class WhatsAppSendError(RuntimeError):
    """Levee quand l'API Meta refuse l'envoi (identifiants invalides, modele non approuve,
    numero invalide...)."""


def normalize_e164(telephone: str) -> str:
    """Normalise un numero local (ex. '70 12 34 56') en E.164 (+22670123456), indicatif Burkina
    Faso par defaut si absent. Ne devine rien au-dela de ca : un numero deja international
    (commence par '00' ou contient deja l'indicatif) est respecte tel quel."""
    digits = re.sub(r"\D", "", telephone)
    if digits.startswith("00"):
        digits = digits[2:]
    elif not digits.startswith(settings.whatsapp_default_country_code):
        digits = settings.whatsapp_default_country_code + digits
    return f"+{digits}"


def send_whatsapp_template(to: str, parameters: list[str]) -> dict:
    """Envoie `settings.whatsapp_template_name` a `to`, avec `parameters` dans l'ordre des
    variables du modele (ex. [objet_resume, organisme]). Leve `WhatsAppSendError` si l'API refuse
    l'envoi (n'attrape pas les erreurs reseau transitoires - a la charge de l'appelant)."""
    url = f"{GRAPH_API_BASE}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_e164(to),
        "type": "template",
        "template": {
            "name": settings.whatsapp_template_name,
            "language": {"code": settings.whatsapp_template_language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in parameters]}
            ],
        },
    }

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise WhatsAppSendError(f"Envoi WhatsApp echoue ({response.status_code}) : {response.text}")

    logger.info("Message WhatsApp envoye a %s (modele=%s)", to, settings.whatsapp_template_name)
    return response.json()
