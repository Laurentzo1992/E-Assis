"""Paiement de l'abonnement annuel via CinetPay (agregateur ouest-africain : Orange Money, Moov
Money, Wave, cartes - choisi pour sa couverture Mobile Money au Burkina Faso, largement plus
utilise que la carte bancaire dans ce contexte).

Page de paiement hebergee chez CinetPay (`initier_paiement` renvoie une simple URL de
redirection) : aucune donnee bancaire ne transite jamais par nos serveurs.

Non teste contre l'API reelle (aucun compte CinetPay ni hebergement public configures a ce stade -
leur webhook de confirmation exige une URL joignable depuis Internet, cf. api/routers/paiement.py).
Ecrit contre la forme documentee de leur API v2 ; a verifier des que des identifiants reels et un
hebergement seront disponibles.
"""

import logging

import requests

from api.config import settings

logger = logging.getLogger(__name__)


class PaiementError(RuntimeError):
    """Levee quand CinetPay refuse l'initiation ou la verification d'un paiement."""


def initier_paiement(
    reference: str, montant: str, devise: str, description: str, notify_url: str, return_url: str
) -> str:
    """Cree une transaction chez CinetPay et renvoie l'URL de la page de paiement hebergee vers
    laquelle rediriger l'utilisateur. `reference` doit etre unique (sert de cle d'idempotence cote
    webhook, cf. Paiement.reference)."""
    payload = {
        "apikey": settings.cinetpay_api_key,
        "site_id": settings.cinetpay_site_id,
        "transaction_id": reference,
        "amount": montant,
        "currency": devise,
        "description": description,
        "notify_url": notify_url,
        "return_url": return_url,
        "channels": "ALL",
    }
    try:
        response = requests.post(f"{settings.cinetpay_base_url}/payment", json=payload, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise PaiementError(f"CinetPay injoignable lors de l'initiation du paiement : {exc}") from exc
    if response.status_code >= 400 or data.get("code") != "201":
        raise PaiementError(f"Initiation du paiement CinetPay echouee : {data}")

    logger.info("Paiement CinetPay initie (reference=%s)", reference)
    return data["data"]["payment_url"]


def verifier_transaction(reference: str) -> bool:
    """Interroge directement CinetPay sur le statut reel d'une transaction plutot que de faire
    confiance au seul contenu du webhook (recommandation CinetPay - un appel entrant sur notify_url
    peut etre rejoue ou falsifie, l'appel sortant vers leur API de verification ne peut pas l'etre).
    Renvoie True si le paiement est effectivement accepte."""
    payload = {
        "apikey": settings.cinetpay_api_key,
        "site_id": settings.cinetpay_site_id,
        "transaction_id": reference,
    }
    try:
        response = requests.post(f"{settings.cinetpay_base_url}/payment/check", json=payload, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise PaiementError(f"CinetPay injoignable lors de la verification du paiement : {exc}") from exc
    if response.status_code >= 400:
        raise PaiementError(f"Verification du paiement CinetPay echouee : {data}")

    statut = data.get("data", {}).get("status")
    logger.info("Verification paiement CinetPay (reference=%s) : statut=%s", reference, statut)
    return statut == "ACCEPTED"
