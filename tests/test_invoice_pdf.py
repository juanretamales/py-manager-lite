"""
Suite de pruebas automatizadas para la lectura, extracción y validación de Facturas Electrónicas PDF del SII.
Verifica que el parser nativo extraiga correctamente los metadatos de todas las facturas en test_invoice/
y valida la persistencia contable en la base de datos de py-manager-lite.
"""

import re
import unittest
from pathlib import Path
from typing import Dict, Any, List

from app.db.session import init_db
from app.models.invoice import InvoiceType
from app.services.finance_service import FinanceService
# Función oficial y nativa responsable de procesar e interpretar documentos tributarios (PDF / XML)
from app.services.sii_invoice_parser import parse_sii_document, parse_sii_pdf


class TestInvoicePdfParser(unittest.TestCase):
    """Pruebas unitarias y de integración para la lectura y parsing de facturas PDF del SII."""

    @classmethod
    def setUpClass(cls) -> None:
        """Inicializa la base de datos de prueba y define la ruta base de facturas."""
        init_db()
        cls.project_root: Path = Path(__file__).resolve().parent.parent
        cls.test_invoice_dir: Path = cls.project_root / "test_invoice"

    def test_read_all_invoices_in_test_invoice_directory(self) -> None:
        """
        Escanea y valida todas las facturas PDF existentes en la carpeta test_invoice/.
        Asegura que el parser extraiga folio, montos, fecha y RUTs válidos para cada documento.
        """
        # DECISIÓN DE NEGOCIO: En Chile, toda factura electrónica del SII contiene folio numérico,
        # RUT del emisor, RUT del receptor, fecha de emisión y desglose neto/IVA/total.
        self.assertTrue(
            self.test_invoice_dir.exists(),
            f"El directorio de pruebas '{self.test_invoice_dir}' no existe."
        )

        pdf_files: List[Path] = sorted(list(self.test_invoice_dir.glob("*.pdf")))
        self.assertGreater(
            len(pdf_files),
            0,
            f"No se encontraron facturas PDF en {self.test_invoice_dir} para ejecutar la prueba."
        )

        rut_pattern = re.compile(r"^\d{1,2}\.?\d{3}\.?\d{3}\-[\dkK]$")
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        for pdf_path in pdf_files:
            with self.subTest(file=pdf_path.name):
                # Importar y ejecutar la función responsable de leer el PDF
                parsed: Dict[str, Any] = parse_sii_document(str(pdf_path))  # type: ignore

                # 1. Asegurar que la función pudo leer y procesar el PDF
                self.assertIsNotNone(
                    parsed,
                    f"Fallo al leer la factura '{pdf_path.name}'. parse_sii_document retornó None."
                )

                # 2. Folio / Número de factura
                folio: str = parsed.get("number", "")
                self.assertTrue(
                    bool(folio and folio.isdigit()),
                    f"Folio inválido o ausente en '{pdf_path.name}': {folio}"
                )

                # 3. Tipo de Documento
                doc_type: str = parsed.get("document_type", "")
                self.assertIn(
                    doc_type,
                    ["FACTURA ELECTRONICA", "FACTURA EXENTA ELECTRONICA", "NOTA DE CREDITO ELECTRONICA"],
                    f"Tipo de documento desconocido en '{pdf_path.name}': {doc_type}"
                )

                # 4. Montos
                total_amount: float = parsed.get("total_amount", 0.0)
                net_amount: float = parsed.get("net_amount", 0.0)
                tax_amount: float = parsed.get("tax_amount", 0.0)

                self.assertGreater(
                    total_amount,
                    0.0,
                    f"Monto total debe ser mayor a 0 en '{pdf_path.name}'"
                )
                self.assertGreaterEqual(
                    net_amount,
                    0.0,
                    f"Monto neto no puede ser negativo en '{pdf_path.name}'"
                )
                self.assertGreaterEqual(
                    tax_amount,
                    0.0,
                    f"IVA no puede ser negativo en '{pdf_path.name}'"
                )

                # 5. Formato de Fecha de Emisión (YYYY-MM-DD)
                issue_date: str = parsed.get("issue_date", "")
                self.assertTrue(
                    bool(issue_date and date_pattern.match(issue_date)),
                    f"Fecha de emisión inválida en '{pdf_path.name}': '{issue_date}'"
                )

                # 6. RUT Emisor y RUT Receptor
                emisor_tax_id: str = parsed.get("emisor_tax_id", "")
                receiver_tax_id: str = parsed.get("receiver_tax_id", "")

                self.assertTrue(
                    bool(emisor_tax_id and rut_pattern.match(emisor_tax_id)),
                    f"RUT Emisor inválido en '{pdf_path.name}': '{emisor_tax_id}'"
                )
                self.assertTrue(
                    bool(receiver_tax_id and rut_pattern.match(receiver_tax_id)),
                    f"RUT Receptor inválido en '{pdf_path.name}': '{receiver_tax_id}'"
                )

                # 7. Razón social / Nombre de emisor y receptor
                emisor_name: str = parsed.get("emisor_name", "")
                receiver_name: str = parsed.get("receiver_name", "")
                self.assertTrue(
                    bool(emisor_name and len(emisor_name.strip()) > 0),
                    f"Nombre de emisor vacío en '{pdf_path.name}'"
                )
                self.assertTrue(
                    bool(receiver_name and len(receiver_name.strip()) > 0),
                    f"Nombre de receptor vacío en '{pdf_path.name}'"
                )

    def test_specific_known_invoice_values(self) -> None:
        """Valida con precisión quirúrgica los campos esperados del archivo 20231226_1.pdf."""
        sample_file: Path = self.test_invoice_dir / "20231226_1.pdf"
        if not sample_file.exists():
            self.skipTest(f"Archivo de prueba {sample_file} no encontrado.")

        # Invocación directa a la función responsable de leer el PDF
        parsed = parse_sii_pdf(str(sample_file))
        self.assertIsNotNone(parsed)

        self.assertEqual(parsed["number"], "27")
        self.assertEqual(parsed["document_type"], "FACTURA ELECTRONICA")
        self.assertEqual(parsed["tipo_dte"], "33")
        self.assertEqual(parsed["issue_date"], "2023-12-26")
        self.assertEqual(parsed["emisor_tax_id"], "77.520.747-7")
        self.assertEqual(parsed["receiver_tax_id"], "77.185.288-2")
        self.assertEqual(parsed["net_amount"], 1350000.0)
        self.assertEqual(parsed["tax_amount"], 256500.0)
        self.assertEqual(parsed["total_amount"], 1606500.0)
        self.assertIn("RETAMALES", parsed["emisor_name"].upper())
        self.assertIn("SERVICIOS DE TECNOLOGIA", parsed["receiver_name"].upper())

    def test_exempt_invoice_known_values(self) -> None:
        """
        Valida que las Facturas Exentas (Tipo DTE 34) sean leídas correctamente,
        asegurando folio 570, emisor Luis Villagra y montos netos/IVA en 0 con total no afecto.
        """
        exempt_file: Path = self.test_invoice_dir / "Fe 570 77694005.pdf"
        if not exempt_file.exists():
            self.skipTest("Factura exenta de prueba no encontrada.")

        parsed = parse_sii_document(str(exempt_file))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["number"], "570")
        self.assertEqual(parsed["document_type"], "FACTURA EXENTA ELECTRONICA")
        # DECISIÓN DE NEGOCIO (SII): Las facturas exentas corresponden obligatoriamente al Tipo DTE 34
        self.assertEqual(parsed["tipo_dte"], "34")
        self.assertEqual(parsed["issue_date"], "2026-02-27")
        self.assertEqual(parsed["emisor_tax_id"], "77.694.005-4")
        self.assertEqual(parsed["receiver_tax_id"], "77.520.747-7")
        self.assertEqual(parsed["net_amount"], 0.0)
        self.assertEqual(parsed["tax_amount"], 0.0)
        self.assertEqual(parsed["total_amount"], 18000.0)
        self.assertIn("LUIS VILLAGRA", parsed["emisor_name"].upper())

    def test_parse_non_existent_file_returns_none(self) -> None:
        """Verifica que rutas no existentes o vacías se manejen elegantemente retornando None."""
        self.assertIsNone(parse_sii_document(""))
        self.assertIsNone(parse_sii_document("test_invoice/no_existe_archivo.pdf"))
        self.assertIsNone(parse_sii_pdf("test_invoice/no_existe_archivo.pdf"))

    def test_parse_and_ingest_invoice_into_database(self) -> None:
        """
        Prueba el flujo integral de negocio: leer el PDF de factura e ingresarlo
        a la base de datos mediante el servicio contable FinanceService.
        """
        sample_file: Path = self.test_invoice_dir / "20231226_1.pdf"
        if not sample_file.exists():
            self.skipTest("No se encontró factura de prueba para ingreso en base de datos.")

        parsed = parse_sii_document(str(sample_file))
        self.assertIsNotNone(parsed)

        fin_svc = FinanceService()
        test_invoice_number: str = f"TEST-{parsed['number']}"

        # DECISIÓN DE NEGOCIO: Factura recibida (Gasto) con emisor como proveedor externo
        invoice_record = fin_svc.create_invoice(
            type=InvoiceType.RECEIVED,
            number=test_invoice_number,
            issuer_name=parsed["emisor_name"],
            issuer_tax_id=parsed["emisor_tax_id"],
            receiver_name=parsed["receiver_name"],
            receiver_tax_id=parsed["receiver_tax_id"],
            issue_date=parsed["issue_date"],
            net_amount=parsed["net_amount"],
            tax_amount=parsed["tax_amount"],
            total_amount=parsed["total_amount"],
            category="Servicios Profesionales & Honorarios",
            document_path=str(sample_file),
            notes=f"Ingreso automático de prueba desde PDF Folio #{parsed['number']}"
        )

        self.assertIsNotNone(invoice_record)
        self.assertEqual(invoice_record["number"], test_invoice_number)
        self.assertEqual(invoice_record["total_amount"], 1606500.0)

        # Recuperar y validar persistencia desde base de datos
        fetched = fin_svc.get_invoice(invoice_record["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["number"], test_invoice_number)
        self.assertEqual(fetched["issuer_tax_id"], "77.520.747-7")
        self.assertEqual(fetched["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
