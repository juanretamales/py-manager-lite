"""Servicio de autenticación, perfil de usuario y gestión de credenciales.

Maneja el almacenamiento seguro (PBKDF2 HMAC SHA-256) de contraseñas y PIN de desbloqueo,
así como la persistencia del perfil y la configuración de Turso Cloud en la carpeta profile.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Callable
from app.core.config import (
    PROFILE_FILE,
    PROFILE_DIR,
    DEFAULT_DOCUMENTS_DIR,
    get_documents_dir,
    set_documents_dir,
    ensure_storage_directories,
)
from app.core.security import (
    hash_credential as _hash_credential,
    verify_credential as _verify_credential,
    encrypt_secret,
    decrypt_secret,
    mask_secret,
)


class AuthService:

    """Gestiona el ciclo de vida del perfil del usuario, credenciales y conexión a Turso."""

    def __init__(self, profile_path=PROFILE_FILE) -> None:
        self.profile_path = profile_path

    def is_profile_configured(self) -> bool:
        """Determina si ya existe un perfil creado en la carpeta profile."""
        if not self.profile_path.exists():
            return False
        try:
            data = self._read_raw_profile()
            return bool(data.get("password_hash") and data.get("pin_hash"))
        except Exception:
            return False

    def create_profile(
        self,
        user_name: str,
        company_name: str,
        password: str,
        pin: str,
        storage_path: Optional[str] = None,
        turso_cloud_url: Optional[str] = None,
        turso_auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crea el perfil inicial de usuario con contraseña maestra, PIN y carpeta de almacenamiento.

        Args:
            user_name: Nombre o identificador del usuario administrador.
            company_name: Nombre de la empresa o negocio.
            password: Contraseña maestra (mínimo 6 caracteres).
            pin: PIN numérico de 4 a 6 dígitos.
            storage_path: Ruta de almacenamiento de archivos y documentos (local o nube).
            turso_cloud_url: URL opcional de Turso Cloud para sincronización.
            turso_auth_token: Token de autenticación de Turso (se almacena cifrado con AES-256-GCM).

        Returns:
            Diccionario con los datos públicos del perfil recién creado.
        """
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        chosen_storage = storage_path.strip() if storage_path and storage_path.strip() else str(DEFAULT_DOCUMENTS_DIR)
        set_documents_dir(Path(chosen_storage))

        pwd_hash, pwd_salt = _hash_credential(password)
        pin_hash, pin_salt = _hash_credential(pin)
        now_iso = datetime.now().isoformat()

        clean_turso_url = turso_cloud_url.strip() if turso_cloud_url else ""
        profile_data = {
            "user_name": user_name.strip(),
            "company_name": company_name.strip(),
            "storage_path": chosen_storage,
            "password_hash": pwd_hash,
            "password_salt": pwd_salt,
            "pin_hash": pin_hash,
            "pin_salt": pin_salt,
            "turso_cloud_url": clean_turso_url,
            "created_at": now_iso,
            "last_login": now_iso,
        }

        # DECISIÓN DE SEGURIDAD: El token de Turso se cifra con AES-256-GCM y salt criptográfico único
        if turso_auth_token and turso_auth_token.strip():
            profile_data["turso_auth_token_encrypted"] = encrypt_secret(
                turso_auth_token.strip(), context="turso_auth"
            )

        self._write_raw_profile(profile_data)
        return self.get_profile_info() or {}

    def verify_password(self, password: str) -> bool:
        """Valida la contraseña maestra del perfil."""
        data = self._read_raw_profile()
        pwd_hash = data.get("password_hash")
        pwd_salt = data.get("password_salt")
        if not pwd_hash or not pwd_salt:
            return False

        is_valid = _verify_credential(password, pwd_hash, pwd_salt)
        if is_valid:
            self._update_last_login()
        return is_valid

    def verify_pin(self, pin: str) -> bool:
        """Valida el PIN de desbloqueo rápido del perfil."""
        data = self._read_raw_profile()
        pin_hash = data.get("pin_hash")
        pin_salt = data.get("pin_salt")
        if not pin_hash or not pin_salt:
            return False

        is_valid = _verify_credential(pin, pin_hash, pin_salt)
        if is_valid:
            self._update_last_login()
        return is_valid

    def get_profile_info(self) -> Optional[Dict[str, Any]]:
        """Retorna información descriptiva del perfil sin exponer hashes ni tokens sin cifrar."""
        if not self.profile_path.exists():
            return None
        try:
            data = self._read_raw_profile()
            url, token = self.get_turso_credentials()
            return {
                "user_name": data.get("user_name", "Usuario"),
                "company_name": data.get("company_name", ""),
                "storage_path": data.get("storage_path", str(get_documents_dir())),
                "turso_cloud_url": url,
                "has_turso_cloud": bool(url),
                "has_turso_token": bool(token),
                "turso_token_masked": mask_secret(token) if token else "",
                "created_at": data.get("created_at"),
                "last_login": data.get("last_login"),
            }
        except Exception:
            return None

    def get_turso_credentials(self, allow_env_fallback: bool = True) -> Tuple[str, str]:
        """Obtiene la URL y el token descifrado de Turso Cloud desde profile.json o variables de entorno.

        Returns:
            Tupla (turso_cloud_url, turso_auth_token).
        """
        data = self._read_raw_profile()
        url = data.get("turso_cloud_url", "").strip()
        enc_token = data.get("turso_auth_token_encrypted") or ""
        token = ""
        if enc_token:
            try:
                token = decrypt_secret(enc_token, context="turso_auth")
            except Exception:
                token = ""

        # Fallback a variables de entorno / archivo .env si es el perfil principal de la app y no tiene credenciales
        if allow_env_fallback and self.profile_path == PROFILE_FILE:
            if not url:
                url = os.getenv("DATABASE_TURSO_URL") or os.getenv("database_turso_url") or ""
            if not token:
                token = os.getenv("DATABASE_TURSO_TOKEN") or os.getenv("database_turso_token") or ""

            if (not url or not token) and Path(".env").exists():
                try:
                    with open(".env", "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or " = " not in line:
                                continue
                            k, v = line.split(" = ", 1)
                            k = k.strip()
                            v = v.strip()
                            if not url and k.lower() == "database_turso_url":
                                url = v
                            if not token and k.lower() == "database_turso_token":
                                token = v
                except Exception:
                    pass

        return url.strip(), token.strip()

    def update_pin(self, master_password: str, new_pin: str) -> bool:

        """Actualiza el PIN numérico tras validar la contraseña maestra."""
        if not self.verify_password(master_password):
            return False

        data = self._read_raw_profile()
        pin_hash, pin_salt = _hash_credential(new_pin)
        data["pin_hash"] = pin_hash
        data["pin_salt"] = pin_salt
        self._write_raw_profile(data)
        return True

    def update_password(self, current_password: str, new_password: str) -> bool:
        """Actualiza la contraseña maestra tras validar la actual."""
        if not self.verify_password(current_password):
            return False

        data = self._read_raw_profile()
        pwd_hash, pwd_salt = _hash_credential(new_password)
        data["password_hash"] = pwd_hash
        data["password_salt"] = pwd_salt
        self._write_raw_profile(data)
        return True

    def update_turso_config(self, cloud_url: str, auth_token: str) -> None:
        """Actualiza las credenciales de Turso Cloud cifrando el token con AES-256-GCM y salt."""
        data = self._read_raw_profile()
        clean_url = cloud_url.strip()
        clean_token = auth_token.strip()

        data["turso_cloud_url"] = clean_url
        if clean_token:
            data["turso_auth_token_encrypted"] = encrypt_secret(clean_token, context="turso_auth")
            data.pop("turso_auth_token", None)
        elif not clean_url:
            data["turso_cloud_url"] = ""
            data.pop("turso_auth_token_encrypted", None)
            data.pop("turso_auth_token", None)

        self._write_raw_profile(data)

    def migrate_storage_path(
        self,
        new_path_str: str,
        move_existing: bool = True,
        progress_callback: Optional[Callable[[float, Optional[str], Optional[str]], None]] = None,
    ) -> Dict[str, Any]:
        """Cambia la ubicación de los archivos de almacenamiento y migra opcionalmente los datos existentes.

        # DECISIÓN DE NEGOCIO: Permite que los usuarios elijan una carpeta en la nube (Dropbox,
        # Google Drive, OneDrive o Nextcloud) y deleguen la sincronización a la app de escritorio,
        # actualizando automáticamente las referencias documentales en la base de datos local.
        """
        clean_new = new_path_str.strip()
        if not clean_new:
            raise ValueError("La nueva ruta de almacenamiento no puede estar vacía.")

        if progress_callback:
            progress_callback(0.05, "Comprobando...", f"Verificando ruta de destino: {clean_new}")

        new_path = Path(clean_new).resolve()
        old_path = get_documents_dir().resolve()

        ensure_storage_directories(new_path)
        files_moved = 0

        if move_existing and old_path != new_path and old_path.exists():
            if progress_callback:
                progress_callback(0.15, "Comprobando...", "Escaneando archivos en la carpeta de origen...")

            all_items = [item for item in old_path.rglob("*") if item.is_file()]
            total_items = len(all_items)

            if progress_callback:
                progress_callback(
                    0.20,
                    "Cargando para mejorar la experiencia de usuario...",
                    f"Se encontraron {total_items} archivos para transferir."
                )

            for idx, item in enumerate(all_items, start=1):
                rel = item.relative_to(old_path)
                dest = new_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                files_moved += 1

                if progress_callback:
                    # Rango de 20% a 80% proporcional al copiado de archivos
                    pct = 0.20 + 0.60 * (idx / total_items) if total_items > 0 else 0.80
                    progress_callback(
                        pct,
                        f"Moviendo archivos ({idx}/{total_items})...",
                        f"Copiado: {rel}"
                    )

            # Actualizar referencias de documentos en la base de datos
            old_prefix = str(old_path)
            new_prefix = str(new_path)
            if progress_callback:
                progress_callback(
                    0.85,
                    "Afinando para el perfil del usuario...",
                    "Actualizando referencias documentales en la base de datos..."
                )

            try:
                from app.db.session import get_db_session
                from app.models.invoice import Invoice, InvoicePayment, PurchaseOrder
                with get_db_session() as session:
                    for inv in session.query(Invoice).filter(Invoice.document_path.isnot(None)).all():
                        if inv.document_path and inv.document_path.startswith(old_prefix):
                            inv.document_path = inv.document_path.replace(old_prefix, new_prefix, 1)
                    for pay in session.query(InvoicePayment).filter(InvoicePayment.voucher_path.isnot(None)).all():
                        if pay.voucher_path and pay.voucher_path.startswith(old_prefix):
                            pay.voucher_path = pay.voucher_path.replace(old_prefix, new_prefix, 1)
                    for po in session.query(PurchaseOrder).filter(PurchaseOrder.document_path.isnot(None)).all():
                        if po.document_path and po.document_path.startswith(old_prefix):
                            po.document_path = po.document_path.replace(old_prefix, new_prefix, 1)
                    session.commit()
            except Exception:
                pass

        # Persistir la nueva ruta en profile.json y actualizar en memoria
        if progress_callback:
            progress_callback(
                0.95,
                "Afinando para el perfil del usuario...",
                "Guardando configuración de ruta en profile.json..."
            )

        data = self._read_raw_profile()
        data["storage_path"] = str(new_path)
        self._write_raw_profile(data)
        set_documents_dir(new_path)

        if progress_callback:
            progress_callback(
                1.0,
                "¡Archivos migrados exitosamente!",
                f"Proceso finalizado. Total de {files_moved} archivos movidos a {new_path.name}."
            )

        return {
            "success": True,
            "old_path": str(old_path),
            "new_path": str(new_path),
            "files_moved": files_moved,
        }

    def _update_last_login(self) -> None:
        """Registra la marca de tiempo del último inicio de sesión exitoso."""
        try:
            data = self._read_raw_profile()
            data["last_login"] = datetime.now().isoformat()
            self._write_raw_profile(data)
        except Exception:
            pass

    def _read_raw_profile(self) -> Dict[str, Any]:
        """Lee el archivo JSON del perfil y migra cualquier token en texto plano a formato cifrado."""
        if not self.profile_path.exists():
            return {}
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # DECISIÓN DE SEGURIDAD: Si existe token heredado en texto plano, cifrarlo con AES-256-GCM y guardarlo
            legacy_token = data.pop("turso_auth_token", None)
            if legacy_token and str(legacy_token).strip() and "turso_auth_token_encrypted" not in data:
                data["turso_auth_token_encrypted"] = encrypt_secret(
                    str(legacy_token).strip(), context="turso_auth"
                )
                self._write_raw_profile(data)
            return data
        except Exception:
            return {}

    def _write_raw_profile(self, data: Dict[str, Any]) -> None:
        """Guarda atómicamente el archivo JSON del perfil."""
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
