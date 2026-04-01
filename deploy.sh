#!/bin/bash
# deploy.sh - Construit et lance le conteneur HChat

set -e

IMAGE="hchat:latest"
CONTAINER="hchat"
DATA_DIR="/opt/tool_web_HChat/data"
UPLOAD_DIR="/opt/tool_web_HChat/uploads"

# Charger les variables d'environnement du fichier .env
if [ -f ".env" ]; then
    export $(grep -v "^#" .env | xargs)
fi

PORT="${PORT:-8080}"

# Création des répertoires de données
mkdir -p "$DATA_DIR" "$UPLOAD_DIR"

# Construction de l'image Podman
echo "[INFO] Construction de l'image $IMAGE..."
podman build -t "$IMAGE" -f Containerfile .

# Lancement du conteneur
#
# Volumes montés :
#   $DATA_DIR         - base de données SQLite
#   $UPLOAD_DIR       - fichiers uploadés
#
# --replace : supprime et recrée si le conteneur existe déjà
# --env-file .env : charge toutes les variables de configuration

echo "[INFO] Démarrage du conteneur $CONTAINER sur le port $PORT..."

podman run -d \
    --replace \
    --name "$CONTAINER" \
    -p ${PORT}:8080 \
    --env-file .env \
    -v "$DATA_DIR":/app/data:z \
    -v "$UPLOAD_DIR":/app/uploads:z \
    --restart unless-stopped \
    "$IMAGE"

echo "[OK] HChat démarré - http://localhost:${PORT}"
echo "[INFO] Logs du conteneur : podman logs -f $CONTAINER"
