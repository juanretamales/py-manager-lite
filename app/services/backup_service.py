"""Servicio de Respaldo, Exportación e Importación de Base de Datos para Turso / LibSQL.

Permite exportar e importar la base de datos completa en formato Turso (.db binario y .sql para Turso Cloud CLI),
así como paquetes completos (.zip) con configuraciones y respaldos de seguridad automáticos antes de restaurar.
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import os
import shutil
import sqlite3
import zipfile
import json
from datetime import datetime

from app.core.config import (
    DB_PATH,
    SAFETY_BACKUPS_DIR,
    PROFILE_FILE,
    AI_CONFIG_FILE,
    CURRENCY_CONFIG_FILE,
    DATABASE_URL,
    APP_VERSION,
    get_documents_dir,
)
from app.db.session import SessionLocal, engine, configure_db, init_db


class BackupService:
    """Gestiona el respaldo, volcado SQL, empaquetado e importación de la base de datos Turso."""

    def __init__(self, backups_dir: Optional[Path] = None, safety_dir: Optional[Path] = None) -> None:
        self._custom_backups_dir = backups_dir
        self.safety_dir = safety_dir or SAFETY_BACKUPS_DIR
        self.safety_dir.mkdir(parents=True, exist_ok=True)
        if self._custom_backups_dir:
            self._custom_backups_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backups_dir(self) -> Path:
        """Retorna la carpeta activa de respaldos."""
        if self._custom_backups_dir:
            return self._custom_backups_dir
        p = get_documents_dir() / "backups"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_database_summary(self, target_db_path: Optional[Path] = None) -> Dict[str, Any]:
        """Obtiene un resumen cuantitativo y estado de integridad de la base de datos indicada o actual.

        # DECISIÓN DE ARQUITECTURA: La inspección se realiza con sqlite3 nativo para no interferir
        # con el pool de conexiones de SQLAlchemy durante operaciones de respaldo o diagnóstico.
        """
        db_file = target_db_path or DB_PATH
        if not db_file.exists():
            return {
                "exists": False,
                "path": str(db_file),
                "size_kb": 0.0,
                "integrity": "MISSING",
                "counts": {},
            }

        size_kb = round(os.path.getsize(db_file) / 1024, 2)
        counts: Dict[str, int] = {}
        integrity = "UNKNOWN"

        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # Verificación de integridad SQLite/LibSQL
            cursor.execute("PRAGMA quick_check")
            check_result = cursor.fetchone()
            integrity = check_result[0] if check_result else "UNKNOWN"

            # Consulta de tablas estándar del sistema
            tables = [
                ("clients", "Clientes"),
                ("quotes", "Cotizaciones"),
                ("quote_items", "Partidas de Cotización"),
                ("projects", "Proyectos"),
                ("invoices", "Facturas"),
                ("invoice_payments", "Pagos de Facturas"),
                ("purchase_orders", "Órdenes de Compra"),
                ("company", "Perfil Empresa"),
                ("business_canvas", "Business Canvas"),
            ]

            for table_name, display_name in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    counts[display_name] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    # La tabla puede no existir si la base de datos es parcial o previa
                    counts[display_name] = 0

            cursor.close()
            conn.close()
        except Exception as ex:
            integrity = f"ERROR: {str(ex)}"

        return {
            "exists": True,
            "path": str(db_file),
            "size_kb": size_kb,
            "integrity": integrity,
            "counts": counts,
        }

    def export_turso_db(
        self,
        destination_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float, Optional[str], Optional[str]], None]] = None,
    ) -> str:
        """Exporta una copia atómica exacta de la base de datos en formato binario Turso / LibSQL (.db).

        # DECISIÓN DE ARQUITECTURA: Se utiliza la API Online Backup de SQLite (conn.backup),
        # lo que asegura una copia coherente punto-en-el-tiempo sin necesidad de bloquear lecturas.
        # El archivo resultante es 100% compatible con el comando `turso db create <db> --from-file <file.db>`.
        """
        dest_dir = destination_dir or self.backups_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"turso_backup_{ts}.db"

        target_file = dest_dir / filename

        if progress_callback:
            progress_callback(0.15, "Comprobando...", "Comprobando conexión a la base de datos Turso...")

        src_conn = sqlite3.connect(str(DB_PATH))
        dst_conn = sqlite3.connect(str(target_file))
        try:
            if progress_callback:
                progress_callback(
                    0.45,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Copiando páginas de base de datos de manera atómica..."
                )
            src_conn.backup(dst_conn)
            if progress_callback:
                progress_callback(
                    0.85,
                    "Afinando para el perfil del usuario...",
                    f"Verificando archivo exportado: {filename}..."
                )
        finally:
            dst_conn.close()
            src_conn.close()

        if progress_callback:
            progress_callback(
                1.0,
                "¡Base de datos exportada con éxito!",
                f"Respaldo generado en {target_file.name}."
            )

        return str(target_file)

    def export_turso_sql_dump(
        self,
        destination_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float, Optional[str], Optional[str]], None]] = None,
    ) -> str:
        """Genera un script de volcado SQL (.sql) compatible con Turso Cloud CLI y consolas SQL.

        # DECISIÓN DE NEGOCIO: Proporcionar el volcado SQL permite migrar directamente a Turso Cloud
        # ejecutando `turso db shell <nombre-bd> < turso_dump_....sql` sin necesidad de subir archivos binarios.
        """
        dest_dir = destination_dir or self.backups_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"turso_dump_{ts}.sql"

        target_file = dest_dir / filename

        if progress_callback:
            progress_callback(0.15, "Comprobando...", "Iniciando volcado SQL para Turso Cloud...")

        conn = sqlite3.connect(str(DB_PATH))
        try:
            lines: List[str] = [
                "-- ====================================================================\n",
                "-- Py-Manager-Lite: Volcado SQL para Turso Cloud / LibSQL\n",
                f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                f"-- Versión de la Aplicación: {APP_VERSION}\n",
                f"-- Compatible con Turso CLI: turso db shell <nombre-db> < {filename}\n",
                "-- ====================================================================\n\n",
                "PRAGMA foreign_keys=OFF;\n",
                "BEGIN TRANSACTION;\n\n",
            ]

            if progress_callback:
                progress_callback(
                    0.45,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Generando sentencias DDL y DML estructuradas..."
                )

            for sql_line in conn.iterdump():
                # iterdump produce sus propios BEGIN y COMMIT, filtramos para estandarizar
                if sql_line.startswith("BEGIN TRANSACTION") or sql_line.startswith("COMMIT"):
                    continue
                lines.append(f"{sql_line}\n")

            lines.append("\nCOMMIT;\n")
            lines.append("PRAGMA foreign_keys=ON;\n")

            if progress_callback:
                progress_callback(
                    0.80,
                    "Afinando para el perfil del usuario...",
                    f"Escribiendo {len(lines)} sentencias SQL en archivo..."
                )

            with open(target_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
        finally:
            conn.close()

        if progress_callback:
            progress_callback(
                1.0,
                "¡Volcado SQL generado con éxito!",
                f"Volcado guardado en {target_file.name}."
            )

        return str(target_file)

    def export_full_backup_package(
        self,
        destination_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float, Optional[str], Optional[str]], None]] = None,
    ) -> str:
        """Crea un paquete ZIP con la BD Turso (.db), volcado SQL (.sql) y los archivos de configuración."""
        dest_dir = destination_dir or self.backups_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not filename:
            filename = f"turso_backup_full_{ts}.zip"

        target_zip = dest_dir / filename

        if progress_callback:
            progress_callback(0.10, "Comprobando...", "Preparando empaquetado integral del sistema...")

        # Generar base de datos y volcado temporal
        temp_dir = self.safety_dir / f"pkg_{ts}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            if progress_callback:
                progress_callback(
                    0.25,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Generando copia binaria de base de datos..."
                )
            db_exported = self.export_turso_db(
                destination_dir=temp_dir,
                filename="turso_manager.db"
            )

            if progress_callback:
                progress_callback(
                    0.50,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Generando volcado SQL para Turso Cloud..."
                )
            sql_exported = self.export_turso_sql_dump(
                destination_dir=temp_dir,
                filename="turso_dump.sql"
            )

            summary = self.get_database_summary()

            manifest = {
                "application": "py-manager-lite",
                "version": APP_VERSION,
                "exported_at": datetime.now().isoformat(),
                "database_size_kb": summary.get("size_kb", 0),
                "record_counts": summary.get("counts", {}),
                "included_files": ["turso_manager.db", "turso_dump.sql"],
            }

            extra_files_to_pack = []
            if PROFILE_FILE.exists():
                extra_files_to_pack.append((PROFILE_FILE, "profile.json"))
                manifest["included_files"].append("profile.json")
            if AI_CONFIG_FILE.exists():
                extra_files_to_pack.append((AI_CONFIG_FILE, "ai_config.json"))
                manifest["included_files"].append("ai_config.json")
            if CURRENCY_CONFIG_FILE.exists():
                extra_files_to_pack.append((CURRENCY_CONFIG_FILE, "currency_config.json"))
                manifest["included_files"].append("currency_config.json")

            manifest_path = temp_dir / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            if progress_callback:
                progress_callback(
                    0.75,
                    "Afinando para el perfil del usuario...",
                    "Comprimiendo archivos de configuración y base de datos en ZIP..."
                )

            with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(db_exported, arcname="turso_manager.db")
                zip_file.write(sql_exported, arcname="turso_dump.sql")
                zip_file.write(manifest_path, arcname="manifest.json")
                for src_file, arc_name in extra_files_to_pack:
                    zip_file.write(src_file, arcname=arc_name)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return str(target_zip)

    def create_safety_backup(self) -> str:
        """Genera un respaldo de seguridad previo no destructivo en la carpeta safety antes de cualquier restore."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_filename = f"pre_restore_{ts}.db"
        safety_file = self.safety_dir / safety_filename

        if DB_PATH.exists():
            src_conn = sqlite3.connect(str(DB_PATH))
            dst_conn = sqlite3.connect(str(safety_file))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        # Respaldo de seguridad de configuraciones
        for cfg in [PROFILE_FILE, AI_CONFIG_FILE, CURRENCY_CONFIG_FILE]:
            if cfg.exists():
                shutil.copy2(cfg, self.safety_dir / f"{cfg.stem}_pre_restore_{ts}{cfg.suffix}")

        return str(safety_file)

    def inspect_backup_file(self, file_path_str: str) -> Dict[str, Any]:
        """Inspecciona y valida un archivo de respaldo (.db, .sql, .zip) antes de proceder con su importación."""
        path = Path(file_path_str).resolve()
        if not path.exists() or not path.is_file():
            return {
                "valid": False,
                "error": f"El archivo no existe o no es accesible: {path.name}",
            }

        size_kb = round(os.path.getsize(path) / 1024, 2)
        ext = path.suffix.lower()

        if ext == ".db" or ext == ".sqlite" or ext == ".libsql":
            # Validar encabezado y tablas de base de datos
            try:
                with open(path, "rb") as f:
                    header = f.read(16)
                if not header.startswith(b"SQLite format 3\x00"):
                    return {
                        "valid": False,
                        "error": "El archivo binario no tiene una cabecera SQLite/Turso válida.",
                    }

                summary = self.get_database_summary(path)
                return {
                    "valid": True,
                    "type": "db",
                    "file_name": path.name,
                    "file_path": str(path),
                    "size_kb": size_kb,
                    "counts": summary.get("counts", {}),
                    "integrity": summary.get("integrity", "OK"),
                }
            except Exception as ex:
                return {"valid": False, "error": f"Error al inspeccionar base de datos: {ex}"}

        elif ext == ".sql":
            # Validar script SQL
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    head_sample = "".join([f.readline() for _ in range(50)])

                if "CREATE TABLE" not in head_sample and "INSERT INTO" not in head_sample:
                    return {
                        "valid": False,
                        "error": "El archivo .sql no contiene sentencias reconocibles de base de datos.",
                    }

                return {
                    "valid": True,
                    "type": "sql",
                    "file_name": path.name,
                    "file_path": str(path),
                    "size_kb": size_kb,
                    "counts": {"Tipo": "Volcado SQL Turso / LibSQL"},
                    "integrity": "Sintaxis SQL válida",
                }
            except Exception as ex:
                return {"valid": False, "error": f"Error al leer archivo SQL: {ex}"}

        elif ext == ".zip":
            # Validar archivo zip
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                    has_db = any(n.endswith(".db") for n in namelist)
                    has_sql = any(n.endswith(".sql") for n in namelist)

                    if not (has_db or has_sql):
                        return {
                            "valid": False,
                            "error": "El archivo ZIP no contiene una base de datos (.db) ni un volcado (.sql).",
                        }

                    counts = {}
                    if "manifest.json" in namelist:
                        try:
                            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                            counts = manifest_data.get("record_counts", {})
                        except Exception:
                            pass

                    return {
                        "valid": True,
                        "type": "zip",
                        "file_name": path.name,
                        "file_path": str(path),
                        "size_kb": size_kb,
                        "counts": counts,
                        "integrity": f"Paquete Turso válido ({len(namelist)} elementos)",
                        "has_configs": any(n.endswith(".json") for n in namelist),
                    }
            except Exception as ex:
                return {"valid": False, "error": f"Error al abrir archivo ZIP: {ex}"}

        return {
            "valid": False,
            "error": f"Extensión '{ext}' no admitida. Se aceptan archivos .db, .sql o .zip.",
        }

    def import_backup(
        self,
        file_path_str: str,
        restore_configs: bool = True,
        progress_callback: Optional[Callable[[float, Optional[str], Optional[str]], None]] = None,
    ) -> Dict[str, Any]:
        """Restaura la base de datos completa desde un archivo de respaldo (.db, .sql o .zip).

        # DECISIÓN DE ARQUITECTURA: Antes de tocar la base de datos activa, se crea automáticamente
        # un respaldo de seguridad en tmp/profile/backups_safety. Posteriormente se descartan las
        # conexiones abiertas de SQLAlchemy y se sobreescribe la base de datos con la API de backup.
        """
        if progress_callback:
            progress_callback(0.08, "Comprobando...", f"Inspeccionando archivo: {Path(file_path_str).name}")

        inspection = self.inspect_backup_file(file_path_str)
        if not inspection.get("valid"):
            raise ValueError(inspection.get("error", "Archivo de respaldo inválido."))

        path = Path(file_path_str).resolve()

        if progress_callback:
            progress_callback(
                0.22,
                "Cargando para mejorar la experiencia de usuario...",
                "Generando respaldo de seguridad previo en safety_backups/..."
            )
        safety_path = self.create_safety_backup()

        if progress_callback:
            progress_callback(0.35, "Comprobando...", "Liberando conexiones activas del motor de base de datos...")

        # 1. Liberar todas las conexiones activas en el pool de SQLAlchemy
        SessionLocal.remove()
        engine.dispose()

        temp_extract_dir = None
        source_db_to_restore = None

        try:
            b_type = inspection.get("type")

            if b_type == "db":
                if progress_callback:
                    progress_callback(
                        0.50,
                        "Cargando para mejorar la experiencia de usuario...",
                        "Preparando base de datos binaria..."
                    )
                source_db_to_restore = path

            elif b_type == "sql":
                if progress_callback:
                    progress_callback(
                        0.45,
                        "Cargando para mejorar la experiencia de usuario...",
                        "Construyendo base de datos temporal desde volcado SQL..."
                    )
                # Construir una base de datos temporal aplicando el script SQL
                temp_extract_dir = self.safety_dir / f"sql_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                temp_extract_dir.mkdir(parents=True, exist_ok=True)
                temp_db = temp_extract_dir / "temp_sql.db"

                temp_conn = sqlite3.connect(str(temp_db))
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    sql_content = f.read()
                temp_conn.executescript(sql_content)
                temp_conn.close()

                source_db_to_restore = temp_db

            elif b_type == "zip":
                if progress_callback:
                    progress_callback(
                        0.45,
                        "Cargando para mejorar la experiencia de usuario...",
                        "Extrayendo paquete ZIP completo..."
                    )
                temp_extract_dir = self.safety_dir / f"zip_ext_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                temp_extract_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(temp_extract_dir)

                # Priorizar archivo .db si existe, sino .sql
                db_files = list(temp_extract_dir.glob("*.db"))
                if db_files:
                    source_db_to_restore = db_files[0]
                else:
                    sql_files = list(temp_extract_dir.glob("*.sql"))
                    if sql_files:
                        temp_db = temp_extract_dir / "temp_sql.db"
                        temp_conn = sqlite3.connect(str(temp_db))
                        with open(sql_files[0], "r", encoding="utf-8", errors="ignore") as f:
                            sql_content = f.read()
                        temp_conn.executescript(sql_content)
                        temp_conn.close()
                        source_db_to_restore = temp_db
                    else:
                        raise ValueError("El ZIP no contenía un archivo .db ni .sql válido.")

                # Restaurar configuraciones si se solicitó y vienen en el paquete
                if restore_configs:
                    if progress_callback:
                        progress_callback(
                            0.65,
                            "Afinando para el perfil del usuario...",
                            "Restaurando configuraciones de perfil, IA y divisas..."
                        )
                    for cfg_name, target_cfg in [
                        ("profile.json", PROFILE_FILE),
                        ("ai_config.json", AI_CONFIG_FILE),
                        ("currency_config.json", CURRENCY_CONFIG_FILE),
                    ]:
                        extracted_cfg = temp_extract_dir / cfg_name
                        if extracted_cfg.exists():
                            shutil.copy2(extracted_cfg, target_cfg)

            if not source_db_to_restore or not source_db_to_restore.exists():
                raise RuntimeError("No se pudo preparar la base de datos de origen para restauración.")

            if progress_callback:
                progress_callback(
                    0.80,
                    "Afinando para el perfil del usuario...",
                    "Sobrescribiendo base de datos local con respaldo verificado..."
                )

            # 2. Restauración atómica hacia DB_PATH usando SQLite backup
            src_conn = sqlite3.connect(str(source_db_to_restore))
            dst_conn = sqlite3.connect(str(DB_PATH))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            if progress_callback:
                progress_callback(0.92, "Comprobando...", "Reinicializando motor SQLAlchemy y aplicando esquemas...")

            # 3. Reiniciar motor y aplicar comprobaciones de esquema
            configure_db(DATABASE_URL)
            init_db()

            # 4. Obtener resumen de la base de datos restaurada
            restored_summary = self.get_database_summary()

            if progress_callback:
                c_sum = ", ".join([f"{k}: {v}" for k, v in restored_summary.get("counts", {}).items()])
                progress_callback(
                    1.0,
                    "¡Base de datos restaurada con éxito!",
                    f"Tablas y registros restablecidos: {c_sum}."
                )

            return {
                "success": True,
                "safety_backup_path": safety_path,
                "file_restored": path.name,
                "type": b_type,
                "counts": restored_summary.get("counts", {}),
                "integrity": restored_summary.get("integrity", "OK"),
            }

        finally:
            if temp_extract_dir and temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def list_backups(self) -> List[Dict[str, Any]]:
        """Lista todos los archivos de respaldo generados en la carpeta de respaldos."""
        if not self.backups_dir.exists():
            return []

        allowed_extensions = {".db", ".sql", ".zip"}
        results: List[Dict[str, Any]] = []

        for item in sorted(
            [f for f in self.backups_dir.iterdir() if f.is_file() and f.suffix.lower() in allowed_extensions],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        ):
            ext = item.suffix.lower()
            type_label = "Base de Datos Turso (.db)" if ext == ".db" else (
                "Volcado SQL (.sql)" if ext == ".sql" else "Paquete Completo (.zip)"
            )
            results.append({
                "name": item.name,
                "path": str(item),
                "type_label": type_label,
                "ext": ext,
                "size_kb": round(item.stat().st_size / 1024, 2),
                "created_at": datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

        return results
