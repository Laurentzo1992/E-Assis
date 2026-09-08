# E-Assis - Plateforme d'Intelligence des Marches Publics

Automatisation complete de l'analyse, de l'extraction et de l'alerte pour le Quotidien des marches publics (DGCMEF Burkina Faso).

---

## Architecture et Approche Finale de Traitement

Le traitement d'un bulletin repose sur une stricte separation des responsabilites :

1. Avis d'appels d'offres (Opportunites) :
   - Detection du début des avis de marches : Localisation de la page de debut des avis de marches a travers une expression reguliere appliquee a la page de sommaire avec falback vers un traitement llm en cas d'echec de l'expression reguliere.
   - Decoupage geometrique unitaire : Chaque marche ou avis est isole comme une entite distincte avec son autorite contractante, son objet et sa reference.
   - Classification par Domaine d'Activite : L'IA analyse l'objet du marche et l'associe strictement a l'un des domaines prealablement configures en base de donnees. Si aucun domaine ne correspond avec certitude, la valeur est fixee a null.
   - Alertes ciblees : Les entreprises abonnees a ce domaine recoivent automatiquement les avis correspondants avec la possiblité de naviguer vers ces marches dans la revue.

2. Resultats d'Attribution (Depouillement et REX) :
   - Ciblage par entreprise : Le systeme charge la liste des entreprises clientes enregistrees dans la base de donnees.
   - Recherche deterministe dans le bulletin : Pour chaque entreprise cliente, le moteur parcourt l'ensemble des pages de resultats du bulletin PDF et repere les extraits tabulaires de depouillement ou le nom (ou l'identifiant legal) de l'entreprise apparait.
   - Extraction des extraits pertinents : Seules les deliberations ou lots concernant specifiquement l'entreprise sont isoles.
   - Interpretation chirurgicale par l'IA : L'extrait brut est soumis au LLM avec un prompt structure. L'IA verifie formellement la situation de l'entreprise, qualifie la decision finale (marché gagne ou perdu), identifie les lots remportes avec montants, et extrait precisement le motif d'eviction ou de rejet si l'entreprise n'a pas ete retenue.
   - Notification dedupliquee : L'alerte personnalisee est enregistree en base de donnees et mise a disposition de l'entreprise sur son espace dedie.

3. Orchestration unifiee (process_bulletin.py) :
   - Un script unifie enchaine l'extraction des avis, la recherche des resultats pour les entreprises en base, et la creation de toutes les alertes associees.

---

## Configuration du Moteur LLM (PROD=true vs PROD=false)

Le module llm_service/llm_client.py fournit une passerelle unifiee (call_llm) garantissant rigoureusement les memes prompts, les memes system instructions et les memes structures JSON quel que soit le moteur utilise.

### Option A : Mode Local avec Ollama (PROD=false)

Cette option permet de tester et d'executer l'ensemble du pipeline en local, sans consommation de credits d'API cloud.

Comment l'activer :
Dans votre fichier .env a la racine du projet, configurez les variables suivantes :
```env
PROD=false
LOCAL_LLM_MODEL=llama3.1:8b
OLLAMA_HOST=http://host.docker.internal:11434
```

Explications et fonctionnement :
- La variable PROD=false indique au code de router les appels vers Ollama.
- Sur votre machine hote, assurez-vous qu'Ollama est installe et demarre avec le modele Llama 3.1 : lancez la commande `ollama run llama3.1:8b`.
- L'adresse http://host.docker.internal:11434 est requise car l'API tourne dans un conteneur Docker. Elle permet au conteneur de joindre le port 11434 d'Ollama sur votre systeme hote Windows ou Linux (si vous utilisiez localhost, le conteneur chercherait Ollama a l'interieur de lui-meme).
- Le client applique automatiquement une temperature deterministe de 0.1 pour assurer une fidelite stricte de reponse comparable au cloud.

### Option B : Mode Production avec Google Cloud Vertex AI (PROD=true)

Dans votre fichier .env :
```env
PROD=true
GEMINI_MODEL=gemini-3.1-flash-lite
GCP_SERVICE_ACCOUNT_JSON=account_services.json
```

---

## Guide de Test Complet de Bout en Bout

Suivez ces etapes pour realiser le test complet : initialisation, creation du compte super-admin, configuration de l'entreprise sur l'interface web, traitement du bulletin en ligne de commande, et consultation des resultats.

### Etape 1 : Demarrer les conteneurs

Demarrez la base de donnees, l'API backend et l'interface frontend :

```bash
docker compose up -d postgres api frontend
```

Appliquez les migrations de schema :
```bash
docker compose exec api alembic -c api/alembic.ini upgrade head
```

---

### Etape 2 : Inserer les Domaines d'Activite de Test

Les avis de marches et les alertes d'entreprises reposent sur la table des domaines. Executez cette commande pour inserer les domaines standards en base :

