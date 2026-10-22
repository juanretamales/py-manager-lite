"""Módulo central de criptografía y seguridad para py-manager-lite.

Implementa:
1. Hash irreversible con salt criptográfico (PBKDF2 HMAC-SHA256, 100k iteraciones) para contraseñas y PIN.
2. Cifrado simétrico autenticado (AES-256-GCM AEAD) con derivación de claves mediante PBKDF2 y salt aleatorio
   para credenciales reversibles como tokens de acceso a bases de datos en la nube (Turso / libSQL).
3. Enmascaramiento visual de secretos para interfaces de usuario.
"""

import os
import hmac
import hashlib
import platform
import getpass
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# DECISIÓN DE ARQUITECTURA (Criptografía Estándar):
# PBKDF2 con SHA-256 y 100.000 iteraciones proporciona protección contra ataques de fuerza bruta
# y ataques de diccionario con hardware acelerado (GPU/ASIC).
PBKDF2_ITERATIONS = 100_000

# Semilla de derivación interna de la aplicación para ligar el cifrado a la instalación local
APP_MASTER_SALT = b"py-manager-lite::v1::cloud-token-vault-entropy"


def hash_credential(secret: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Genera el hash PBKDF2 de una credencial con salt criptográfico.

    Args:
        secret: Cadena en texto plano (contraseña maestra o PIN).
        salt: Salt de 16 bytes. Si es None, se genera uno nuevo aleatoriamente.

    Returns:
        Tupla con (hash_hexadecimal, salt_hexadecimal).
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def verify_credential(secret: str, expected_hash_hex: str, salt_hex: str) -> bool:
    """Verifica si un secreto coincide con su hash esperado utilizando tiempo constante.

    Args:
        secret: Texto plano a verificar.
        expected_hash_hex: Hash hexadecimal almacenado en profile.json.
        salt_hex: Salt hexadecimal almacenado.

    Returns:
        True si coincide, False en caso contrario.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        computed_hash_hex, _ = hash_credential(secret, salt)
        # DECISIÓN DE SEGURIDAD: compare_digest previene ataques de temporización (timing attacks).
        return hmac.compare_digest(computed_hash_hex, expected_hash_hex)
    except Exception:
        return False


def _get_system_fingerprint() -> bytes:
    """Obtiene una huella del sistema y usuario local para vincular las claves al dispositivo."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "default_user"
    node = platform.node() or "local_node"
    fingerprint_raw = f"{user}::{node}::{APP_MASTER_SALT.decode('ascii', errors='ignore')}"
    return fingerprint_raw.encode("utf-8")


def derive_encryption_key(salt: bytes, context: str = "turso_auth") -> bytes:
    """Deriva una clave simétrica de 256 bits (32 bytes) usando PBKDF2-HMAC-SHA256 y un salt aleatorio.

    Args:
        salt: Salt aleatorio de 16 bytes único por cifrado.
        context: Contexto o propósito de la clave para separación de dominios criptográficos.

    Returns:
        Clave derivada de 32 bytes para AES-256-GCM.
    """
    seed = _get_system_fingerprint() + context.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", seed, salt, PBKDF2_ITERATIONS, dklen=32)


def encrypt_secret(plaintext: str, context: str = "turso_auth") -> str:
    """Cifra un secreto (ej. token de Turso) utilizando AES-256-GCM con un salt aleatorio nuevo.

    # DECISIÓN DE SEGURIDAD: Los tokens de bases de datos remotas dan acceso completo de lectura y
    # escritura. Guardarlos en texto plano en profile.json es una vulnerabilidad crítica. Mediante
    # AES-256-GCM con salt aleatorio e IV único, el archivo profile.json puede respaldarse o inspeccionarse
    # sin comprometer el acceso a la base de datos remota.

    Args:
        plaintext: Texto plano del token o credencial a proteger.
        context: Nombre del contexto para separación criptográfica.

    Returns:
        Sobre criptográfico con formato: 'enc:v1:aes-gcm:<salt_hex>:<nonce_hex>:<ciphertext_hex>'
    """
    if not plaintext:
        return ""

    salt = os.urandom(16)
    nonce = os.urandom(12)  # Nonce de 96 bits recomendado para AES-GCM
    key = derive_encryption_key(salt, context=context)

    aesgcm = AESGCM(key)
    # AAD (Additional Authenticated Data): Vincula el contexto a la autenticidad del mensaje
    aad = context.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

    return f"enc:v1:aes-gcm:{salt.hex()}:{nonce.hex()}:{ciphertext.hex()}"


def decrypt_secret(envelope: str, context: str = "turso_auth") -> str:
    """Descifra un secreto protegido con 'encrypt_secret' verificando la autenticidad del sobre.

    Args:
        envelope: Cadena en formato 'enc:v1:aes-gcm:<salt_hex>:<nonce_hex>:<ciphertext_hex>'
                  o texto plano directo (para migración transparente de versiones previas).
        context: Contexto de cifrado esperado.

    Returns:
        Texto plano descifrado del secreto.

    Raises:
        ValueError: Si el formato del sobre es inválido o los datos fueron manipulados.
    """
    if not envelope:
        return ""

    # Soporte de migración transparente: si no tiene el prefijo de sobre, se asume texto plano legacy
    if not envelope.startswith("enc:v1:aes-gcm:"):
        return envelope

    parts = envelope.split(":")
    if len(parts) != 6:
        raise ValueError("El sobre criptográfico tiene un formato no reconocido.")

    try:
        salt = bytes.fromhex(parts[3])
        nonce = bytes.fromhex(parts[4])
        ciphertext = bytes.fromhex(parts[5])

        key = derive_encryption_key(salt, context=context)
        aesgcm = AESGCM(key)
        aad = context.encode("utf-8")
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        return decrypted_bytes.decode("utf-8")
    except Exception as ex:
        raise ValueError(f"Fallo en la autenticación o descifrado del secreto: {ex}") from ex


def mask_secret(secret: str, visible_prefix: int = 6, visible_suffix: int = 4) -> str:
    """Genera una representación enmascarada segura de un token o secreto para mostrar en la interfaz.

    Ejemplo: 'eyJhbGciOiJFZERT...3BQ' (muestra prefijo y sufijo protegiendo el cuerpo del token).
    """
    if not secret:
        return ""
    if len(secret) <= (visible_prefix + visible_suffix + 4):
        return "•" * len(secret)
    return f"{secret[:visible_prefix]}...{secret[-visible_suffix:]}"
