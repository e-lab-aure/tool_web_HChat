"""
Couche de persistance SQLite via aiosqlite.
Gere les rooms, messages chiffres et fichiers avec migration de schema versionne.

Schema v1 : rooms, messages, room_files, schema_version
Les messages stockent uniquement le contenu chiffre cote client (AES-GCM).
Le serveur ne voit jamais le texte en clair.
"""
import secrets
from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH, DATA_DIR, ROOM_EXPIRY_HOURS
from utils.logger import logger

# Version courante du schema - incrementer a chaque migration
_SCHEMA_VERSION = 1


async def init_db() -> None:
    """
    Initialise la base de donnees et applique les migrations necessaires.
    Cree le repertoire data/ si absent.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Table de versionnage pour les migrations futures
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
        """)

        cursor = await db.execute("SELECT version FROM schema_version LIMIT 1")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0

        if current_version < 1:
            await _migrate_v1(db)

        await db.commit()
    logger.info("Base de donnees initialisee (schema v%d)", _SCHEMA_VERSION)


async def _migrate_v1(db: aiosqlite.Connection) -> None:
    """
    Migration vers le schema v1 : rooms, messages chiffres, fichiers par room.
    Supprime les tables de l'ancien schema (sans rooms ni room_id) si elles existent.
    """
    # Detecte le schema legacy (messages sans colonne room_id) et le supprime proprement
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if await cursor.fetchone():
        cursor2 = await db.execute("PRAGMA table_info(messages)")
        cols = [row[1] for row in await cursor2.fetchall()]
        if "room_id" not in cols:
            logger.info("Schema legacy detecte - suppression des anciennes tables")
            await db.execute("DROP TABLE IF EXISTS messages")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id           TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt         TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            expires_at   TEXT NOT NULL
        )
    """)

    # Le champ content stocke le JSON {"iv":"..","ct":".."} chiffre AES-GCM
    # Le serveur ne peut pas lire ce contenu - il le relaie uniquement
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id    TEXT    NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            user_id    TEXT    NOT NULL,
            username   TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            sent_at    TEXT    NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, sent_at)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS room_files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id     TEXT    NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            filename    TEXT    NOT NULL,
            uploaded_at TEXT    NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_files_room ON room_files(room_id)")

    # Marque le schema comme migre en v1
    await db.execute("DELETE FROM schema_version")
    await db.execute("INSERT INTO schema_version (version) VALUES (1)")
    logger.info("Migration schema v1 appliquee")


# ---------------------------------------------------------------------------
# Gestion des rooms
# ---------------------------------------------------------------------------

async def create_room(password_hash: str, salt: str) -> str:
    """
    Cree une nouvelle room avec un identifiant aleatoire cryptographiquement sur.

    Args:
        password_hash: Hash scrypt du mot de passe (format "sel$hash").
        salt:          Sel hexadecimal pour la derivation de cle cote client.

    Returns:
        L'identifiant unique de la room creee.
    """
    room_id = secrets.token_urlsafe(16)
    now = datetime.now()
    expires_at = now + timedelta(hours=ROOM_EXPIRY_HOURS)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            "INSERT INTO rooms (id, password_hash, salt, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (
                room_id,
                password_hash,
                salt,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await db.commit()

    logger.info("Room creee : %s (expire le %s)", room_id[:8], expires_at.strftime("%Y-%m-%d %H:%M:%S"))
    return room_id


async def get_room(room_id: str) -> dict | None:
    """
    Recupere les metadonnees d'une room par son identifiant.

    Returns:
        Dict avec cles id, password_hash, salt, created_at, expires_at,
        ou None si la room est introuvable ou expiree.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM rooms WHERE id = ? AND expires_at > ?",
            (room_id, now),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_room(room_id: str) -> None:
    """
    Supprime une room et toutes ses donnees (messages, fichiers).
    La suppression physique des fichiers est geree par cleanup.py.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        await db.commit()
    logger.info("Room detruite manuellement : %s", room_id[:8])


async def get_expired_rooms() -> list[str]:
    """
    Retourne les identifiants de toutes les rooms dont la date d'expiration est passee.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM rooms WHERE expires_at <= ?", (now,)
        )
        return [row[0] for row in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Gestion des messages
# ---------------------------------------------------------------------------

async def save_message(room_id: str, user_id: str, username: str, content: str) -> int:
    """
    Persiste un message chiffre dans la base.
    Le champ content contient le JSON AES-GCM {"iv":"..", "ct":".."} tel quel.

    Returns:
        L'identifiant auto-incremente du message insere.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            "INSERT INTO messages (room_id, user_id, username, content, sent_at) VALUES (?, ?, ?, ?, ?)",
            (room_id, user_id, username, content, now),
        )
        msg_id = cursor.lastrowid
        await db.commit()
    return msg_id


async def load_recent_messages(room_id: str, limit: int = 100) -> list[dict]:
    """
    Charge les N derniers messages d'une room, dans l'ordre chronologique.
    Le contenu reste chiffre - le serveur ne le dechiffre pas.

    Returns:
        Liste de dicts avec cles type, id, userId, username, content, time.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, username, content, sent_at
            FROM messages
            WHERE room_id = ?
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (room_id, limit),
        )
        rows = await cursor.fetchall()

    return [
        {
            "type":     "message",
            "id":       row["id"],
            "userId":   row["user_id"],
            "username": row["username"],
            "content":  row["content"],
            "time":     row["sent_at"][11:16],  # Extrait HH:MM depuis "YYYY-MM-DD HH:MM:SS"
        }
        for row in reversed(rows)
    ]


# ---------------------------------------------------------------------------
# Gestion des fichiers par room
# ---------------------------------------------------------------------------

async def register_file(room_id: str, filename: str) -> None:
    """Enregistre un fichier uploade dans la base pour une room donnee."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            "INSERT INTO room_files (room_id, filename, uploaded_at) VALUES (?, ?, ?)",
            (room_id, filename, now),
        )
        await db.commit()


async def list_room_files(room_id: str) -> list[str]:
    """Retourne la liste des noms de fichiers associes a une room."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT filename FROM room_files WHERE room_id = ? ORDER BY uploaded_at",
            (room_id,),
        )
        return [row[0] for row in await cursor.fetchall()]


async def get_room_file_names(room_id: str) -> list[str]:
    """Alias de list_room_files pour la coherence des noms."""
    return await list_room_files(room_id)
