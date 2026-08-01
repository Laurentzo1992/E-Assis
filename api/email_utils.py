"""Envoi d'email (activation, reset mot de passe) via SMTP, gabarits Jinja2 repris de
templates/emails/ (syntaxe {{ }} directement compatible avec les templates Django existants).

Le template activation_email.html utilise `{{ user_email }}` mais la vue Django d'origine ne
passait que `{'user':..., 'activation_link':...}` au contexte - l'email actuel affiche donc un
champ vide. On passe ici `user_email` explicitement (corrige, cf. plan).
"""

import logging
import smtplib
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


def render_template(template_name: str, context: dict) -> str:
    return _env.get_template(template_name).render(**context)


def send_email(to_email: str, subject: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.default_from_email or settings.email_host_user
    message["To"] = to_email
    message.attach(MIMEText(_strip_tags(html_body), "plain"))
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.email_host, settings.email_port) as server:
        if settings.email_use_tls:
            server.starttls()
        if settings.email_host_user:
            server.login(settings.email_host_user, settings.email_host_password)
        server.sendmail(message["From"], [to_email], message.as_string())


def send_activation_email(user_email: str, activation_link: str) -> None:
    html = render_template("activation_email.html", {"user_email": user_email, "activation_link": activation_link})
    send_email(user_email, "Vérification de votre compte", html)


def send_password_reset_email(user_email: str, user_name: str, reset_link: str) -> None:
    html = render_template(
        "password_reset_email.html", {"user_name": user_name, "reset_link": reset_link}
    )
    send_email(user_email, "Réinitialisation de votre mot de passe", html)
