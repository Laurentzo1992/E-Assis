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


settings = Settings()
