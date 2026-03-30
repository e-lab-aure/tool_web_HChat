"""
Couche de persistance SQLite via aiosqlite.
Gere l'historique des messages du chat avec des operations
entierement asynchrones pour ne pas bloquer la boucle d'evenements.
"""
import aiosqlite

from config import DB_PATH, MAX_HISTORY
from utils.logger import logger


async def init_db() -> None:
    """
    Cree le schema de la base de donnees si necessaire.
    Doit etre appelee une seule fois au demarrage du serveur.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT    NOT NULL,
                username  TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                plain     TEXT    NOT NULL,
                sent_at   TEXT    NOT NULL
            )
        """)
        await db.commit()
    logger.info("Base de donnees initialisee : %s", DB_PATH)


async def save_message(user_id: str, username: str, content: str, plain: str) -> int:
    """
    Persiste un message dans la base et retourne son identifiant generé.

    Args:
        user_id:  UUID unique du client emetteur.
        username: Nom d'affichage choisi par l'utilisateur.
        content:  HTML sanitize du message.
        plain:    Texte brut du message (pour notifications et recherche).

    Returns:
        L'identifiant auto-incremente du message insere.
    """
    from datetime import datetime
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (user_id, username, content, plain, sent_at) VALUES (?,?,?,?,?)",
            (user_id, username, content, plain, sent_at),
        )
        await db.commit()
        return cursor.lastrowid


async def load_recent_messages(limit: int = MAX_HISTORY) -> list[dict]:
    """
    Charge les N derniers messages dans l'ordre chronologique.
    Utilise pour initialiser l'historique des nouveaux clients.

    Args:
        limit: Nombre maximum de messages a charger.

    Returns:
        Liste de dicts serialisables en JSON, du plus ancien au plus recent.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, username, content, plain, sent_at
            FROM   messages
            ORDER  BY id DESC
            LIMIT  ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

    # Inverse pour avoir l'ordre chronologique (du plus ancien au plus recent)
    return [
        {
            "type":     "message",
            "id":       row["id"],
            "userId":   row["user_id"],
            "username": row["username"],
            "content":  row["content"],
            "plain":    row["plain"],
            # Extrait seulement HH:MM depuis "YYYY-MM-DD HH:MM:SS"
            "time":     row["sent_at"][11:16],
        }
        for row in reversed(rows)
    ]
