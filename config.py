"""
Configuration centrale de HChat.
Toutes les valeurs sont chargees depuis des variables d'environnement
avec des valeurs par defaut raisonnables. Copier .env.example en .env
pour personnaliser sans modifier le code.
"""
import os
from pathlib import Path

# Charge automatiquement le fichier .env si present (sans erreur si absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Serveur
# ---------------------------------------------------------------------------
PORT: int = int(os.environ.get("PORT", 5000))
HOST: str = os.environ.get("HOST", "0.0.0.0")
APP_NAME: str = os.environ.get("APP_NAME", "HChat")

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).parent
UPLOAD_DIR: Path = BASE_DIR / os.environ.get("UPLOAD_DIR", "uploads")
DATA_DIR: Path = BASE_DIR / os.environ.get("DATA_DIR", "data")
STATIC_DIR: Path = BASE_DIR / "static"
DB_PATH: Path = DATA_DIR / "chat.db"

# ---------------------------------------------------------------------------
# Limites de contenu
# ---------------------------------------------------------------------------
# Taille maximale d'un fichier uploade (en octets)
MAX_UPLOAD_SIZE: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 10)) * 1024 * 1024
# Taille maximale d'un message WebSocket (en octets)
MAX_MESSAGE_SIZE: int = int(os.environ.get("MAX_MESSAGE_SIZE_KB", 64)) * 1024
# Nombre de messages charges depuis la BDD pour les nouveaux connectes
MAX_HISTORY: int = int(os.environ.get("MAX_HISTORY", 100))

# ---------------------------------------------------------------------------
# Extensions de fichiers autorisees a l'upload
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS: frozenset = frozenset(
    os.environ.get(
        "ALLOWED_EXTENSIONS",
        "pdf,xlsx,xls,docx,doc,txt,png,jpg,jpeg,gif,webp,zip,csv,md,py,js,ts,json"
    ).split(",")
)

# ---------------------------------------------------------------------------
# Rate limiting (fenetre glissante par userId)
# ---------------------------------------------------------------------------
RATE_LIMIT_MESSAGES: int = int(os.environ.get("RATE_LIMIT_MESSAGES", 30))
RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", 60))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE: str = os.environ.get("LOG_FILE", "chat.log")
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
