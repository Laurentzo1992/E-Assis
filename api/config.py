from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://eassis:eassis@localhost:5432/eassis"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_lifetime_minutes: int = 5
    refresh_token_lifetime_days: int = 1

    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_use_tls: bool = True
    email_host_user: str = ""
    email_host_password: str = ""
    default_from_email: str = ""

    google_client_id: str = ""

    # Domaine du frontend React - sert a construire les liens d'activation/reset envoyes par email
    frontend_domain: str = "http://localhost:3000"

    activation_token_lifetime_minutes: int = 15

    # Alertes WhatsApp (Meta Cloud API) - voir api/whatsapp_client.py. whatsapp_template_name doit
    # correspondre a un modele deja approuve par Meta (aucun texte libre pour un message
    # "business-initiated" hors fenetre des 24h) ; whatsapp_min_match_score = seuil de similarite
    # Qdrant en dessous duquel une entreprise n'est pas alertee (cf. api/scripts/match_and_alert.py).
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v20.0"
    whatsapp_template_name: str = "nouvelle_opportunite_marche"
    whatsapp_template_language: str = "fr"
    whatsapp_default_country_code: str = "226"
    whatsapp_min_match_score: float = 0.35


settings = Settings()
