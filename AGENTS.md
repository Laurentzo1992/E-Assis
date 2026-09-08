# Charte d'Ingénierie & Règles d'Or du Projet (E-Assis-main)

Ce document régit l'ensemble des règles de développement, d'architecture et de méthodologie que l'agent et les développeurs doivent scrupuleusement respecter sur le projet.

---

### Règle 1 : Déterminisme d'abord, IA en complément ciblé
- Ne jamais déléguer à un LLM ce qui peut être résolu de manière déterministe (expressions régulières, parsers tabulaires géométriques, jointures SQL, trigrammes).
- Le routage des pages (avis d'appels d'offres vs résultats de dépouillement vs pages administratives/sommaires) s'effectue par analyse structurelle et détection de rubriques.
- L'extraction tabulaire est effectuée via des parsers dédiés ; le LLM n'intervient qu'en fallback ciblé ou clarification sémantique sur des textes non structurés.
- Bénéfices : Vitesse d'exécution décuplée, réduction drastique des coûts d'inférence, robustesse et reproductibilité totale.

---

### Règle 2 : Tolérance Zéro aux Faux Positifs d'Attribution
- Notifier à tort une entreprise qu'elle a remporté ou perdu un marché est inacceptable.
- La réconciliation d'entités (*Entity Resolution*) applique une hiérarchie stricte :
  1. **Niveau 1 :** Concordance exacte sur l'identifiant fiscal/légal (IFU, RCCM).
  2. **Niveau 2 :** Normalisation canonique stricte (suppression des formes juridiques *SARL, ETS, SA, SUARL, GIE*, mise en minuscules, suppression des accents et signes de ponctuation).
  3. **Niveau 3 :** Similarité trigramme (`pg_trgm`) avec seuil de tolérance strict ($\ge 0.85$).
- En cas de doute ou d'ambiguïté, le résultat est flagué `A_VERIFIER` sans émission d'alerte erronée.

---

### Règle 3 : Idempotence Absolue des Pipelines
- Tout script d'ingestion, d'extraction, de parsing ou de notification doit pouvoir être réexécuté $N$ fois d'affilée sans créer de doublon ni réémettre une notification déjà envoyée.
- Utilisation de contraintes d'unicité composites en base (ex. `numero_bulletin + reference_dossier + lot + entreprise_id`).
- Traçabilité des notifications via une table dédiée (`AlertLog`) avec statut d'émission et hash d'unicité du message.

---

### Règle 4 : Préservation du Code Existant et Rétrocompatibilité
- Ne jamais casser les fonctionnalités déjà en place dans `E-Assis-main`.
- Les évolutions de schéma PostgreSQL doivent systématiquement passer par des migrations versionnées Alembic.
- Réutilisation des briques existantes (`minio_client`, `email_utils`, `whatsapp_client`, `llm_client`).
- Le flux de détection des opportunités (appels d'offres) doit continuer de fonctionner sans interruption ; le pipeline des résultats d'attribution s'ajoute comme un service complémentaire et modulaire.

---

### Règle 5 : Traçabilité Complète et Auditabilité
- Chaque résultat extrait et chaque alerte émise doivent être reliés à leur source exacte dans le bulletin.
- Stockage systématique du numéro de bulletin, de la page PDF source, de l'extrait brut du tableau et de la date d'extraction.
- Conservation de la règle ou du score ayant déclenché le matching.

---

### Règle 6 : Gestion Défensive des Erreurs et Résilience
- Aucun échec ponctuel (page mal formatée, indisponibilité temporaire d'un webhook WhatsApp, coupure réseau) ne doit faire crasher le traitement global du document.
- Isolation des étapes dans des blocs `try/except` avec logging contextuel précis.
- Mécanismes de reprise et de file d'attente pour les notifications externes.

---

### Règle 7 : Validation Continue par Tests Réels
- Aucune brique n'est considérée terminée sans validation par des tests unitaires et d'intégration basés sur des cas réels du Quotidien des marchés publics (DGCMEF).
- Prise en compte des cas complexes : tableaux scindés sur plusieurs pages, groupements d'entreprises, attributions partielles, marchés infructueux.

---

### Règle 8 : Continuité et Intégrité de l'Environnement de Travail (Strict)
- **Emplacement unique :** Toutes les modifications, créations de code, scripts, modèles, migrations et tests doivent être exécutés **STRICTEMENT** à l'intérieur du répertoire `E-Assis-main/`, jamais en dehors.
- **Aucun déplacement :** Ne jamais déplacer, copier ou ramener le projet à la racine.
- **Aucune conversion de stack :** Ne jamais chercher à convertir ou réécrire le backend Python (FastAPI / SQLAlchemy / Alembic) en Node.js, Express.js ou tout autre framework pour tenter de le faire tourner dans l'environnement de conteneur local.
- **Pas de prévisualisation AI Studio :** Ne jamais tenter d'adapter le code pour la prévisualisation dans l'iframe d'AI Studio. L'ensemble de la plateforme est conçu pour tourner sur son infrastructure dédiée (Docker Compose, PostgreSQL, MinIO, Celery/Airflow, FastAPI) et sera testé hors de Google AI Studio.
