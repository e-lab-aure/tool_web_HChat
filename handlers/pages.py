"""
Handler HTTP pour la page principale de l'application.
Sert le fichier static/index.html depuis le repertoire du projet.
"""
from aiohttp import web

from config import STATIC_DIR


async def index(request: web.Request) -> web.FileResponse:
    """Sert la page principale de l'application."""
    return web.FileResponse(STATIC_DIR / "index.html")
