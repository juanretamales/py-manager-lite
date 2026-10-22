"""Pruebas unitarias para seguridad criptográfica, almacenamiento de credenciales y Turso Cloud (Fase 5).

Verifica:
1. Derivación de claves PBKDF2 HMAC-SHA256 con salt criptográfico.
2. Cifrado simétrico autenticado AES-256-GCM (AEAD), detección de manipulación y enmascaramiento.
3. Almacenamiento seguro en profile.json y ciclo de vida de credenciales de Turso Cloud.
4. Servicio TursoCloudService: diagnóstico, normalización de URLs y manejo de errores.
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.security import (
    hash_credential,
    verify_credential,
    encrypt_secret,
    decrypt_secret,
    mask_secret,
)
from app.core.config import normalize_turso_url
from app.services.auth_service import AuthService
from app.services.turso_cloud_service import TursoCloudService


class TestSecurityAndTursoCloud(unittest.TestCase):
    """Suite de pruebas para seguridad de credenciales y Turso Cloud."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.profile_path = Path(self.test_dir) / "profile.json"
        self.auth_service = AuthService(profile_path=self.profile_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pbkdf2_hash_and_verify(self) -> None:
        """Verifica que el hash PBKDF2 sea irreversible, único por salt y verificable en tiempo constante."""
        secret = "MasterPassword2026!"
        h1, s1 = hash_credential(secret)
        h2, s2 = hash_credential(secret)

        # Salto aleatorio garantiza hashes diferentes para el mismo secreto
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)

        # Verificación exitosa con los salts respectivos
        self.assertTrue(verify_credential(secret, h1, s1))
        self.assertTrue(verify_credential(secret, h2, s2))

        # Falla con secreto incorrecto o salt alterado
        self.assertFalse(verify_credential("WrongPassword", h1, s1))
        self.assertFalse(verify_credential(secret, h1, s2))

    def test_aes_gcm_encrypt_decrypt_lifecycle(self) -> None:
        """Verifica el cifrado reversible AES-256-GCM con salt y nonce aleatorios."""
        raw_token = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.test-turso-token-secret-12345"
        envelope1 = encrypt_secret(raw_token, context="turso_auth")
        envelope2 = encrypt_secret(raw_token, context="turso_auth")

        # Dos cifrados del mismo texto producen sobres diferentes debido a salt y nonce aleatorios
        self.assertNotEqual(envelope1, envelope2)
        self.assertTrue(envelope1.startswith("enc:v1:aes-gcm:"))
        self.assertTrue(envelope2.startswith("enc:v1:aes-gcm:"))

        # Descifrado fiel
        self.assertEqual(decrypt_secret(envelope1, context="turso_auth"), raw_token)
        self.assertEqual(decrypt_secret(envelope2, context="turso_auth"), raw_token)

        # Texto vacío devuelve vacío
        self.assertEqual(encrypt_secret(""), "")
        self.assertEqual(decrypt_secret(""), "")

    def test_aes_gcm_tamper_resistance(self) -> None:
        """Verifica que cualquier manipulación del sobre criptográfico sea rechazada por AEAD."""
        raw_token = "secret-token-payload"
        envelope = encrypt_secret(raw_token, context="turso_auth")
        parts = envelope.split(":")

        # Manipular ciphertext
        corrupted_ct = parts[5][:-2] + ("00" if parts[5][-2:] != "00" else "ff")
        corrupted_envelope = f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{parts[4]}:{corrupted_ct}"

        with self.assertRaises(ValueError):
            decrypt_secret(corrupted_envelope, context="turso_auth")

        # Intentar descifrar con contexto no coincidente
        with self.assertRaises(ValueError):
            decrypt_secret(envelope, context="otro_contexto")

    def test_mask_secret(self) -> None:
        """Verifica el enmascaramiento seguro de tokens para visualización."""
        token = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.abc123xyz"
        masked = mask_secret(token, visible_prefix=6, visible_suffix=4)
        self.assertTrue(masked.startswith("eyJhbG..."))
        self.assertTrue(masked.endswith("3xyz"))
        self.assertNotIn("test", masked)
        self.assertEqual(mask_secret(""), "")
        self.assertEqual(mask_secret("short"), "•••••")

    def test_profile_stores_only_encrypted_turso_token(self) -> None:
        """Verifica que el archivo profile.json guarde el token cifrado y nunca en texto plano."""
        self.auth_service.create_profile(
            user_name="admin",
            company_name="Mi Empresa SpA",
            password="Password123",
            pin="1234",
            turso_cloud_url="libsql://empresa-turso.turso.io",
            turso_auth_token="super_secret_token_never_plaintext_on_disk",
        )

        # Inspección directa del archivo JSON en disco
        with open(self.profile_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # El token en texto plano NO debe existir en el JSON
        self.assertNotIn("turso_auth_token", raw_data)
        self.assertIn("turso_auth_token_encrypted", raw_data)
        self.assertTrue(raw_data["turso_auth_token_encrypted"].startswith("enc:v1:aes-gcm:"))
        self.assertNotIn("super_secret_token_never_plaintext_on_disk", json.dumps(raw_data))

        # La lectura a través de AuthService descifra correctamente en memoria
        url, decrypted_token = self.auth_service.get_turso_credentials()
        self.assertEqual(url, "libsql://empresa-turso.turso.io")
        self.assertEqual(decrypted_token, "super_secret_token_never_plaintext_on_disk")

        # Profile info muestra has_turso_token=True y valor enmascarado
        info = self.auth_service.get_profile_info()
        self.assertIsNotNone(info)
        self.assertTrue(info["has_turso_token"])
        self.assertTrue(info["has_turso_cloud"])
        self.assertIn("...", info["turso_token_masked"])

    def test_update_turso_config_encryption(self) -> None:
        """Verifica la actualización y eliminación de credenciales de Turso Cloud en profile."""
        self.auth_service.create_profile(
            user_name="admin",
            company_name="Empresa",
            password="Password123",
            pin="1234",
        )

        # Inicialmente sin Turso
        self.assertEqual(self.auth_service.get_turso_credentials(), ("", ""))

        # Actualizar credenciales
        self.auth_service.update_turso_config(
            cloud_url="https://nueva-bd.turso.io",
            auth_token="token_nuevo_cifrado",
        )
        url, token = self.auth_service.get_turso_credentials()
        self.assertEqual(url, "https://nueva-bd.turso.io")
        self.assertEqual(token, "token_nuevo_cifrado")

        # Limpiar credenciales
        self.auth_service.update_turso_config(cloud_url="", auth_token="")
        url_empty, token_empty = self.auth_service.get_turso_credentials()
        self.assertEqual(url_empty, "")
        self.assertEqual(token_empty, "")

    def test_normalize_turso_url(self) -> None:
        """Verifica la normalización de protocolos de URL para Turso (libsql:// a https://)."""
        self.assertEqual(
            normalize_turso_url("libsql://demo.turso.io", force_https=True),
            "https://demo.turso.io",
        )
        self.assertEqual(
            normalize_turso_url("https://demo.turso.io", force_https=True),
            "https://demo.turso.io",
        )
        self.assertEqual(
            normalize_turso_url("libsql://demo.turso.io", force_https=False),
            "libsql://demo.turso.io",
        )

    def test_turso_cloud_service_diagnostics(self) -> None:
        """Verifica el diagnóstico de conexión de TursoCloudService ante credenciales ausentes o simuladas."""
        svc = TursoCloudService(auth_service=self.auth_service)
        self.assertFalse(svc.is_configured())

        # Sin configuración retorna mensaje amigable sin explotar
        res = svc.test_connection(url="", token="")
        self.assertFalse(res["connected"])
        self.assertIn("Falta ingresar la URL", res["message"])

        res2 = svc.test_connection(url="libsql://demo.turso.io", token="")
        self.assertFalse(res2["connected"])
        self.assertIn("Falta ingresar el Token", res2["message"])

        # Con cliente mock simulando conexión exitosa
        with patch.object(svc, "get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.execute.side_effect = [
                MagicMock(rows=[(1,)]),  # SELECT 1
                MagicMock(rows=[(8,)]),  # SELECT count(*)
            ]
            mock_get_client.return_value = mock_client

            conn_res = svc.test_connection(url="https://demo.turso.io", token="dummy-token")
            self.assertTrue(conn_res["connected"])
            self.assertEqual(conn_res["table_count"], 8)
            self.assertGreater(conn_res["latency_ms"], 0.0)
            mock_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
