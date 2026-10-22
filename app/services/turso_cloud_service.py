"""Servicio de Integración y Sincronización con Turso Cloud (libSQL).

Implementa las capacidades de la Fase 5 del Roadmap:
1. Conexión segura autenticada a Turso Cloud vía HTTPS con credenciales protegidas por AES-256-GCM.
2. Diagnóstico de conectividad, medición de latencia (ping) y recuento de tablas remotas.
3. Replicación unidireccional Push (Local -> Cloud) para migración o respaldo remoto en la nube.
4. Replicación unidireccional Pull (Cloud -> Local) con respaldo de seguridad automático previo.
5. Resumen comparativo de tablas y registros entre base local y Turso Cloud.
"""

import time
import sqlite3
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime

import libsql_client
from app.core.config import DB_PATH, normalize_turso_url
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService


class TursoCloudService:
    """Gestiona la conectividad, diagnóstico y replicación con la base de datos Turso Cloud."""

    def __init__(self, auth_service: Optional[AuthService] = None) -> None:
        self.auth_service = auth_service or AuthService()
        self.backup_service = BackupService()

    def get_credentials(self) -> Tuple[str, str]:
        """Obtiene la URL y el token descifrado de Turso Cloud desde el perfil seguro."""
        return self.auth_service.get_turso_credentials()

    def is_configured(self) -> bool:
        """Determina si la URL y el token de Turso Cloud están configurados en el perfil."""
        url, token = self.get_credentials()
        return bool(url.strip() and token.strip())

    def get_client(self, url: Optional[str] = None, token: Optional[str] = None) -> libsql_client.ClientSync:
        """Crea y retorna un cliente sincrónico conectado a Turso Cloud mediante protocolo HTTP seguro.

        # DECISIÓN DE ARQUITECTURA: Se normaliza la URL a https:// porque la API HTTP de Turso
        # es inmune a bloqueos de WebSockets por proxies o firewalls corporativos en entornos Windows.
        """
        target_url = url or self.get_credentials()[0]
        target_token = token or self.get_credentials()[1]

        if not target_url.strip():
            raise ValueError("La URL de la base de datos Turso Cloud no está configurada.")
        if not target_token.strip():
            raise ValueError("El token de autenticación de Turso Cloud no está configurado.")

        http_url = normalize_turso_url(target_url, force_https=True)
        return libsql_client.create_client_sync(http_url, auth_token=target_token.strip())

    def test_connection(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verifica la conectividad en vivo con Turso Cloud y mide la latencia de respuesta en milisegundos."""
        start_time = time.perf_counter()
        target_url = url or self.get_credentials()[0]
        target_token = token or self.get_credentials()[1]

        if not target_url.strip():
            return {
                "connected": False,
                "latency_ms": 0.0,
                "table_count": 0,
                "url": "",
                "message": "Falta ingresar la URL de Turso Cloud (ej: libsql://tu-bd.turso.io).",
            }
        if not target_token.strip():
            return {
                "connected": False,
                "latency_ms": 0.0,
                "table_count": 0,
                "url": target_url,
                "message": "Falta ingresar el Token de autenticación de Turso Cloud.",
            }

        client = None
        try:
            client = self.get_client(url=target_url, token=target_token)
            client.execute("SELECT 1 as ping;")
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

            tables_res = client.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            table_count = int(tables_res.rows[0][0]) if tables_res.rows else 0

            return {
                "connected": True,
                "latency_ms": latency_ms,
                "table_count": table_count,
                "url": target_url,
                "message": f"Conexión exitosa a Turso Cloud ({latency_ms} ms). Tablas remotas: {table_count}.",
            }
        except Exception as ex:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            err_msg = str(ex)
            if "401" in err_msg or "Unauthorized" in err_msg:
                user_msg = "Token de autenticación de Turso inválido o expirado."
            elif "404" in err_msg or "not found" in err_msg.lower():
                user_msg = "Base de datos en Turso no encontrada. Revisa la URL."
            else:
                user_msg = f"Error al conectar: {err_msg}"
            return {
                "connected": False,
                "latency_ms": latency_ms,
                "table_count": 0,
                "url": target_url,
                "message": user_msg,
            }
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    def get_remote_tables_summary(self) -> Dict[str, Any]:
        """Obtiene el listado detallado de tablas y conteo de filas alojadas actualmente en Turso Cloud."""
        client = None
        try:
            client = self.get_client()
            res = client.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            tables = [row[0] for row in res.rows]
            counts: Dict[str, int] = {}
            for t in tables:
                try:
                    r_count = client.execute(f"SELECT COUNT(*) FROM {t};")
                    counts[t] = int(r_count.rows[0][0])
                except Exception:
                    counts[t] = 0
            return {
                "success": True,
                "tables": tables,
                "counts": counts,
                "total_tables": len(tables),
                "total_rows": sum(counts.values()),
            }
        except Exception as ex:
            return {
                "success": False,
                "error": str(ex),
                "tables": [],
                "counts": {},
                "total_tables": 0,
                "total_rows": 0,
            }
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    def push_local_to_cloud(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """Reemplaza y replica el esquema y los datos locales SQLite en Turso Cloud.

        # DECISIÓN DE NEGOCIO: Permite que el usuario sincronice toda su información comercial
        # local hacia la base remota de Turso Cloud para acceso multi-dispositivo o respaldo en la nube.
        """
        if not DB_PATH.exists():
            raise FileNotFoundError(f"La base de datos local no existe en {DB_PATH}.")

        client = None
        local_conn = None
        try:
            if progress_callback:
                progress_callback("Conectando con Turso Cloud...", 0.1)

            client = self.get_client()
            local_conn = sqlite3.connect(str(DB_PATH))
            cur = local_conn.cursor()

            # Obtener nombres de tablas locales (excluyendo sqlite_*)
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            tables = [row[0] for row in cur.fetchall()]

            if not tables:
                return {
                    "success": True,
                    "tables_synced": 0,
                    "records_synced": 0,
                    "message": "No hay tablas locales para sincronizar.",
                }

            total_tables = len(tables)
            total_records = 0
            tables_synced = 0

            # Deshabilitar claves foráneas temporalmente en Turso para inserción limpia
            try:
                client.execute("PRAGMA foreign_keys=OFF;")
            except Exception:
                pass

            for idx, table_name in enumerate(tables, 1):
                fraction = 0.1 + (idx / (total_tables + 1)) * 0.8
                if progress_callback:
                    progress_callback(f"Sincronizando tabla '{table_name}' ({idx}/{total_tables})...", fraction)

                # 1. Obtener DDL de creación de la tabla
                cur.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?;",
                    (table_name,)
                )
                row_ddl = cur.fetchone()
                if not row_ddl or not row_ddl[0]:
                    continue
                create_sql = row_ddl[0]

                # Ejecutar DDL en Turso Cloud
                client.execute(create_sql)

                # 2. Leer filas y columnas locales
                cur.execute(f"SELECT * FROM {table_name};")
                rows = cur.fetchall()
                if not rows:
                    tables_synced += 1
                    continue

                col_names = [d[0] for d in cur.description]
                placeholders = ", ".join(["?"] * len(col_names))
                cols_joined = ", ".join([f'"{c}"' for c in col_names])
                insert_query = f'INSERT OR REPLACE INTO "{table_name}" ({cols_joined}) VALUES ({placeholders});'

                # Enviar en lotes de 50 registros parametrizados
                batch_size = 50
                for start_idx in range(0, len(rows), batch_size):
                    chunk = rows[start_idx:start_idx + batch_size]
                    stmt_list = [
                        libsql_client.Statement(insert_query, list(r))
                        for r in chunk
                    ]
                    client.batch(stmt_list)
                    total_records += len(chunk)

                tables_synced += 1

            try:
                client.execute("PRAGMA foreign_keys=ON;")
            except Exception:
                pass

            if progress_callback:
                progress_callback("Sincronización a Turso Cloud finalizada.", 1.0)

            return {
                "success": True,
                "tables_synced": tables_synced,
                "records_synced": total_records,
                "timestamp": datetime.now().isoformat(),
                "message": (
                    f"Se sincronizaron con éxito {tables_synced} tablas y {total_records} registros en Turso Cloud."
                ),
            }
        except Exception as ex:
            raise RuntimeError(f"Error durante la sincronización a Turso Cloud: {ex}") from ex
        finally:
            if local_conn:
                local_conn.close()
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    def pull_cloud_to_local(
        self,
        safety_backup: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """Descarga el esquema y los datos desde Turso Cloud a la base de datos local SQLite.

        # DECISIÓN DE SEGURIDAD: Siempre genera un respaldo de seguridad previo en 'safety_backups/'
        # para garantizar cero pérdida de información local ante cualquier imprevisto de red.
        """
        safety_path = None
        if safety_backup and DB_PATH.exists():
            if progress_callback:
                progress_callback("Generando respaldo local de seguridad...", 0.05)
            safety_path = self.backup_service.create_safety_backup("pre_turso_pull")

        client = None
        local_conn = None
        try:
            if progress_callback:
                progress_callback("Conectando con Turso Cloud...", 0.15)

            client = self.get_client()

            # Leer tablas remotas
            res_tables = client.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            remote_tables = [(row[0], row[1]) for row in res_tables.rows]

            if not remote_tables:
                return {
                    "success": True,
                    "tables_synced": 0,
                    "records_synced": 0,
                    "safety_backup_path": safety_path,
                    "message": "Turso Cloud no contiene tablas para descargar.",
                }

            # Abrir base local SQLite
            local_conn = sqlite3.connect(str(DB_PATH))
            local_cur = local_conn.cursor()
            local_cur.execute("PRAGMA foreign_keys=OFF;")

            total_tables = len(remote_tables)
            total_records = 0
            tables_synced = 0

            for idx, (table_name, create_sql) in enumerate(remote_tables, 1):
                fraction = 0.2 + (idx / (total_tables + 1)) * 0.75
                if progress_callback:
                    progress_callback(f"Descargando tabla '{table_name}' ({idx}/{total_tables})...", fraction)

                # Recrear tabla localmente
                local_cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
                local_cur.execute(create_sql)

                # Descargar registros desde Turso Cloud
                remote_rows = client.execute(f'SELECT * FROM "{table_name}";')
                if remote_rows.rows:
                    col_names = [f'"{c}"' for c in remote_rows.columns]
                    placeholders = ", ".join(["?"] * len(col_names))
                    cols_joined = ", ".join(col_names)
                    ins_query = f'INSERT INTO "{table_name}" ({cols_joined}) VALUES ({placeholders});'

                    rows_tuples = [row.astuple() for row in remote_rows.rows]
                    local_cur.executemany(ins_query, rows_tuples)
                    total_records += len(rows_tuples)

                tables_synced += 1

            local_conn.commit()
            local_cur.execute("PRAGMA foreign_keys=ON;")
            local_conn.commit()

            # Reconfigurar motor SQLAlchemy de la aplicación
            from app.db.session import configure_db
            configure_db(f"sqlite:///{DB_PATH}")

            if progress_callback:
                progress_callback("Base de datos local actualizada desde Turso Cloud.", 1.0)

            return {
                "success": True,
                "tables_synced": tables_synced,
                "records_synced": total_records,
                "safety_backup_path": safety_path,
                "message": (
                    f"Base de datos local actualizada desde Turso Cloud: "
                    f"{tables_synced} tablas y {total_records} registros."
                ),
            }
        except Exception as ex:
            if local_conn:
                local_conn.rollback()
            raise RuntimeError(f"Error al descargar desde Turso Cloud: {ex}") from ex
        finally:
            if local_conn:
                local_conn.close()
            if client:
                try:
                    client.close()
                except Exception:
                    pass
