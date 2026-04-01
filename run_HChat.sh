#!/bin/bash
# run_HChat.sh - Lanceur HChat (à copier dans le home, ne pas versionner)
# Usage: ~/run_HChat.sh [pull|logs|stop]
#
# Exemples:
#   ~/run_HChat.sh           # Mise à jour + démarrage
#   ~/run_HChat.sh logs      # Voir les logs
#   ~/run_HChat.sh stop      # Arrêter

set -e

PROJECT_DIR="/opt/tool_web_HChat"
CONTAINER="hchat"
COMMAND="${1:-pull}"

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[HChat]${NC} $1"
}

print_error() {
    echo -e "${RED}[Error]${NC} $1"
}

# Vérifier le répertoire du projet
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Répertoire $PROJECT_DIR non trouvé"
    echo "Installez HChat avec: git clone <repo> $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

case "$COMMAND" in
    pull)
        # Mise à jour depuis Git + démarrage
        print_status "Tirage des derniers changements..."
        git restore . 2>/dev/null || true
        git pull --rebase
        chmod +x deploy.sh
        print_status "Démarrage du conteneur..."
        ./deploy.sh
        ;;
    logs)
        # Afficher les logs en direct
        print_status "Logs du conteneur (Ctrl+C pour quitter)..."
        podman logs -f "$CONTAINER"
        ;;
    stop)
        # Arrêter et supprimer le conteneur
        print_status "Arrêt du conteneur..."
        podman stop "$CONTAINER" || true
        podman rm "$CONTAINER" || true
        print_status "Conteneur arrêté"
        ;;
    help|*)
        cat << EOF
${GREEN}HChat Launcher${NC}

Usage: $(basename "$0") [command]

Commands:
    pull      Mettre à jour depuis Git et démarrer (défaut)
    logs      Afficher les logs en temps réel
    stop      Arrêter et supprimer le conteneur
    help      Afficher cette aide

Exemples:
    ~/run_HChat.sh          # Mise à jour + démarrage
    ~/run_HChat.sh logs     # Voir les logs
    ~/run_HChat.sh stop     # Arrêter

Installation:
    1. Cloner: git clone <repo> /opt/tool_web_HChat
    2. Créer .env avec SECRET_KEY
    3. Copier ce script: cp run_HChat.sh ~/ && chmod +x ~/run_HChat.sh
    4. Lancer: ~/run_HChat.sh pull

Documentation: /opt/tool_web_HChat/README.md
EOF
        [ "$COMMAND" = "help" ] && exit 0 || exit 1
        ;;
esac
