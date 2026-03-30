"""
Utilitaires d'authentification : hachage de mots de passe et tokens de session.
Utilise exclusivement la bibliotheque standard Python (hashlib, hmac, secrets).

Hachage : scrypt(n=2^15, r=8, p=1) avec sel aleatoire 16 octets.
Tokens   : base64url(payload_json).hmac_sha256_hex
"""
import base64
import hashlib
import hmac
import json
import os
import time

from config import SECRET_KEY, SESSION_EXPIRY_HOURS


def hash_password(password: str) -> str:
    """
    Hache un mot de passe avec scrypt et un sel aleatoire.

    Returns:
        Chaine au format "sel_hex$hash_hex" a stocker en base.
    """
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2 ** 14,
        r=8,
        p=1,
        dklen=32,
    )
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    """
    Verifie un mot de passe contre un hash stocke au format "sel_hex$hash_hex".
    La comparaison est effectuee en temps constant pour prevenir les attaques temporelles.

    Args:
        password: Mot de passe en clair fourni par l'utilisateur.
        stored:   Hash stocke en base, format "sel_hex$hash_hex".

    Returns:
        True si le mot de passe correspond, False sinon.
    """
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2 ** 14,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_token(user_id: str, room_id: str, username: str) -> str:
    """
    Cree un token de session signe avec HMAC-SHA256.

    Format : base64url(payload_json).signature_hex
    Le token expire apres SESSION_EXPIRY_HOURS heures.

    Args:
        user_id:  Identifiant unique de l'utilisateur.
        room_id:  Identifiant de la room.
        username: Nom d'affichage de l'utilisateur.

    Returns:
        Token de session opaque sous forme de chaine.
    """
    payload = {
        "uid": user_id,
        "rid": room_id,
        "usr": username,
        "exp": int(time.time()) + SESSION_EXPIRY_HOURS * 3600,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )
    sig = hmac.new(
        SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> dict | None:
    """
    Verifie et decode un token de session.

    Controles effectues :
    - Signature HMAC valide (comparaison en temps constant)
    - Token non expire

    Args:
        token: Token brut fourni par le client.

    Returns:
        Payload dict avec cles "uid", "rid", "usr", "exp" si valide,
        None si invalide ou expire.
    """
    try:
        payload_b64, sig = token.rsplit(".", 1)

        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Comparaison en temps constant pour eviter les attaques par oracle temporel
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Restaure le padding base64 supprime a la creation
        padding = (4 - len(payload_b64) % 4) % 4
        payload = json.loads(
            base64.urlsafe_b64decode(payload_b64 + "=" * padding)
        )

        if int(time.time()) > payload["exp"]:
            return None

        return payload
    except Exception:
        return None
