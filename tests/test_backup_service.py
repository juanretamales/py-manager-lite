"""Pruebas unitarias para BackupService (Exportación, Importación y Respaldo Turso/LibSQL)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.db.session import init_db, get_db_session
from app.models.client import Client
from app.services.backup_service import BackupService


class TestBackupService(unittest.TestCase):
    """Conjunto de pruebas para respaldar, exportar e importar datos en formato Turso."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_backup_svc_")
        self.temp_path = Path(self.temp_dir)
        self.backups_dir = self.temp_path / "backups"
        self.safety_dir = self.temp_path / "safety"

        self.service = BackupService(
            backups_dir=self.backups_dir,
            safety_dir=self.safety_dir
        )

        # Sembrar cliente de prueba para validar persistencia en volcados
        init_db()
        with get_db_session() as session:
            existing = session.query(Client).filter_by(tax_id="76.111.222-3").first()
            if not existing:
                c = Client(
                    tax_id="76.111.222-3",
                    name="Empresa de Respaldo Test SpA",
                    legal_name="Empresa de Respaldo Test SpA",
                    contact_name="Tester",
                    email="test@respaldo.cl",
                    phone="+56911223344",
                    address="Calle Backup 123",
                )
                session.add(c)
                session.commit()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_database_summary(self) -> None:
        summary = self.service.get_database_summary()
        self.assertTrue(summary["exists"])
        self.assertEqual(summary["integrity"], "ok")
        self.assertIn("Clientes", summary["counts"])
        self.assertGreaterEqual(summary["counts"]["Clientes"], 1)

    def test_export_turso_db(self) -> None:
        exported_path = self.service.export_turso_db(filename="test_turso.db")
        self.assertTrue(os.path.exists(exported_path))
        self.assertTrue(exported_path.endswith(".db"))

        # Validar inspección
        inspection = self.service.inspect_backup_file(exported_path)
        self.assertTrue(inspection["valid"])
        self.assertEqual(inspection["type"], "db")
        self.assertGreaterEqual(inspection["counts"].get("Clientes", 0), 1)

    def test_export_turso_sql_dump(self) -> None:
        exported_sql = self.service.export_turso_sql_dump(filename="test_dump.sql")
        self.assertTrue(os.path.exists(exported_sql))

        with open(exported_sql, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Turso Cloud / LibSQL", content)
        self.assertIn("CREATE TABLE", content)
        self.assertIn("clients", content)

        # Validar inspección
        inspection = self.service.inspect_backup_file(exported_sql)
        self.assertTrue(inspection["valid"])
        self.assertEqual(inspection["type"], "sql")

    def test_export_full_backup_package(self) -> None:
        zip_path = self.service.export_full_backup_package(filename="full_pkg.zip")
        self.assertTrue(os.path.exists(zip_path))
        self.assertTrue(zip_path.endswith(".zip"))

        # Validar inspección
        inspection = self.service.inspect_backup_file(zip_path)
        self.assertTrue(inspection["valid"])
        self.assertEqual(inspection["type"], "zip")
        self.assertIn("Paquete Turso válido", inspection["integrity"])

    def test_inspect_invalid_file(self) -> None:
        invalid_file = self.temp_path / "fake.txt"
        invalid_file.write_text("not a valid db")
        inspection = self.service.inspect_backup_file(str(invalid_file))
        self.assertFalse(inspection["valid"])

    def test_safety_backup_creation(self) -> None:
        safety_path = self.service.create_safety_backup()
        self.assertTrue(os.path.exists(safety_path))
        self.assertIn("pre_restore_", safety_path)

    def test_import_turso_db_roundtrip(self) -> None:
        # Exportar BD actual
        exported_db = self.service.export_turso_db(filename="restore_candidate.db")

        # Modificar o verificar que se puede restaurar
        result = self.service.import_backup(exported_db)
        self.assertTrue(result["success"])
        self.assertEqual(result["integrity"], "ok")
        self.assertTrue(os.path.exists(result["safety_backup_path"]))

    def test_import_sql_dump_roundtrip(self) -> None:
        exported_sql = self.service.export_turso_sql_dump(filename="restore_candidate.sql")
        result = self.service.import_backup(exported_sql)
        self.assertTrue(result["success"])
        self.assertEqual(result["integrity"], "ok")

    def test_list_backups(self) -> None:
        self.service.export_turso_db(filename="list_1.db")
        self.service.export_turso_sql_dump(filename="list_2.sql")
        backups = self.service.list_backups()
        self.assertGreaterEqual(len(backups), 2)
        filenames = [b["name"] for b in backups]
        self.assertIn("list_1.db", filenames)
        self.assertIn("list_2.sql", filenames)


if __name__ == "__main__":
    unittest.main()
