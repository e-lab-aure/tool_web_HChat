"""
Factory de l'application aiohttp.
Configure les middlewares de securite, les routes et les taches de fond.
"""
from aiohttp import web

from config import STATIC_DIR, UPLOAD_DIR, DATA_DIR
from state import AppState
from utils.db import init_db
from utils.cleanup import cleanup_ctx
from utils.logger import logger

from handlers.pages import index, room_page
from handlers.ws import websocket_handler
from handlers.upload import upload_file, list_files, serve_file
from handlers.rooms import handle_create_room, handle_join_room, handle_destroy_room


@web.middleware
async def security_headers(request: web.Request, handler) -> web.Response:
    """
    Ajoute les en-tetes de securite HTTP a chaque reponse.
    Permet les scripts inline et eval pour le chiffrement Web Crypto dans le navigateur.
    """
    response = await handler(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP permissif sur les scripts pour autoriser Web Crypto API et les inline scripts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "font-src 'self' data:;"
    )
    return response


def _register_routes(app: web.Application) -> None:
    """Enregistre toutes les routes de l'application."""
    # Pages HTML
    app.router.add_get("/",                   index)
    app.router.add_get("/room/{room_id}",      room_page)

    # API REST rooms
    app.router.add_post("/api/rooms",                       handle_create_room)
    app.router.add_post("/api/rooms/{room_id}/join",        handle_join_room)
    app.router.add_post("/api/rooms/{room_id}/destroy",     handle_destroy_room)

    # WebSocket (token en query param)
    app.router.add_get("/ws/{room_id}",        websocket_handler)

    # Fichiers par room
    app.router.add_post("/api/rooms/{room_id}/upload",              upload_file)
    app.router.add_get( "/api/rooms/{room_id}/files",               list_files)
    app.router.add_get( "/api/rooms/{room_id}/uploads/{filename}",  serve_file)

    # Fichiers statiques (CSS, JS, images)
    app.router.add_static("/static", STATIC_DIR)


def create_app() -> web.Application:
    """
    Cree et configure l'application aiohttp.

    Initialise :
    - Les middlewares de securite
    - L'etat global (connexions WS)
    - La base de donnees SQLite
    - La tache de nettoyage des rooms expirees
    - Toutes les routes

    Returns:
        Instance web.Application prete a etre servie.
    """
    # client_max_size=0 desactive la limite interne d'aiohttp sur le corps HTTP,
    # ce qui permet le streaming de gros fichiers sans rejet premature.
    # La validation de taille est geree applicativement dans upload.py.
    app = web.Application(middlewares=[security_headers], client_max_size=0)

    app["state"] = AppState()

    # Cree les repertoires de donnees si absents
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Initialisation de la base de donnees au demarrage
    async def on_startup(app: web.Application) -> None:
        await init_db()
        logger.info("Application demarree.")

    async def on_cleanup(app: web.Application) -> None:
        # Ferme proprement toutes les connexions WS actives
        state: AppState = app["state"]
        for user in list(state._connections.values()):
            try:
                await user.ws.close()
            except Exception:
                pass
        logger.info("Application arretee.")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Tache de fond pour l'expiration automatique des rooms
    app.cleanup_ctx.append(cleanup_ctx)

    _register_routes(app)
    return app
