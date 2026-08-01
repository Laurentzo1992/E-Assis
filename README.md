# kbbot

Base de connaissances vectorielle pour les bulletins "Quotidien des marches publics" (DGCMEF
Burkina Faso, PDF texte natif avec pages scannees ponctuelles).

## Stack

- **MinIO** : archive brute des PDF collectes (`docker-compose.yml`)
- **Qdrant** : base vectorielle (`docker-compose.yml`)
- **DeepSeek-OCR** (`vision-ocr/`) : fallback OCR pour les pages sans texte natif exploitable
  (annexes scannees, cachets). Necessite un GPU NVIDIA, service demarre a la demande
  (`--profile gpu`).
- **sentence-transformers** `paraphrase-multilingual-mpnet-base-v2` : embeddings (768 dim),
  local et gratuit.
- **ingestion/** : pipeline Python conteneurise (scraping -> archivage MinIO -> extraction ->
  chunking -> embeddings -> upsert Qdrant).
- **Airflow** (`docker-compose.airflow.yml`, `dags/`) : automatise quotidiennement la decouverte
  de nouveaux bulletins et leur indexation.
- **Postgres + FastAPI** (`api/`) : backend "entreprises" (auth JWT, module Entreprise, marches
  publics) - integre depuis le projet E-Assis (Django/DRF d'origine remplace par FastAPI, meme
  contrat d'API).
- **frontend-2/** : interface React (inscription/connexion/dashboard), integree depuis E-Assis,
  pointe vers l'API sur `http://localhost:8000` (`npm --prefix frontend-2 start`, port 3000).

## Demarrage

```bash
docker compose up -d minio qdrant
docker compose --profile gpu up -d vision-ocr   # optionnel, seulement si des pages sont scannees

# Automatisation (necessite le reseau kbbot_backend cree par la commande ci-dessus) :
docker compose -f docker-compose.airflow.yml build
docker compose -f docker-compose.airflow.yml up -d
# UI Airflow : http://localhost:8081 (identifiants AIRFLOW_ADMIN_USER/PASSWORD du .env)
```

## Indexer un PDF manuellement

```bash
docker compose --profile tools run --rm ingest ingestion.ingest "Quotidien n°4456.pdf"
```

Un re-import du meme fichier remplace ses chunks existants (pas de doublons).

## Automatisation : scraping DGCMEF -> MinIO -> Qdrant

`dags/dag_kbbot_quotidien.py` tourne `@daily` :

1. **`scrape_and_archive`** (`ingestion/scrape_and_upload.py`) - relit la page
   https://www.dgcmef.gov.bf/fr/taxonomy/term/16, repere le bulletin le plus recent (le flux RSS
   du site est casse - un seul item perime de 2020 - donc scraping HTML direct, voir
   `ingestion/scraper.py`) et l'archive dans MinIO sous `pdf/quotidien/{numero}.pdf`. Le test
   d'existence de cette cle dans MinIO garantit qu'on ne retelecharge et ne retraite **jamais**
   un bulletin deja vu, et que les executions sans nouvelle publication (le site ne publie pas
   tous les jours) ne font rien.
2. **`has_new_bulletin`** - court-circuite le DAG si rien de nouveau n'a ete trouve.
3. **`vectorize_bulletin`** - lance l'image `kbbot-ingest` via `DockerOperator` (poids ML tenus
   hors de l'image Airflow) pour indexer le nouveau PDF depuis MinIO dans Qdrant
   (`ingestion/ingest_from_minio.py`).

Verifie en conditions reelles le 2026-08-01 : cycle complet (decouverte -> MinIO -> Qdrant, 445
chunks) execute avec succes via le scheduler Airflow, y compris le court-circuit quand rien de
nouveau n'est publie et le declenchement reel du conteneur Docker de vectorisation.

## Backend entreprises (api/)

```bash
docker compose up -d postgres
docker compose up -d --build api
# Une seule fois, pour charger les donnees existantes (utilisateurs, entreprises, marches) :
docker compose exec api python -m api.scripts.migrate_sqlite_to_postgres  # attend db.sqlite3 a la racine

# UI interactive : http://localhost:8000/docs
```

Reproduit exactement les routes/formats de reponse du backend Django d'origine (auth
register/activation/login/refresh JWT/Google OAuth/reset mot de passe, CRUD `/api/entreprise/*`
scope par proprietaire, CRUD `/api/backend/api/*` pour les marches publics) - voir les docstrings
de `api/routers/`. Mots de passe migres depuis Django (PBKDF2) verifies sans reinitialisation
(`api/security.py`, `passlib` avec le hasher `django_pbkdf2_sha256`).

**A savoir** : les identifiants SMTP Gmail fournis (`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`) ne
sont pas valides pour l'authentification SMTP (`535 BadCredentials` constate en reel) - il faut
un mot de passe d'application Gmail, pas le mot de passe du compte. Le code d'envoi est verifie
fonctionnel (teste avec MailHog).

## Rechercher

```bash
docker compose --profile tools run --rm ingest ingestion.search "acquisition de logiciels ArchiCAD QGIS" --top-k 5
```

## Fonctionnement du chunking

Ce bulletin n'a pas de marqueur structurel fiable pour separer les avis entre eux (les
references "N°2026-xxx/ORG/PRM" apparaissent aussi bien dans les titres que dans le corps). Le
decoupage se fait donc par accumulation de paragraphes sous une taille max
(`CHUNK_MAX_CHARS`, defaut 1000 caracteres, chevauchement `CHUNK_OVERLAP_CHARS`), et chaque chunk
est enrichi avec le dernier titre en MAJUSCULES rencontre (`section_title`, generalement le nom
de l'organisme) ainsi que le numero de page, le numero et la date du bulletin (`doc_number`,
`doc_date`, extraits du nom de fichier + de l'en-tete).

**Limite connue** : cette detection de titre est heuristique (ligne majoritairement en
MAJUSCULES, peu de chiffres) et se trompe parfois sur des pages a forte densite de tableaux
(lignes de classement "N° ENTREPRISE ..." peuvent etre prises a tort pour un titre). Ca n'affecte
pas la recherche elle-meme, seulement la metadonnee `section_title` de citation.

## Variables d'environnement (`.env`, voir `.env.example`)

| Variable | Defaut | Role |
|---|---|---|
| `EMBEDDING_MODEL` | `paraphrase-multilingual-mpnet-base-v2` | Modele d'embeddings |
| `QDRANT_COLLECTION` | `kbbot_documents` | Nom de la collection Qdrant |
| `OCR_MIN_CHARS` | `50` | Seuil de texte natif sous lequel une page bascule sur l'OCR |
| `CHUNK_MAX_CHARS` | `1000` | Taille max d'un chunk |
| `CHUNK_OVERLAP_CHARS` | `150` | Chevauchement entre chunks consecutifs |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | - (requis) | Identifiants MinIO |
| `MINIO_BUCKET` | `kbbot` | Bucket d'archivage des PDF |
| `DGCMEF_TAXONOMY_URL` | page taxonomie DGCMEF | Page source du scraping |
| `AIRFLOW_*` | - (requis) | Voir `.env.example` - DB, admin, fernet/secret key Airflow |
| `POSTGRES_USER` / `PASSWORD` / `DB` | - (requis) | Base du backend `api/` |
| `JWT_SECRET_KEY` | - (requis) | Signature des tokens JWT (`api/security.py`) |
| `FRONTEND_DOMAIN` | `http://localhost:3000` | Base des liens d'activation/reset envoyes par email |
| `EMAIL_HOST_USER` / `PASSWORD` | - (requis) | SMTP - mot de passe d'application pour Gmail |
| `GOOGLE_CLIENT_ID` / `SECRET` | - (requis pour Google OAuth) | Connexion via compte Google |

## Tests

```bash
python -m pytest tests/
```

Les tests de `api/` (`test_auth_flow.py`, `test_entreprise.py`) tournent contre une vraie base
Postgres (`docker compose up -d postgres`, puis `DATABASE_URL` pointant dessus) - pas de mock DB.
