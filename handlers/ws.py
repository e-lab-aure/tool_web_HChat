"""
Handler WebSocket - coeur du systeme de messagerie en temps reel.

Authentification : token de session passe en query param (?token=...) verifie
AVANT l'ouverture de la connexion WS pour eviter les connexions non autorisees.

Protocole client -> serveur :
  {type: "message", content: "<JSON chiffre AES-GCM>"}
  {type: "typing",  isTyping: bool}

Protocole serveur -> client :
  {type: "history",        messages: [...]}
  {type: "message",        id, content, userId, username, time}
  {type: "users",          users: [{userId, username}]}
  {type: "system",         message}
  {type: "typing",         userId, username, isTyping}
  {type: "file_added",     filename}
  {type: "room_destroyed"} (fermeture immediate)
  {type: "error",          message}

Le champ "content" des messages est un payload chiffre opaque (JSON AES-GCM).
Le serveur ne le lit pas, ne le valide pas et ne le dechiffre jamais.
"""
import json

from aiohttp import web, WSMsgType

from config import MAX_MESSAGE_SIZE, MAX_HISTORY
from state import AppState, ConnectedUser
from utils.auth import verify_token
from utils.db import save_message, load_recent_messages, update_room_activity
from utils.logger import logger


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Gere le cycle de vie complet d'une connexion WebSocket authentifiee.

    1. Verifie le token de session avant l'ouverture de la connexion
    2. Envoie l'historique chiffre au nouveau client
    3. Diffuse les messages et evenements a la room
    4. Nettoie l'etat et annonce le depart a la deconnexion
    """
    state: AppState = request.app["state"]

    # Verification du token AVANT ws.prepare() pour rejeter les connexions non autorisees
    # sans ouvrir de connexion WebSocket coutouse
    token = request.rel_url.query.get("token", "")
    payload = verify_token(token)
    if not payload:
        return web.Response(status=401, text="Token invalide ou expire.")

    user_id  = payload["uid"]
    room_id  = payload["rid"]
    username = payload["usr"]

    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE_SIZE)
    await ws.prepare(request)

    user = ConnectedUser(ws=ws, user_id=user_id, username=username, room_id=room_id)
    state.add(user)
    logger.info("Connexion WS : %s (%s) -> room %s", username, user_id[:8], room_id[:8])

    try:
        # Envoie l'historique chiffre uniquement au nouveau client
        try:
            history = await load_recent_messages(room_id, limit=MAX_HISTORY)
            await ws.send_str(json.dumps({"type": "history", "messages": history}))
        except Exception as exc:
            logger.error("Erreur chargement historique pour %s : %s", username, exc)

        # Informe tous les membres de la room de la nouvelle connexion
        await state.broadcast_to_room(room_id, json.dumps({
            "type":  "users",
            "users": state.get_room_users(room_id),
        }))
        await state.broadcast_to_room(
            room_id,
            json.dumps({"type": "system", "message": f"{username} a rejoint le chat."}),
            exclude_id=user_id,
        )

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _dispatch(ws, msg.data, user, state)
            elif msg.type == WSMsgType.ERROR:
                logger.error(
                    "Erreur WebSocket depuis %s : %s",
                    request.remote, ws.exception(),
                )

    except Exception as exc:
        logger.error(
            "Exception inattendue dans le handler WS (%s) : %s",
            request.remote, exc,
            exc_info=True,
        )

    finally:
        state.remove(user_id)
        logger.info("Deconnexion : %s (%s) depuis room %s", username, user_id[:8], room_id[:8])

        await state.broadcast_to_room(room_id, json.dumps({
            "type":  "users",
            "users": state.get_room_users(room_id),
        }))
        await state.broadcast_to_room(
            room_id,
            json.dumps({"type": "system", "message": f"{username} a quitte le chat."}),
        )

    return ws


async def _dispatch(
    ws:    web.WebSocketResponse,
    raw:   str,
    user:  ConnectedUser,
    state: AppState,
) -> None:
    """
    Analyse le type du message entrant et delègue au handler specifique.

    Args:
        ws:    Connexion WebSocket de l'emetteur.
        raw:   Payload JSON brut recu.
        user:  Utilisateur authentifie associe a cette connexion.
        state: Etat global de l'application.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Payload JSON invalide de %s (%s)", user.username, user.user_id[:8])
        return

    msg_type = data.get("type")

    if msg_type == "message":
        await _handle_message(ws, data, user, state)
    elif msg_type == "typing":
        await _handle_typing(data, user, state)


async def _handle_message(
    ws:    web.WebSocketResponse,
    data:  dict,
    user:  ConnectedUser,
    state: AppState,
) -> None:
    """
    Valide, persiste et diffuse un message chiffre a toute la room.
    Le contenu (AES-GCM) est opaque pour le serveur - aucun acces au texte en clair.

    Applique le rate limiting avant tout traitement.
    """
    if not state.rate_limiter.is_allowed(user.user_id):
        logger.warning("Rate limit atteint pour %s (%s)", user.username, user.user_id[:8])
        await ws.send_str(json.dumps({
            "type":    "error",
            "message": "Trop de messages envoyes. Attendez un moment.",
        }))
        return

    content = str(data.get("content", "")).strip()
    if not content:
        return  # Message vide ignore silencieusement

    from datetime import datetime
    time_str = datetime.now().strftime("%H:%M")

    try:
        msg_id = await save_message(user.room_id, user.user_id, user.username, content)
    except Exception as exc:
        logger.error("Erreur persistance message de %s : %s", user.username, exc)
        msg_id = -1

    # Met a jour l'horodatage d'activite pour eviter la destruction automatique par inactivite
    try:
        await update_room_activity(user.room_id)
    except Exception as exc:
        logger.warning("Erreur mise a jour activite room %s : %s", user.room_id[:8], exc)

    await state.broadcast_to_room(
        user.room_id,
        json.dumps({
            "type":     "message",
            "id":       msg_id,
            "content":  content,
            "userId":   user.user_id,
            "username": user.username,
            "time":     time_str,
        }),
    )
    logger.info("Message chiffre de %s dans room %s", user.username, user.room_id[:8])


async def _handle_typing(
    data:  dict,
    user:  ConnectedUser,
    state: AppState,
) -> None:
    """Diffuse l'indicateur de frappe a tous les membres de la room sauf l'emetteur."""
    await state.broadcast_to_room(
        user.room_id,
        json.dumps({
            "type":     "typing",
            "userId":   user.user_id,
            "username": user.username,
            "isTyping": bool(data.get("isTyping", False)),
        }),
        exclude_id=user.user_id,
    )
