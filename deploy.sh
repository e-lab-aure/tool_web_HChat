#!/bin/bash

# Script de déploiement HChat avec Podman
# Utilisation: ./deploy.sh [start|stop|logs|rebuild]

set -e

CONTAINER_NAME="hchat"
IMAGE_NAME="hchat:latest"
PORT="${PORT:-8080}"
SECRET_KEY="${SECRET_KEY:-}"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[HChat]${NC} $1"
}

print_error() {
    echo -e "${RED}[Error]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[Warning]${NC} $1"
}

# Vérifier les prérequis
check_podman() {
    if ! command -v podman &> /dev/null; then
        print_error "Podman n'est pas installé. Veuillez installer Podman d'abord."
        exit 1
    fi
    print_status "Podman trouvé: $(podman --version)"
}

# Générer une clé secrète
generate_secret() {
    python3 -c "import secrets; print(secrets.token_hex(32))"
}

# Builder l'image
build() {
    print_status "Construction de l'image Docker..."
    podman build -t $IMAGE_NAME .
    print_status "Image construite: $IMAGE_NAME"
}

# Démarrer le conteneur
start() {
    # Vérifier si le conteneur existe déjà
    if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        print_warning "Le conteneur $CONTAINER_NAME existe déjà."
        print_status "Démarrage du conteneur..."
        podman start $CONTAINER_NAME
    else
        print_status "Création et démarrage du conteneur..."

        # Générer une clé si pas fournie
        if [ -z "$SECRET_KEY" ]; then
            print_warning "SECRET_KEY non définie. Génération d'une clé aléatoire..."
            SECRET_KEY=$(generate_secret)
        fi

        podman run -d \
            --name $CONTAINER_NAME \
            -p ${PORT}:8080 \
            -e SECRET_KEY="$SECRET_KEY" \
            -v "$(pwd)/uploads:/app/uploads" \
            -v "$(pwd)/data:/app/data" \
            -v "$(pwd)/chat.log:/app/chat.log" \
            --restart unless-stopped \
            --health-interval 30s \
            --health-timeout 5s \
            --health-start-period 10s \
            $IMAGE_NAME

        print_status "Conteneur créé et démarré avec succès"
        print_status "HChat est accessible à: http://localhost:${PORT}"
        if [ -n "$SECRET_KEY" ]; then
            echo -e "${GREEN}SECRET_KEY utilisée:${NC} $SECRET_KEY"
            echo -e "${YELLOW}Gardez cette clé en sécurité!${NC}"
        fi
    fi
}

# Arrêter le conteneur
stop() {
    if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        print_status "Arrêt du conteneur..."
        podman stop $CONTAINER_NAME
        print_status "Conteneur arrêté"
    else
        print_warning "Le conteneur $CONTAINER_NAME n'est pas actif"
    fi
}

# Supprimer le conteneur
remove() {
    if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        print_status "Suppression du conteneur..."
        podman rm $CONTAINER_NAME
        print_status "Conteneur supprimé"
    else
        print_warning "Le conteneur $CONTAINER_NAME n'existe pas"
    fi
}

# Afficher les logs
logs() {
    print_status "Logs du conteneur:"
    podman logs -f $CONTAINER_NAME
}

# Afficher le statut
status() {
    if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        print_status "Conteneur est en cours d'exécution"
        podman ps | grep $CONTAINER_NAME
    else
        print_warning "Conteneur n'est pas actif"
        if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
            podman ps -a | grep $CONTAINER_NAME
        fi
    fi
}

# Reconstruire et redémarrer
restart() {
    print_status "Reconstruction de l'image..."
    build
    stop
    remove
    start
    print_status "HChat a été redémarré"
}

# Menu aide
help() {
    cat << EOF
HChat Deployment Script

Usage: $0 [command]

Commands:
    build       Construire l'image Docker
    start       Démarrer le conteneur
    stop        Arrêter le conteneur
    remove      Supprimer le conteneur
    restart     Reconstruire et redémarrer le conteneur
    logs        Afficher les logs en temps réel
    status      Afficher le statut du conteneur
    help        Afficher cette aide

Variables d'environnement:
    PORT        Port d'écoute (défaut: 8080)
    SECRET_KEY  Clé secrète pour les tokens (générée si absente)

Examples:
    $0 build
    $0 start
    PORT=3000 $0 start
    SECRET_KEY="abc123..." $0 start
    $0 logs
    $0 stop

EOF
}

# Point d'entrée
check_podman

case "${1:-help}" in
    build)       build ;;
    start)       build && start ;;
    stop)        stop ;;
    remove)      remove ;;
    restart)     restart ;;
    logs)        logs ;;
    status)      status ;;
    help)        help ;;
    *)
        print_error "Commande inconnue: $1"
        help
        exit 1
        ;;
esac
