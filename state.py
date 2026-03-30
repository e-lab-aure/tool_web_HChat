"""
Etat partage de l'application entre tous les handlers.
Centralise la gestion des connexions WebSocket actives
et le limiteur de debit.
"""
import json
from dataclasses import dataclass, field

from aiohttp import web

from utils.rate_limiter import RateLimiter
from utils.logger import logger


@dataclass
class ConnectedUser:
    """Represente un client WebSocket authentifie et connecte."""
    ws: web.WebSocketResponse
    user_id: str
    username: str


class AppState:
    """
    Registre central des connexions actives et services partages.
    Une seule instance est creee au demarrage et stockee dans app["state"].
    """

    def __init__(self) -> None:
        # Dictionnaire userId -> ConnectedUser pour un acces O(1)
        self._connections: dict[str, ConnectedUser] = {}
        self.rate_limiter: RateLimiter = RateLimiter()

    # ------------------------------------------------------------------
    # Gestion des connexions
    # ------------------------------------------------------------------

    def add(self, user: ConnectedUser) -> None:
        """Enregistre un nouveau client connecte."""
        self._connections[user.user_id] = user

    def remove(self, user_id: str) -> None:
        """Deconnecte et supprime un client du registre."""
        self._connections.pop(user_id, None)

    def get_users_list(self) -> list[dict]:
        """Retourne la liste des utilisateurs en ligne (pour diffusion aux clients)."""
        return [
            {"userId": u.user_id, "username": u.username}
            for u in self._connections.values()
        ]

    # ------------------------------------------------------------------
    # Diffusion de messages
    # ------------------------------------------------------------------

    async def broadcast(self, payload: str, exclude_id: str | None = None) -> None:
        """
        Diffuse un message JSON a tous les clients connectes.
        Les clients dont la connexion est morte sont silencieusement retires.

        Args:
            payload:    Chaine JSON a envoyer.
            exclude_id: userId a exclure de la diffusion (typiquement l'emetteur
                        pour les messages systeme ou de frappe).
        """
        dead: list[str] = []
        for uid, user in self._connections.items():
            if uid == exclude_id:
                continue
            try:
                await user.ws.send_str(payload)
            except Exception as exc:
                logger.warning("Impossible d'envoyer a %s (%s) : %s", user.username, uid[:8], exc)
                dead.append(uid)

        for uid in dead:
            self.remove(uid)

    async def send_to(self, user_id: str, payload: str) -> bool:
        """
        Envoie un message a un client specifique.

        Returns:
            True si le message a ete envoye, False si le client est introuvable ou mort.
        """
        user = self._connections.get(user_id)
        if not user:
            return False
        try:
            await user.ws.send_str(payload)
            return True
        except Exception as exc:
            logger.warning("Echec envoi direct a %s : %s", user_id[:8], exc)
            self.remove(user_id)
            return False
