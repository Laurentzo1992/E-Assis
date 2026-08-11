from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://eassis:eassis@localhost:5432/eassis"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_lifetime_minutes: int = 5
    refresh_token_lifetime_days: int = 1

    # Site d'administration (sqladmin, monte sous /admin - cf. api/admin.py). Session signee par
    # cookie (Starlette SessionMiddleware), independante des JWT utilises par le reste de l'API -
    # a distinguer de jwt_secret_key. Defaut = jwt_secret_key pour ne pas exiger une variable
    # d'environnement supplementaire en dev ; a definir explicitement en production.
    admin_session_secret_key: str = ""

    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_use_tls: bool = True
    email_host_user: str = ""
    email_host_password: str = ""
    default_from_email: str = ""

    google_client_id: str = ""

    # Domaine du frontend React - sert a construire les liens d'activation/reset envoyes par email
    frontend_domain: str = "http://localhost:3000"

    # Domaine public de CETTE api (distinct de frontend_domain : peuvent etre deux domaines/sous-
    # domaines differents en production) - sert a construire notify_url pour CinetPay, qui doit
    # joindre l'API elle-meme, pas le frontend. En local (aucun hebergement public), CinetPay ne
    # pourra jamais atteindre cette URL - cf. api/payment_client.py.
    api_public_domain: str = "http://localhost:8000"

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

    # MinIO - reutilise ici uniquement pour generer des URL presignees de telechargement des PDF
    # de bulletins (cf. api/minio_client.py), le reste des acces MinIO se fait depuis l'image
    # ingest (ingestion/config.py), pas depuis ce service. minio_public_endpoint est distinct de
    # l'hote interne "minio:9000" du reseau Docker : une URL presignee encode l'hote dans sa
    # signature, elle doit rester resolvable depuis le navigateur qui la suivra (pas seulement
    # depuis les conteneurs du reseau "backend").
    minio_public_endpoint: str = "localhost:9000"
    # False en local (MinIO sans TLS, cf. api/minio_client.py) - DOIT passer a True des que
    # minio_public_endpoint est servi en HTTPS (ex. derriere Caddy en production), sinon les URL
    # presignees restent en http:// et le navigateur bloque leur chargement en mixed-content
    # depuis une page HTTPS (l'apercu PDF du tableau de bord resterait blanc, sans autre erreur
    # visible que dans la console navigateur).
    minio_public_secure: bool = False
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_bucket: str = "kbbot"

    # Abonnement annuel par entreprise (essai gratuit puis payant) - cf. api/models/abonnement.py.
    # Le prix et la duree d'essai vivent en base (table tarifs_abonnement, cf. api/models/tarif.py)
    # plutot qu'ici, pour etre modifiables depuis /admin sans redeploiement. CinetPay choisi comme
    # fournisseur (Mobile Money Orange/Moov + carte, page de paiement hebergee chez eux - jamais de
    # donnee bancaire sur nos serveurs), mais aucune cle reelle n'est configuree : integration
    # ecrite et testee (mocks) mais jamais verifiee contre l'API reelle, en l'absence de compte
    # CinetPay et d'hebergement public (le webhook de confirmation exige une URL joignable depuis
    # Internet).
    cinetpay_api_key: str = ""
    cinetpay_site_id: str = ""
    cinetpay_base_url: str = "https://api-checkout.cinetpay.com/v2"


settings = Settings()
