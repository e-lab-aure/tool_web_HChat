"""
Handlers HTTP pour les pages HTML de l'application.
Sert la page d'accueil et les pages de room depuis static/.
"""
from aiohttp import web

from config import STATIC_DIR


async def index(request: web.Request) -> web.FileResponse:
    """Sert la page d'accueil (creation et rejoindre une room)."""
    return web.FileResponse(STATIC_DIR / "index.html")


async def room_page(request: web.Request) -> web.FileResponse:
    """
    Sert la page de chat pour une room specifique.
    L'authentification est geree cote client (formulaire de mot de passe).
    """
    return web.FileResponse(STATIC_DIR / "room.html")
