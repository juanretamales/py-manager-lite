import os
import sys
from typing import Optional
from pathlib import Path

# Base directories
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DOCUMENTS_DIR = BASE_DIR / "documents"
TMP_DIR = BASE_DIR / "tmp"
PROFILE_DIR = TMP_DIR / "profile"
PROFILE_FILE = PROFILE_DIR / "profile.json"
AI_CONFIG_FILE = PROFILE_DIR / "ai_config.json"
CURRENCY_CONFIG_FILE = PROFILE_DIR / "currency_config.json"


def get_storage_path_from_profile() -> Path:
    """Obtiene la ruta de almacenamiento configurada en profile.json o retorna la ruta por defecto."""
    if PROFILE_FILE.exists():
        try:
            import json
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_path = data.get("storage_path")
                if custom_path and str(custom_path).strip():
                    p = Path(custom_path).resolve()
                    p.mkdir(parents=True, exist_ok=True)
                    return p
        except Exception:
            pass
    return DEFAULT_DOCUMENTS_DIR


DOCUMENTS_DIR = get_storage_path_from_profile()
BACKUPS_DIR = DOCUMENTS_DIR / "backups"
SAFETY_BACKUPS_DIR = PROFILE_DIR / "backups_safety"


def ensure_storage_directories(base_dir: Optional[Path] = None) -> None:
    """Asegura la estructura completa de carpetas de almacenamiento para documentos comerciales."""
    target = (base_dir or DOCUMENTS_DIR).resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "quotes").mkdir(parents=True, exist_ok=True)
    (target / "purchase_orders").mkdir(parents=True, exist_ok=True)
    (target / "invoices" / "issued").mkdir(parents=True, exist_ok=True)
    (target / "invoices" / "received").mkdir(parents=True, exist_ok=True)
    (target / "payments").mkdir(parents=True, exist_ok=True)
    (target / "exports").mkdir(parents=True, exist_ok=True)
    (target / "backups").mkdir(parents=True, exist_ok=True)


def get_documents_dir() -> Path:
    """Retorna la ruta actual de la carpeta de documentos y almacenamiento."""
    return DOCUMENTS_DIR


def set_documents_dir(new_path: Path) -> Path:
    """Actualiza la ruta activa de almacenamiento en memoria y crea sus subdirectorios."""
    global DOCUMENTS_DIR, BACKUPS_DIR
    resolved = new_path.resolve()
    DOCUMENTS_DIR = resolved
    BACKUPS_DIR = DOCUMENTS_DIR / "backups"
    ensure_storage_directories(DOCUMENTS_DIR)
    return DOCUMENTS_DIR


# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
SAFETY_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
ensure_storage_directories(DOCUMENTS_DIR)

# DECISIÓN DE NEGOCIO: La base de datos local y el perfil residen en tmp/profile/
# para mantener la portabilidad del entorno de usuario antes de moverlo a su destino definitivo.
TURSO_DB_PATH = PROFILE_DIR / "turso_manager.db"

# DECISIÓN DE ARQUITECTURA: Migración automática y no destructiva de la BD SQLite previa a Turso/LibSQL local
LEGACY_DB_PATH = DATA_DIR / "py-manager.db"
if LEGACY_DB_PATH.exists() and not TURSO_DB_PATH.exists():
    try:
        import shutil
        shutil.copy2(LEGACY_DB_PATH, TURSO_DB_PATH)
    except Exception:
        pass

DB_PATH = TURSO_DB_PATH
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")


def normalize_turso_url(url: str, force_https: bool = True) -> str:
    """Normaliza una URL de Turso (libsql:// o https://) para compatibilidad con el cliente HTTP/LibSQL."""
    clean = url.strip()
    if force_https and clean.startswith("libsql://"):
        return clean.replace("libsql://", "https://", 1)
    return clean


def get_turso_cloud_config() -> dict:
    """Retorna la configuración de Turso Cloud (URL y token descifrado) desde profile.json o variables de entorno."""
    from app.services.auth_service import AuthService
    auth_svc = AuthService()
    url, token = auth_svc.get_turso_credentials()
    return {
        "url": url,
        "url_normalized": normalize_turso_url(url) if url else "",
        "token": token,
        "has_cloud": bool(url and token),
    }


# App Metadata
APP_TITLE = "py-manager-lite"
APP_VERSION = "0.1.0-poc"
DEFAULT_TAX_RATE = 0.19  # 19% IVA estándar
