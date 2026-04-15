"""
Handlers HTTP pour la gestion des fichiers, scopees par room.
Chaque room dispose de son propre sous-repertoire dans UPLOAD_DIR.

Routes :
  POST   /api/rooms/{room_id}/upload
  GET    /api/rooms/{room_id}/files
  GET    /api/rooms/{room_id}/uploads/{filename}

Toutes les routes exigent un token de session valide pour la room concernee.

L'upload utilise un streaming raw (corps HTTP brut, header X-Filename) plutot
que multipart/form-data, ce qui permet de traiter des fichiers volumineux
sans les charger entierement en memoire.
"""
import json
import time
from pathlib import Path
from urllib.parse import unquote

import aiofiles
from aiohttp import web

from config import (
    UPLOAD_DIR,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
    UPLOAD_CHUNK_SIZE,
    UPLOAD_PROGRESS_LOG_BYTES,
)
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
    Recoit un fichier via streaming HTTP brut et le stocke dans le sous-repertoire
    de la room apres validation d'extension.

    Le nom du fichier est transmis dans l'en-tete X-Filename (pas de multipart).
    Les donnees sont lues par chunks de UPLOAD_CHUNK_SIZE pour limiter
    l'empreinte memoire, meme pour des fichiers de plusieurs gigaoctets.

    Diffuse un evenement 'file_added' a tous les participants de la room via WebSocket.

    Returns:
        JSON {"ok": true, "filename": "...", "size": <octets>}
        ou   {"ok": false, "error": "..."}.
    """
    room_id = request.match_info["room_id"]
    state: AppState = request.app["state"]

    if not _check_token(request, room_id):
        return web.json_response({"ok": False, "error": "Non autorise."}, status=401)

    # Recupere et assainit le nom de fichier transmis dans le header.
    # Le client encode le nom en URL (encodeURIComponent) pour supporter
    # les caracteres speciaux et les espaces.
    raw_name = unquote(request.headers.get("X-Filename", "").strip())
    if not raw_name:
        return web.json_response({"ok": False, "error": "Header X-Filename manquant."}, status=400)

    filename = Path(raw_name).name  # Elimine tout prefixe de chemin (traversee de repertoire)
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

    room_dir = UPLOAD_DIR / room_id
    room_dir.mkdir(parents=True, exist_ok=True)
    fpath = room_dir / filename

    total_bytes = 0
    start = time.monotonic()
    last_log_threshold = 0  # prochain seuil de progression (en octets) pour le log

    try:
        async with aiofiles.open(fpath, "wb") as f:
            while True:
                chunk = await request.content.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break

                await f.write(chunk)
                total_bytes += len(chunk)

                # Verifie la limite de taille si elle est definie (MAX_UPLOAD_SIZE > 0)
                if MAX_UPLOAD_SIZE > 0 and total_bytes > MAX_UPLOAD_SIZE:
                    fpath.unlink(missing_ok=True)
                    limit_mb = MAX_UPLOAD_SIZE // 1024 // 1024
                    logger.warning(
                        "Upload annule depuis %s : fichier trop volumineux (%s, >%dMo)",
                        request.remote, filename, limit_mb,
                    )
                    return web.json_response(
                        {"ok": False, "error": f"Fichier trop volumineux (max {limit_mb}Mo)."},
                        status=413,
                    )

                # Log de progression tous les UPLOAD_PROGRESS_LOG_BYTES
                if total_bytes >= last_log_threshold + UPLOAD_PROGRESS_LOG_BYTES:
                    last_log_threshold = total_bytes
                    elapsed = time.monotonic() - start
                    speed = (total_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    logger.info(
                        "Upload en cours [room %s] %s : %d Mo recus | %.2f Mo/s",
                        room_id[:8], filename, total_bytes // (1024 * 1024), speed,
                    )

    except OSError as exc:
        fpath.unlink(missing_ok=True)
        logger.error("Erreur d'ecriture '%s' dans room %s : %s", filename, room_id[:8], exc)
        return web.json_response({"ok": False, "error": "Erreur lors de l'enregistrement."}, status=500)

    elapsed = time.monotonic() - start
    speed = (total_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
    logger.info(
        "Fichier uploade [room %s] par %s : %s (%.2f Mo en %.2fs, %.2f Mo/s)",
        room_id[:8], request.remote, filename,
        total_bytes / (1024 * 1024), elapsed, speed,
    )

    await register_file(room_id, filename)

    event = json.dumps({"type": "file_added", "filename": filename})
    await state.broadcast_to_room(room_id, event)

    return web.json_response({"ok": True, "filename": filename, "size": total_bytes})


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
