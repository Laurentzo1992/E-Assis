#!/usr/bin/env bash
# Deploiement en une commande, a lancer depuis le repo sur le VPS : ./deploy.sh
#
# Prerequis (une seule fois sur le VPS, pas a chaque deploiement) :
#   - `git clone` du repo + `.env` rempli (cf. .env.example) a la racine.
#   - `docker login ghcr.io` avec un token ayant le droit `read:packages` (le repo est prive, les
#     images GHCR heritent de cette visibilite - un simple `docker compose pull` sans etre
#     connecte echoue en "denied").
#   - docker-compose.yml (dev, reseau "kbbot_backend") deja demarre au moins une fois OU
#     docker-compose.prod.yml demarre en premier : le reseau externe utilise par
#     docker-compose.airflow.yml doit exister avant de lancer ce dernier.
#
# Ce script suppose que la CI (.github/workflows/build-and-push.yml) a deja construit et publie
# les images a jour sur GHCR suite au dernier push sur main - il ne reconstruit jamais
# api/ingest/frontend localement (c'est tout l'interet : eviter de recompiler torch sur le VPS).

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Recuperation du code (git pull)"
git pull --ff-only

echo "==> Recuperation des images a jour (GHCR)"
docker compose -f docker-compose.prod.yml pull

echo "==> Redemarrage des services applicatifs"
docker compose -f docker-compose.prod.yml up -d

echo "==> Migration de la base de donnees (Alembic)"
docker exec kbbot-api sh -c "cd /app/api && alembic upgrade head"

echo "==> Airflow (rebuild leger, pas de dependances ML - toujours a jour en quelques secondes)"
docker compose -f docker-compose.airflow.yml up -d --build

echo "==> Nettoyage des anciennes images (evite l'accumulation de disque au fil des deploiements)"
docker image prune -f

echo "==> Deploiement termine."
docker compose -f docker-compose.prod.yml ps
