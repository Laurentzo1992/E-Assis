"""Envoi d'email (activation, reset mot de passe) via SMTP, gabarits Jinja2 repris de
templates/emails/ (syntaxe {{ }} directement compatible avec les templates Django existants).

Le template activation_email.html utilise `{{ user_email }}` mais la vue Django d'origine ne
passait que `{'user':..., 'activation_link':...}` au contexte - l'email actuel affiche donc un
champ vide. On passe ici `user_email` explicitement (corrige, cf. plan).
"""

import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api.config import settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape())


class _TextExtractor(HTMLParser):
    """Equivalent minimal de django.utils.html.strip_tags pour le corps texte brut de l'email."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _strip_tags(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "".join(parser.parts).strip()


def render_template(template_name: str, context: dict, langue: str = "fr") -> str:
    """Rend `template_name` (ex. "activation_email.html"). Si `langue != "fr"`, cherche d'abord la
    variante `<nom>.<langue>.html` (ex. "activation_email.en.html") et l'utilise si elle existe -
    sinon repli silencieux sur le fichier francais par defaut (ex. langue "mos" pas encore
    couverte pour un template donne)."""
    if langue != "fr":
        base, _, ext = template_name.rpartition(".")
        candidat = f"{base}.{langue}.{ext}"
        if (TEMPLATES_DIR / candidat).exists():
            template_name = candidat
    return _env.get_template(template_name).render(**context)


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    attachment: tuple[str, bytes] | None = None,
) -> None:
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = settings.default_from_email or settings.email_host_user
    message["To"] = to_email

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(_strip_tags(html_body), "plain"))
    body.attach(MIMEText(html_body, "html"))
    message.attach(body)

    if attachment is not None:
        filename, png_bytes = attachment
        image = MIMEImage(png_bytes, name=filename)
        image["Content-Disposition"] = f'attachment; filename="{filename}"'
        message.attach(image)

    with smtplib.SMTP(settings.email_host, settings.email_port) as server:
        if settings.email_use_tls:
            server.starttls()
        if settings.email_host_user:
            server.login(settings.email_host_user, settings.email_host_password)
        server.sendmail(message["From"], [to_email], message.as_string())


def send_activation_email(user_email: str, activation_link: str, langue: str = "fr") -> None:
    html = render_template(
        "activation_email.html",
        {"user_email": user_email, "activation_link": activation_link},
        langue=langue,
    )
    send_email(user_email, "Vérification de votre compte", html)


def send_password_reset_email(user_email: str, user_name: str, reset_link: str, langue: str = "fr") -> None:
    html = render_template(
        "password_reset_email.html", {"user_name": user_name, "reset_link": reset_link}, langue=langue
    )
    send_email(user_email, "Réinitialisation de votre mot de passe", html)


def send_alert_email(
    user_email: str,
    entreprise_nom: str,
    resume: str,
    organisme: str,
    numero_bulletin: str,
    date_bulletin: str | None = None,
    page_number: int | None = None,
    page_image: bytes | None = None,
    langue: str = "fr",
) -> None:
    """Canal d'alerte interim en attendant l'approbation Meta du modele WhatsApp (cf.
    api/scripts/match_and_alert.py) - meme resume redige par le LLM et meme organisme qu'en
    WhatsApp, mais mis en page pour l'email (pas de contrainte de gabarit Meta) et avec, si
    fourni, la page du bulletin correspondant au match en piece jointe. `resume`/`organisme` sont
    deja dans la langue voulue au moment de l'appel (cf. match_and_alert.py::_envoyer_alerte) -
    `langue` ne pilote ici que le choix du GABARIT HTML (libelles fixes), pas leur contenu."""
    html = render_template(
        "alerte_marche.html",
        {
            "entreprise_nom": entreprise_nom,
            "resume": resume,
            "organisme": organisme,
            "numero_bulletin": numero_bulletin,
            "date_bulletin": date_bulletin,
            "page_number": page_number,
        },
        langue=langue,
    )
    attachment = None
    if page_image is not None:
        attachment = (f"bulletin_{numero_bulletin}_page_{page_number}.png", page_image)
    # Nom de l'entreprise dans le sujet (pas seulement le corps) : un compte gerant plusieurs
    # entreprises recoit un email distinct par entreprise matchee, avec jusque-la un sujet
    # identique pour toutes - impossible a distinguer sans ouvrir chaque message.
    send_email(user_email, f"Nouvelle opportunité de marché public — {entreprise_nom}", html, attachment=attachment)
