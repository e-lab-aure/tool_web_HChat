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

PORT="${PORT:-8081}"

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

# Arrêt propre de l'ancien conteneur avant remplacement
# --replace utiliserait le timeout par defaut (10s) de l'ancien conteneur
if podman container exists "$CONTAINER" 2>/dev/null; then
    echo "[INFO] Arrêt de l'ancien conteneur (timeout 30s)..."
    podman stop --time 30 "$CONTAINER" 2>/dev/null || true
    podman rm "$CONTAINER" 2>/dev/null || true
fi

podman run -d \
    --name "$CONTAINER" \
    -p ${PORT}:8081 \
    --env-file .env \
    -v "$DATA_DIR":/app/data:z \
    -v "$UPLOAD_DIR":/app/uploads:z \
    --restart unless-stopped \
    --stop-timeout 30 \
    "$IMAGE"

echo "[OK] HChat démarré - http://localhost:${PORT}"
echo "[INFO] Logs du conteneur : podman logs -f $CONTAINER"
