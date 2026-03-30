"""
Fabrique de l'application aiohttp.
Configure le middleware de securite, les routes HTTP/WS
et les hooks de cycle de vie (demarrage / arret).
"""
from aiohttp import web

from config import UPLOAD_DIR, DATA_DIR
from state import AppState
from handlers.pages import index
from handlers.ws import websocket_handler
from handlers.upload import upload_file, list_files, serve_file
from utils.db import init_db
from utils.logger import logger


# ---------------------------------------------------------------------------
# Middleware de securite
# ---------------------------------------------------------------------------

@web.middleware
async def security_headers(request: web.Request, handler) -> web.Response:
    """
    Injecte les en-tetes de securite HTTP sur toutes les reponses.
    Protege contre le clickjacking, le sniffing de type MIME et le XSS reflechi.
    Les reponses WebSocket (deja envoyees lors du handshake) sont ignorees.
    """
    response = await handler(request)

    # WebSocketResponse envoie ses headers lors du prepare() dans le handler ;
    # tenter de les modifier apres coup leve une RuntimeError.
    if isinstance(response, web.WebSocketResponse):
        return response

    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response


# ---------------------------------------------------------------------------
# Hooks de cycle de vie
# ---------------------------------------------------------------------------

async def on_startup(app: web.Application) -> None:
    """
    Initialise les ressources necessaires au demarrage :
    - Cree les repertoires de donnees si absents
    - Initialise la base de donnees SQLite
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("Application '%s' demarree", app["config_name"])


async def on_cleanup(app: web.Application) -> None:
    """Nettoyage des ressources a l'arret propre du serveur."""
    logger.info("Application arretee proprement")


# ---------------------------------------------------------------------------
# Fabrique principale
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    """
    Cree, configure et retourne l'instance aiohttp prete a etre lancee.
    Cette fonction est aussi le point d'entree pour les tests unitaires.
    """
    from config import APP_NAME

    app = web.Application(middlewares=[security_headers])

    # Etat partage accessible depuis tous les handlers via request.app["state"]
    app["state"] = AppState()
    app["config_name"] = APP_NAME

    # Routes
    app.add_routes([
        web.get("/",                  index),
        web.get("/ws",                websocket_handler),
        web.post("/upload",           upload_file),
        web.get("/files",             list_files),
        web.get("/uploads/{filename}", serve_file),
    ])

    # Hooks
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app