```bash
docker compose exec api python -c "
from api.db.database import SessionLocal
from api.models.backend import Domaine

db = SessionLocal()
exemples = [
    ('Informatique & Telecoms', 'Fourniture de materiels informatiques, logiciels, reseaux et telecommunications'),
    ('Batiment et Travaux Publics (BTP)', 'Construction, rehabilitation de batiments, travaux de voirie et genie civil'),
    ('Sante et Materiel Medical', 'Fourniture de consommables medicaux, reactifs et equipements hospitaliers'),
    ('Fournitures de Bureau & Mobilier', 'Fournitures de bureau, papier, mobilier et consommables divers'),
    ('Etudes et Conseil', 'Prestations intellectuelles, audits, formations et etudes techniques')
]
for nom, desc in exemples:
    if not db.query(Domaine).filter(Domaine.nom == nom).first():
        db.add(Domaine(nom=nom, description=desc))
db.commit()
print('Domaines inseres avec succes !')
"
```

---

### Etape 3 : Creer le Compte Super-Admin

Executez cette commande pour creer un compte super-administrateur active et verifie :

```bash
docker compose exec api python -c "
from api.db.database import SessionLocal
from api.models.utilisateur import Utilisateur
from api.security import hash_password

db = SessionLocal()
email = 'admin@e-assis.bf'
user = db.query(Utilisateur).filter(Utilisateur.email == email).first()
if not user:
    user = Utilisateur(
        email=email,
        password_hash=hash_password('Admin1234!'),
        repnom='Admin',
        repprenom='Super',
        is_active=True,
        is_staff=True,
        is_superuser=True,
        is_email_verified=True,
        notifications_actives=True
    )
    db.add(user)
    db.commit()
    print('Compte super-admin cree : admin@e-assis.bf / Admin1234!')
else:
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.is_email_verified = True
    user.password_hash = hash_password('Admin1234!')
    db.commit()
    print('Compte super-admin mis a jour : admin@e-assis.bf / Admin1234!')
"
```

---

### Etape 4 : Creer l'Entreprise via l'Interface Web (http://localhost:3000)

1. Ouvrez votre navigateur a l'adresse : `http://localhost:3000`
2. Connectez-vous avec les identifiants crees :
   - Email : `admin@e-assis.bf`
   - Mot de passe : `Admin1234!`
3. Rendez-vous dans la section Entreprise / Profil de l'interface.
4. Renseignez les informations de l'entreprise que vous souhaitez tester (par exemple une entreprise presente dans le bulletin PDF a tester, ou une entreprise de BTP) :
   - Raison sociale (Nom de l'entreprise) : nom exact ou approchant de l'entreprise
   - IFU et RCCM (optionnels mais conseilles pour la reconciliation)
   - Cochez les Domaines d'activite correspondants (ex: `Batiment et Travaux Publics (BTP)` ou `Informatique & Telecoms`).
5. Enregistrez. L'entreprise est desormais enregistree en base et liee aux domaines selectionnes.

---

### Etape 5 : Copier le Bulletin PDF dans le Conteneur Docker

Revenez dans votre terminal. Copiez le fichier PDF de la revue depuis votre machine vers le dossier temporaire du conteneur `kbbot-api`.

Adaptez la commande avec le chemin exact de votre fichier et le nom de votre revue ( vous pouvez placer la revue a la racine du projet pour un chemin approprie) :

Sous Windows (PowerShell ou Invite de commandes) :
```powershell
docker cp "C:\chemin\vers\votre\quotidien_4480.pdf" kbbot-api:/tmp/bulletin_a_traiter.pdf
```

Sous Linux ou macOS :
```bash
docker cp /chemin/vers/votre/quotidien_4480.pdf kbbot-api:/tmp/bulletin_a_traiter.pdf
```

---

### Etape 6 : Lancer le Traitement Unifie du Bulletin

Lancez l'execution complete en precisant le fichier copie et le numero de bulletin :

```bash
docker compose exec api python -m api.scripts.process_bulletin --pdf /tmp/bulletin_a_traiter.pdf --bulletin 4480
```

Pendant l'execution, le script effectue :
1. Extraction des Avis de marches : decoupage des avis a partir de la page sommaire, identification de l'autorite et de l'objet, classification IA dans un des domaines de la base, et association aux entreprises abonnees a ces domaines.
2. Extraction des Resultats pour les entreprises de la base : recherche des mentions de vos entreprises clientes dans les tableaux de depouillement, analyse chirurgicale par l'IA (gagne/perdu/motif de rejet) et creation des alertes de resultats.

---

### Etape 7 : Visualiser les Resultats sur l'Interface Web

1. Retournez sur votre navigateur a l'adresse `http://localhost:3000`.
2. Actualisez la page :
   - Onglet Opportunites / Marches : visualisez la liste des nouveaux avis d'appels d'offres extraits du bulletin 4480 filtres selon vos domaines d'activite.
   - Onglet Alertes et Resultats : visualisez les notifications de resultats d'attribution detectees pour votre entreprise, indiquant le statut (remporte ou non), les lots concernes, les montants et les motifs eventuels de rejet.
