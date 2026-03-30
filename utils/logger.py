"""
Configuration centralisee du logger de l'application.
Ecrit simultanement dans la console (stdout) et dans un fichier
rotatif pour faciliter la supervision en production.
"""
import logging
import logging.handlers

from config import LOG_FILE, LOG_LEVEL, APP_NAME


def setup_logger() -> logging.Logger:
    """
    Cree et configure le logger principal de l'application.

    Format : [LEVEL] YYYY-MM-DD HH:MM:SS - module - message
    Le fichier est limite a 5 Mo avec 3 fichiers de rotation conserves.
    """
    logger = logging.getLogger(APP_NAME)

    # Evite d'ajouter des handlers en double si setup_logger est appele plusieurs fois
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler fichier rotatif (5 Mo max, 3 sauvegardes)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Impossible d'ouvrir le fichier de log '%s' : %s", LOG_FILE, exc)

    return logger


# Instance globale importable depuis tous les modules
logger: logging.Logger = setup_logger()
