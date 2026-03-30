"""
Tache de fond pour l'expiration et le nettoyage automatique des rooms.
S'execute toutes les 5 minutes et supprime :
  - Les rooms dont la date d'expiration est passee (24h par defaut)
  - Les rooms sans activite depuis plus de 1h et sans clients connectes
Lors de la suppression, tous les messages et fichiers sont effaces.
"""
import asyncio
from typing import AsyncIterator

import aiosqlite

from config import DB_PATH, UPLOAD_DIR
from utils.db import get_expired_rooms, get_inactive_rooms
from utils.logger import logger

# Intervalle de verification en secondes
_CHECK_INTERVAL = 300

# Duree d'inactivite en minutes avant destruction automatique (aucun message, aucun client)
_INACTIVITY_MINUTES = 60


async def _delete_room_data(room_id: str) -> None:
    """
    Supprime physiquement les fichiers d'une room puis efface ses enregistrements en base.
    La suppression est irreversible.

    Args:
        room_id: Identifiant de la room a detruire.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")

        # Recupere les noms de fichiers avant la suppression en cascade
        cursor = await db.execute(
            "SELECT filename FROM room_files WHERE room_id = ?", (room_id,)
        )
        filenames = [row[0] for row in await cursor.fetchall()]

        # Supprime les enregistrements (ON DELETE CASCADE gere messages et room_files)
        await db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        await db.commit()

    # Supprime les fichiers physiques apres la transaction pour eviter les orphelins
    room_dir = UPLOAD_DIR / room_id
    for filename in filenames:
        (room_dir / filename).unlink(missing_ok=True)

    if room_dir.exists():
        try:
            room_dir.rmdir()
        except OSError:
            pass  # Le repertoire n'est pas vide - sera nettoye au prochain cycle

    logger.info("Room expiree et detruite : %s (%d fichier(s))", room_id[:8], len(filenames))


async def sweep_expired_rooms(active_room_ids: set[str] | None = None) -> int:
    """
    Detecte et supprime les rooms expirees et les rooms inactives sans clients connectes.

    Args:
        active_room_ids: Ensemble des room_id avec au moins un client connecte.
                         Passe par la tache de fond pour eviter de detruire des rooms actives.

    Returns:
        Nombre de rooms supprimees.
    """
    expired  = await get_expired_rooms()
    inactive = await get_inactive_rooms(active_room_ids or set(), _INACTIVITY_MINUTES)

    # Deduplique au cas ou une room serait a la fois expiree et inactive
    to_delete = list({*expired, *inactive})

    for room_id in to_delete:
        try:
            await _delete_room_data(room_id)
        except Exception as exc:
            logger.error("Erreur lors de la destruction de la room %s : %s", room_id[:8], exc)
    return len(to_delete)


async def _cleanup_loop(app) -> None:
    """
    Boucle infinie qui declenche le nettoyage des rooms toutes les CHECK_INTERVAL secondes.
    Recoit l'application pour acceder a l'etat des connexions actives.
    Concu pour s'executer comme tache asyncio independante.
    """
    logger.info("Tache de nettoyage des rooms demarree (intervalle : %ds)", _CHECK_INTERVAL)
    while True:
        await asyncio.sleep(_CHECK_INTERVAL)
        try:
            active_ids = app["state"].get_active_room_ids()
            count = await sweep_expired_rooms(active_ids)
            if count:
                logger.info(
                    "Nettoyage periodique : %d room(s) supprimee(s) (expirees ou inactives)",
                    count,
                )
        except Exception as exc:
            logger.error("Erreur dans la boucle de nettoyage : %s", exc)


async def cleanup_ctx(app) -> AsyncIterator[None]:
    """
    Generateur aiohttp (cleanup_ctx) pour la tache de nettoyage periodique.
    Demarre la tache au lancement du serveur et l'annule proprement a l'arret.
    Le yield separe la phase de demarrage (avant) de la phase d'arret (apres).
    """
    task = asyncio.create_task(_cleanup_loop(app))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Tache de nettoyage des rooms arretee.")
