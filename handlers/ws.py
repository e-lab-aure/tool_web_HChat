"""
Handler WebSocket - coeur du systeme de messagerie en temps reel.

Protocole client -> serveur :
  {type: "join",    userId, username}
  {type: "message", content (HTML), plain (texte brut), userId, username}
  {type: "typing",  userId, username, isTyping (bool)}

Protocole serveur -> client :
  {type: "history",    messages: [...]}
  {type: "message",    id, content, plain, userId, username, time}
  {type: "users",      users: [{userId, username}]}
  {type: "system",     message}
  {type: "typing",     userId, username, isTyping}
  {type: "file_added", filename}
  {type: "error",      message}
"""
import json
from datetime import datetime

from aiohttp import web, WSMsgType

from config import MAX_MESSAGE_SIZE
from state import AppState, ConnectedUser
from utils.db import save_message, load_recent_messages
from utils.logger import logger


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Gere le cycle de vie complet d'une connexion WebSocket :
    1. Attente du message d'identification (type "join")
    2. Envoi de l'historique et annonce aux autres clients
    3. Diffusion des messages et evenements de frappe
    4. Nettoyage et annonce de depart a la deconnexion
    """
    state: AppState = request.app["state"]

    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE_SIZE)
    await ws.prepare(request)

    # L'utilisateur n'est identifie qu'apres reception du premier message "join"
    user: ConnectedUser | None = None

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                user = await _dispatch(ws, msg.data, user, state, request)

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
        if user:
            state.remove(user.user_id)
            logger.info("Deconnexion : %s (%s)", user.username, user.user_id[:8])

            await state.broadcast(json.dumps({
                "type": "users",
                "users": state.get_users_list(),
            }))
            await state.broadcast(json.dumps({
                "type":    "system",
                "message": f"{user.username} a quitte le chat.",
            }))

    return ws


async def _dispatch(
    ws:      web.WebSocketResponse,
    raw:     str,
    user:    ConnectedUser | None,
    state:   AppState,
    request: web.Request,
) -> ConnectedUser | None:
    """
    Analyse le type du message entrant et delègue au handler specifique.
    Retourne l'objet ConnectedUser courant (eventuellement mis a jour apres "join").
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Payload JSON invalide depuis %s", request.remote)
        return user

    msg_type = data.get("type")

    if msg_type == "join":
        # Renvoie le ConnectedUser cree, ou None si le join est rejete
        return await _handle_join(ws, data, state, request)

    if user is None:
        # Tout message autre que "join" est ignore si le client n'est pas identifie
        logger.warning("Message '%s' recu avant identification depuis %s", msg_type, request.remote)
        return None

    if msg_type == "message":
        await _handle_message(ws, data, user, state)
    elif msg_type == "typing":
        await _handle_typing(data, user, state)

    return user


async def _handle_join(
    ws:      web.WebSocketResponse,
    data:    dict,
    state:   AppState,
    request: web.Request,
) -> ConnectedUser | None:
    """
    Identifie le client, envoie l'historique, annonce la connexion aux autres.
    Ferme la connexion si le userId est absent ou vide.
    """
    user_id  = str(data.get("userId", ""))[:64].strip()
    username = str(data.get("username") or "Anonyme")[:32].strip() or "Anonyme"

    if not user_id:
        logger.warning("Connexion rejetee : userId absent depuis %s", request.remote)
        await ws.close()
        return None

    user = ConnectedUser(ws=ws, user_id=user_id, username=username)
    state.add(user)
    logger.info("Connexion : %s (%s) depuis %s", username, user_id[:8], request.remote)

    # Historique uniquement pour ce nouveau client
    try:
        history = await load_recent_messages()
        await ws.send_str(json.dumps({"type": "history", "messages": history}))
    except Exception as exc:
        logger.error("Erreur chargement historique pour %s : %s", username, exc)

    # Mise a jour de la liste d'utilisateurs pour tous
    await state.broadcast(json.dumps({
        "type":  "users",
        "users": state.get_users_list(),
    }))

    # Annonce systeme pour tous sauf le nouvel arrive
    await state.broadcast(
        json.dumps({"type": "system", "message": f"{username} a rejoint le chat."}),
        exclude_id=user_id,
    )

    return user


async def _handle_message(
    ws:    web.WebSocketResponse,
    data:  dict,
    user:  ConnectedUser,
    state: AppState,
) -> None:
    """
    Valide, persiste et diffuse un message de chat.
    Applique le rate limiting avant tout traitement.
    """
    if not state.rate_limiter.is_allowed(user.user_id):
        logger.warning("Rate limit atteint pour %s (%s)", user.username, user.user_id[:8])
        await ws.send_str(json.dumps({
            "type":    "error",
            "message": "Trop de messages envoyes. Attendez un moment avant de continuer.",
        }))
        return

    content = str(data.get("content", ""))
    plain   = str(data.get("plain",   "")).strip()

    if not plain:
        return  # Message vide ignore silencieusement

    time_str = datetime.now().strftime("%H:%M")

    try:
        msg_id = await save_message(user.user_id, user.username, content, plain)
    except Exception as exc:
        logger.error("Erreur persistance message de %s : %s", user.username, exc)
        msg_id = -1

    await state.broadcast(json.dumps({
        "type":     "message",
        "id":       msg_id,
        "content":  content,
        "plain":    plain,
        "userId":   user.user_id,
        "username": user.username,
        "time":     time_str,
    }))
    logger.info("Message de %s : %s", user.username, plain[:80])


async def _handle_typing(
    data:  dict,
    user:  ConnectedUser,
    state: AppState,
) -> None:
    """Diffuse l'indicateur de frappe a tous les clients sauf a l'emetteur."""
    await state.broadcast(
        json.dumps({
            "type":     "typing",
            "userId":   user.user_id,
            "username": user.username,
            "isTyping": bool(data.get("isTyping", False)),
        }),
        exclude_id=user.user_id,
    )
