#!/bin/bash
# run_HChat.sh - Lanceur HChat (a copier dans le home, ne pas versionner)
# Usage: ~/run_HChat.sh [start|stop|logs|restart|pull]
#
# Exemple:
#   ~/run_HChat.sh pull      # Mise a jour depuis Git + demarrage
#   ~/run_HChat.sh start     # Demarrer le pod
#   ~/run_HChat.sh logs      # Voir les logs
#   ~/run_HChat.sh stop      # Arreter le pod

set -e

PROJECT_DIR="/opt/tool_HChat"
COMMAND="${1:-pull}"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[HChat]${NC} $1"
}

print_error() {
    echo -e "${RED}[Error]${NC} $1"
}

# Verifier le repertoire
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Repertoire $PROJECT_DIR non trouve"
    echo "Installez HChat avec: git clone <repo> $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

case "$COMMAND" in
    pull)
        print_status "Tirage des derniers changements..."
        git restore . 2>/dev/null || true
        git pull --rebase
        chmod +x deploy.sh
        print_status "Demarrage du pod..."
        ./deploy.sh start
        print_status "HChat est pret !"
        ;;
    start)
        print_status "Demarrage du pod..."
        chmod +x deploy.sh
        ./deploy.sh start
        ;;
    stop)
        print_status "Arret du pod..."
        chmod +x deploy.sh
        ./deploy.sh stop
        ;;
    restart)
        print_status "Redemarrage du pod..."
        chmod +x deploy.sh
        ./deploy.sh restart
        ;;
    logs)
        print_status "Logs en direct (Ctrl+C pour quitter)..."
        chmod +x deploy.sh
        ./deploy.sh logs
        ;;
    status)
        print_status "Statut du pod..."
        podman ps | grep hchat || echo "Le pod n'est pas en cours d'execution"
        ;;
    build)
        print_status "Reconstruction de l'image..."
        chmod +x deploy.sh
        ./deploy.sh restart
        ;;
    help|*)
        cat << EOF
${GREEN}HChat Launcher${NC}

Usage: $(basename "$0") [command]

Commands:
    pull      Mettre a jour depuis Git et demarrer (defaut)
    start     Demarrer le pod
    stop      Arreter le pod
    restart   Redemarrer le pod
    logs      Afficher les logs en temps reel
    status    Afficher le statut du pod
    build     Reconstruire l'image Podman

Exemples:
    ~/run_HChat.sh              # Mise a jour + demarrage
    ~/run_HChat.sh start        # Demarrer
    ~/run_HChat.sh logs         # Logs
    ~/run_HChat.sh pull         # Mise a jour + demarrage

Installation:
    1. Cloner: git clone <repo> /opt/tool_HChat
    2. Creer .env avec SECRET_KEY
    3. Copier ce script: cp run_HChat.sh ~/ && chmod +x ~/run_HChat.sh
    4. Lancer: ~/run_HChat.sh pull

Documentation: $PROJECT_DIR/README.md
EOF
        [ "$COMMAND" = "help" ] && exit 0 || exit 1
        ;;
esac
