"""
Handlers HTTP pour la gestion des fichiers :
- upload multipart avec validation de type et de taille
- liste des fichiers disponibles
- telechargement securise (protection contre la traversee de repertoire)
"""
import json
from pathlib import Path
from urllib.parse import unquote

import aiofiles
from aiohttp import web

from config import UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS
from state import AppState
from utils.logger import logger


async def upload_file(request: web.Request) -> web.Response:
    """
    Recoit un fichier via un formulaire multipart/form-data.

    Valide :
    - Que le nom de fichier est present et non vide
    - Que l'extension est dans la liste blanche
    - Que la taille ne depasse pas MAX_UPLOAD_SIZE

    En cas de succes, diffuse un evenement 'file_added' via WebSocket
    a tous les clients connectes.

    Returns:
        JSON {"ok": true, "filename": "..."} ou {"ok": false, "error": "..."}
    """
    state: AppState = request.app["state"]

    try:
        reader = await request.multipart()
    except Exception as exc:
        logger.warning("Requete multipart invalide depuis %s : %s", request.remote, exc)
        return web.json_response({"ok": False, "error": "Requete invalide."}, status=400)

    async for part in reader:
        if not part.filename:
            continue

        # Normalisation du nom de fichier - protege contre la traversee de repertoire
        filename = Path(part.filename).name
        if not filename:
            return web.json_response({"ok": False, "error": "Nom de fichier invalide."}, status=400)

        # Validation de l'extension
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

        # Ecriture avec controle continu de la taille
        fpath = UPLOAD_DIR / filename
        total_bytes = 0
        try:
            async with aiofiles.open(fpath, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_SIZE:
                        # Supprime le fichier partiel avant de retourner l'erreur
                        fpath.unlink(missing_ok=True)
                        logger.warning(
                            "Upload annule depuis %s : fichier trop volumineux (%s, >%d Mo)",
                            request.remote, filename, MAX_UPLOAD_SIZE // 1024 // 1024,
                        )
                        return web.json_response(
                            {"ok": False, "error": f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // 1024 // 1024} Mo)."},
                            status=413,
                        )
                    await f.write(chunk)
        except OSError as exc:
            logger.error("Erreur d'ecriture fichier '%s' : %s", filename, exc)
            return web.json_response(
                {"ok": False, "error": "Erreur lors de l'enregistrement."},
                status=500,
            )

        logger.info(
            "Fichier uploade par %s : %s (%d octets)",
            request.remote, filename, total_bytes,
        )

        # Notifie tous les clients connectes du nouvel upload via WebSocket
        event = json.dumps({"type": "file_added", "filename": filename})
        await state.broadcast(event)

        return web.json_response({"ok": True, "filename": filename})

    return web.json_response({"ok": False, "error": "Aucun fichier recu."}, status=400)


async def list_files(request: web.Request) -> web.Response:
    """
    Retourne la liste JSON des fichiers disponibles dans UPLOAD_DIR,
    triee par nom et sans le placeholder .gitkeep.
    """
    try:
        files = sorted(
            f.name
            for f in UPLOAD_DIR.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        )
        return web.json_response(files)
    except OSError as exc:
        logger.error("Erreur de lecture du repertoire uploads : %s", exc)
        return web.Response(status=500, text="Erreur interne.")


async def serve_file(request: web.Request) -> web.Response:
    """
    Sert un fichier depuis UPLOAD_DIR pour le telechargement.
    Protege contre la traversee de repertoire en isolant le nom de fichier.
    """
    raw_name = unquote(request.match_info["filename"])
    filename = Path(raw_name).name  # Elimine tout prefixe de chemin (ex: ../../etc/passwd)

    filepath = UPLOAD_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        return web.Response(status=404, text="Fichier introuvable.")

    return web.FileResponse(filepath)
