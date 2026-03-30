"""
Point d'entree de HChat.
Lance le serveur aiohttp sur l'hote et le port configures.

Demarrage :
    pip install -r requirements.txt
    python server.py

Variables d'environnement disponibles : voir .env.example
"""
from aiohttp import web

from app import create_app
from config import HOST, PORT, APP_NAME
from utils.logger import logger


if __name__ == "__main__":
    logger.info("Demarrage de %s sur http://%s:%d", APP_NAME, HOST, PORT)
    app = create_app()
    web.run_app(app, host=HOST, port=PORT, print=None)
