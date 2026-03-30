"""
Handlers HTTP pour la gestion des fichiers, scopees par room.
Chaque room dispose de son propre sous-repertoire dans UPLOAD_DIR.

Routes :
  POST   /api/rooms/{room_id}/upload
  GET    /api/rooms/{room_id}/files
  GET    /api/rooms/{room_id}/uploads/{filename}

Toutes les routes exigent un token de session valide pour la room concernee.
"""
import json
from pathlib import Path
from urllib.parse import unquote

import aiofiles
from aiohttp import web

from config import UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS
from state import AppState
from utils.auth import verify_token
from utils.db import register_file, list_room_files
from utils.logger import logger


def _check_token(request: web.Request, room_id: str) -> dict | None:
    """
    Extrait et verifie le token de session depuis la query string ou l'en-tete Authorization.
    Verifie que le token est bien autorise pour la room demandee.

    Returns:
        Payload dict si valide, None sinon.
    """
    token = request.rel_url.query.get("token", "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    payload = verify_token(token)
    if not payload or payload.get("rid") != room_id:
        return None
    return payload


async def upload_file(request: web.Request) -> web.Response:
    """
    Recoit un fichier via multipart/form-data et le stocke dans le sous-repertoire
    de la room apres validation d'extension et de taille.

    Diffuse un evenement 'file_added' a tous les participants de la room via WebSocket.

    Returns:
        JSON {"ok": true, "filename": "..."} ou {"ok": false, "error": "..."}.
    """
    room_id = request.match_info["room_id"]
    state: AppState = request.app["state"]

    if not _check_token(request, room_id):
        return web.json_response({"ok": False, "error": "Non autorise."}, status=401)

    try:
        reader = await request.multipart()
    except Exception as exc:
        logger.warning("Requete multipart invalide depuis %s : %s", request.remote, exc)
        return web.json_response({"ok": False, "error": "Requete invalide."}, status=400)

    room_dir = UPLOAD_DIR / room_id
    room_dir.mkdir(parents=True, exist_ok=True)

    async for part in reader:
        if not part.filename:
            continue

        # Isole le nom de fichier pour prevenir la traversee de repertoire
        filename = Path(part.filename).name
        if not filename:
            return web.json_response({"ok": False, "error": "Nom de fichier invalide."}, status=400)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(
                "Upload refuse depuis %s : extension '.%s' non autorisee (%s)",
                request.remote, ext, filename,
            )
            return web.json_response(
                {"ok": False, "error": f"Extension .{ext} non autorisee."},
                status=415,
            )

        fpath = room_dir / filename
        total_bytes = 0
        try:
            async with aiofiles.open(fpath, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_SIZE:
                        fpath.unlink(missing_ok=True)
                        logger.warning(
                            "Upload annule depuis %s : fichier trop volumineux (%s, >%dMo)",
                            request.remote, filename, MAX_UPLOAD_SIZE // 1024 // 1024,
                        )
                        return web.json_response(
                            {"ok": False, "error": f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // 1024 // 1024}Mo)."},
                            status=413,
                        )
                    await f.write(chunk)
        except OSError as exc:
            logger.error("Erreur d'ecriture '%s' dans room %s : %s", filename, room_id[:8], exc)
            return web.json_response({"ok": False, "error": "Erreur lors de l'enregistrement."}, status=500)

        await register_file(room_id, filename)
        logger.info(
            "Fichier uploade dans room %s par %s : %s (%d octets)",
            room_id[:8], request.remote, filename, total_bytes,
        )

        event = json.dumps({"type": "file_added", "filename": filename})
        await state.broadcast_to_room(room_id, event)

        return web.json_response({"ok": True, "filename": filename})

    return web.json_response({"ok": False, "error": "Aucun fichier recu."}, status=400)


async def list_files(request: web.Request) -> web.Response:
    """
    Retourne la liste JSON des fichiers disponibles dans la room.
    """
    room_id = request.match_info["room_id"]

    if not _check_token(request, room_id):
        return web.json_response({"error": "Non autorise."}, status=401)

    try:
        files = await list_room_files(room_id)
        return web.json_response(files)
    except Exception as exc:
        logger.error("Erreur lecture fichiers room %s : %s", room_id[:8], exc)
        return web.Response(status=500, text="Erreur interne.")


async def serve_file(request: web.Request) -> web.Response:
    """
    Sert un fichier depuis le sous-repertoire de la room.
    Protege contre la traversee de repertoire.
    """
    room_id = request.match_info["room_id"]

    if not _check_token(request, room_id):
        return web.Response(status=401, text="Non autorise.")

    raw_name = unquote(request.match_info["filename"])
    filename = Path(raw_name).name  # Elimine tout prefixe de chemin

    filepath = UPLOAD_DIR / room_id / filename
    if not filepath.exists() or not filepath.is_file():
        return web.Response(status=404, text="Fichier introuvable.")

    return web.FileResponse(filepath)
