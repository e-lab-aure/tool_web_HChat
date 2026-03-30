"""
Handlers HTTP pour la gestion des rooms :
- Creation d'une room avec mot de passe
- Rejoindre une room existante
- Destruction manuelle d'une room

Le serveur ne stocke jamais le mot de passe en clair.
Le sel retourne au client permet la derivation de la cle AES-GCM dans le navigateur.
"""
import os
import secrets

from aiohttp import web

from state import AppState
from utils.auth import hash_password, verify_password, create_token
from utils.cleanup import _delete_room_data
from utils.db import create_room, get_room
from utils.logger import logger


async def handle_create_room(request: web.Request) -> web.Response:
    """
    Cree une nouvelle room chiffree.

    Corps JSON attendu : {"password": "...", "username": "...", "allow_anyone_destroy": true}

    Le mot de passe est hache avec scrypt avant stockage.
    Un sel aleatoire (distinct du sel scrypt) est genere pour la derivation
    de la cle AES-GCM cote client.

    Returns:
        JSON {"room_id", "salt", "token", "expires_in", "is_creator", "allow_anyone_destroy"}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Corps JSON invalide."}, status=400)

    password             = str(data.get("password", "")).strip()
    username             = str(data.get("username", "")).strip()[:32] or "Anonyme"
    allow_anyone_destroy = bool(data.get("allow_anyone_destroy", True))

    if not password:
        return web.json_response({"error": "Le mot de passe est obligatoire."}, status=400)
    if len(password) < 6:
        return web.json_response({"error": "Le mot de passe doit faire au moins 6 caracteres."}, status=400)

    # Sel pour la derivation de cle AES-GCM (distinct du sel scrypt interne)
    crypto_salt   = secrets.token_hex(16)
    password_hash = hash_password(password)
    user_id       = secrets.token_hex(16)

    try:
        room_id = await create_room(
            password_hash,
            crypto_salt,
            creator_id=user_id,
            allow_anyone_destroy=allow_anyone_destroy,
        )
    except Exception as exc:
        logger.error("Erreur creation room : %s", exc)
        return web.json_response({"error": "Erreur interne."}, status=500)

    token = create_token(user_id, room_id, username)
    logger.info("Room creee par %s (%s) : %s", username, request.remote, room_id[:8])

    return web.json_response({
        "room_id":            room_id,
        "salt":               crypto_salt,
        "token":              token,
        "expires_in":         86400,
        "is_creator":         True,
        "allow_anyone_destroy": allow_anyone_destroy,
    })


async def handle_join_room(request: web.Request) -> web.Response:
    """
    Rejoint une room existante apres verification du mot de passe.

    Corps JSON attendu : {"password": "...", "username": "..."}

    Returns:
        JSON {"salt": "...", "token": "..."} si le mot de passe est correct,
        ou 401/404 selon l'erreur.
    """
    room_id = request.match_info["room_id"]

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Corps JSON invalide."}, status=400)

    password = str(data.get("password", "")).strip()
    username = str(data.get("username", "")).strip()[:32] or "Anonyme"

    if not password:
        return web.json_response({"error": "Le mot de passe est obligatoire."}, status=400)

    room = await get_room(room_id)
    if room is None:
        # Meme message pour room introuvable et mot de passe incorrect
        # afin d'eviter l'enumeration des rooms
        return web.json_response({"error": "Room introuvable ou mot de passe incorrect."}, status=401)

    if not verify_password(password, room["password_hash"]):
        logger.warning(
            "Tentative de connexion avec mauvais mot de passe sur la room %s depuis %s",
            room_id[:8], request.remote,
        )
        return web.json_response({"error": "Room introuvable ou mot de passe incorrect."}, status=401)

    user_id = secrets.token_hex(16)
    token = create_token(user_id, room_id, username)
    logger.info("Utilisateur %s (%s) a rejoint la room %s", username, request.remote, room_id[:8])

    return web.json_response({
        "salt":               room["salt"],
        "token":              token,
        "is_creator":         False,
        "allow_anyone_destroy": bool(room["allow_anyone_destroy"]),
    })


async def handle_destroy_room(request: web.Request) -> web.Response:
    """
    Detruit une room et toutes ses donnees a la demande d'un participant.
    Necessite un token de session valide pour la room concernee.
    Ferme egalement toutes les connexions WebSocket actives dans cette room.

    Returns:
        JSON {"ok": true} en cas de succes, ou erreur appropriee.
    """
    from utils.auth import verify_token

    room_id = request.match_info["room_id"]

    # Verification du token dans l'en-tete Authorization ou le corps JSON
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        try:
            data = await request.json()
            token = str(data.get("token", ""))
        except Exception:
            pass

    if not token:
        return web.json_response({"error": "Token manquant."}, status=401)

    payload = verify_token(token)
    if not payload or payload.get("rid") != room_id:
        return web.json_response({"error": "Token invalide ou expire."}, status=401)

    room = await get_room(room_id)
    if room is None:
        return web.json_response({"error": "Room introuvable."}, status=404)

    # Verifie les droits de destruction si la room est restreinte au createur
    if not room["allow_anyone_destroy"]:
        if payload.get("uid") != room["creator_id"]:
            logger.warning(
                "Tentative de destruction non autorisee de la room %s par %s (%s)",
                room_id[:8], payload.get("usr"), request.remote,
            )
            return web.json_response(
                {"error": "Seul le createur peut detruire cette room."},
                status=403,
            )

    # Ferme les connexions WS avant la suppression physique
    state: AppState = request.app["state"]
    await state.kick_room(room_id)

    try:
        await _delete_room_data(room_id)
    except Exception as exc:
        logger.error("Erreur destruction room %s : %s", room_id[:8], exc)
        return web.json_response({"error": "Erreur interne."}, status=500)

    logger.info(
        "Room %s detruite manuellement par %s (%s)",
        room_id[:8], payload.get("usr"), request.remote,
    )
    return web.json_response({"ok": True})
