"""
Limiteur de debit en memoire base sur une fenetre glissante.
Protege contre les floods de messages sans necessite de base de donnees.
"""
import time
from collections import defaultdict, deque

from config import RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW


class RateLimiter:
    """
    Implemente un algorithme de fenetre glissante par identifiant utilisateur.

    Pour chaque userId, conserve un historique des timestamps de ses messages.
    Un nouveau message est refuse si l'utilisateur en a deja envoye
    RATE_LIMIT_MESSAGES dans la fenetre de RATE_LIMIT_WINDOW secondes.
    """

    def __init__(
        self,
        max_messages: int = RATE_LIMIT_MESSAGES,
        window: int = RATE_LIMIT_WINDOW,
    ) -> None:
        """
        Args:
            max_messages: Nombre maximum de messages autorises dans la fenetre.
            window:       Duree de la fenetre en secondes.
        """
        self._max = max_messages
        self._window = window
        self._history: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, user_id: str) -> bool:
        """
        Verifie si l'utilisateur peut envoyer un message.

        Args:
            user_id: Identifiant unique de l'utilisateur.

        Returns:
            True si le message est autorise, False si la limite est atteinte.
        """
        now = time.monotonic()
        history = self._history[user_id]

        # Purge les entrees qui sortent de la fenetre courante
        while history and now - history[0] > self._window:
            history.popleft()

        if len(history) >= self._max:
            return False

        history.append(now)
        return True

    def cleanup_inactive(self) -> None:
        """
        Supprime les entrees des utilisateurs inactifs depuis plus de 2 fenetres.
        A appeler periodiquement pour eviter les fuites memoire sur longue duree.
        """
        now = time.monotonic()
        cutoff = self._window * 2
        inactive = [
            uid for uid, hist in self._history.items()
            if not hist or now - hist[-1] > cutoff
        ]
        for uid in inactive:
            del self._history[uid]
