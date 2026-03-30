"""
Etat global de l'application : connexions WebSocket actives et rate limiting.
Toutes les operations sur les connexions sont thread-safe dans un contexte asyncio.
"""
import json
from dataclasses import dataclass, field

from aiohttp import web

from utils.rate_limiter import RateLimiter


@dataclass
class ConnectedUser:
    """Represente un client WebSocket authentifie et connecte a une room."""
    ws:       web.WebSocketResponse
    user_id:  str
    username: str
    room_id:  str


class AppState:
    """
    Registre central des connexions WebSocket actives.

    Indexe les utilisateurs par user_id pour les operations unitaires
    et par room_id pour les diffusions groupees.
    """

    def __init__(self) -> None:
        # Index plat user_id -> ConnectedUser pour les acces directs
        self._connections: dict[str, ConnectedUser] = {}
        self.rate_limiter = RateLimiter()

    # ------------------------------------------------------------------
    # Gestion du registre
    # ------------------------------------------------------------------

    def add(self, user: ConnectedUser) -> None:
        """Enregistre une nouvelle connexion authentifiee."""
        self._connections[user.user_id] = user

    def remove(self, user_id: str) -> None:
        """Retire une connexion du registre (deconnexion ou expiration)."""
        self._connections.pop(user_id, None)

    def get(self, user_id: str) -> ConnectedUser | None:
        """Retourne un utilisateur par son identifiant, ou None s'il est absent."""
        return self._connections.get(user_id)

    # ------------------------------------------------------------------
    # Listes d'utilisateurs par room
    # ------------------------------------------------------------------

    def get_room_users(self, room_id: str) -> list[dict]:
        """
        Retourne la liste des utilisateurs actuellement connectes dans une room.

        Returns:
            Liste de dicts {"userId": ..., "username": ...}.
        """
        return [
            {"userId": u.user_id, "username": u.username}
            for u in self._connections.values()
            if u.room_id == room_id
        ]

    def get_active_room_ids(self) -> set[str]:
        """Retourne l'ensemble des room_id ayant au moins un client connecte."""
        return {u.room_id for u in self._connections.values()}

    # ------------------------------------------------------------------
    # Diffusion de messages
    # ------------------------------------------------------------------

    async def broadcast(self, payload: str, exclude_id: str | None = None) -> None:
        """
        Diffuse un message a tous les clients connectes, toutes rooms confondues.
        Utilise pour les evenements globaux (non implemente dans le protocole actuel).

        Args:
            payload:    Chaine JSON a envoyer.
            exclude_id: user_id a exclure de la diffusion (l'emetteur en general).
        """
        for user in list(self._connections.values()):
            if user.user_id == exclude_id:
                continue
            try:
                await user.ws.send_str(payload)
            except Exception:
                pass  # La connexion sera nettoyee a la prochaine iteration de son handler

    async def broadcast_to_room(
        self,
        room_id: str,
        payload: str,
        exclude_id: str | None = None,
    ) -> None:
        """
        Diffuse un message a tous les clients connectes dans une room specifique.

        Args:
            room_id:    Identifiant de la room cible.
            payload:    Chaine JSON a envoyer.
            exclude_id: user_id a exclure de la diffusion.
        """
        for user in list(self._connections.values()):
            if user.room_id != room_id:
                continue
            if user.user_id == exclude_id:
                continue
            try:
                await user.ws.send_str(payload)
            except Exception:
                pass

    async def send_to(self, user_id: str, payload: str) -> None:
        """
        Envoie un message a un utilisateur specifique.

        Args:
            user_id: Destinataire.
            payload: Chaine JSON a envoyer.
        """
        user = self._connections.get(user_id)
        if user:
            try:
                await user.ws.send_str(payload)
            except Exception:
                pass

    async def kick_room(self, room_id: str) -> None:
        """
        Ferme toutes les connexions WebSocket d'une room (utilise lors de la destruction).
        Envoie un evenement 'room_destroyed' avant la fermeture.

        Args:
            room_id: Identifiant de la room a vider.
        """
        payload = json.dumps({"type": "room_destroyed"})
        users = [u for u in self._connections.values() if u.room_id == room_id]
        for user in users:
            try:
                await user.ws.send_str(payload)
                await user.ws.close()
            except Exception:
                pass
