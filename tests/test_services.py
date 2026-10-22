import unittest
import shutil
from datetime import datetime
from pathlib import Path
from app.core.config import DATA_DIR
from app.db.session import configure_db
from app.services.company_service import CompanyService
from app.services.client_service import ClientService
from app.services.quote_service import QuoteService
from app.services.project_service import ProjectService
from app.services.finance_service import FinanceService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService
from app.services.sii_invoice_parser import parse_sii_document
from app.models.quote import QuoteStatus
from app.models.invoice import InvoiceType, PaymentStatus

TEST_DB_FILE = DATA_DIR / "test_isolated_manager.db"


class TestServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass
        configure_db(f"sqlite:///{TEST_DB_FILE}")

    @classmethod
    def tearDownClass(cls):
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass

    def test_company_and_canvas(self):
        svc = CompanyService()
        company = svc.get_company()
        self.assertIsNotNone(company["id"])
        self.assertTrue(len(company["legal_name"]) > 0)

        canvas = svc.get_canvas(company["id"])
        self.assertEqual(canvas["company_id"], company["id"])

    def test_client_crud_and_events(self):
        client_svc = ClientService()
        created = client_svc.create_client(
            name="Cliente Prueba SpA",
            legal_name="Cliente de Prueba Sociedad por Acciones",
            tax_id="76.123.456-7",
            email="contacto@clienteprueba.cl"
        )
        self.assertIsNotNone(created["id"])

        client = client_svc.get_client(created["id"])
        self.assertEqual(client["name"], "Cliente Prueba SpA")
        self.assertTrue(len(client["events"]) >= 1)

        # Toggle active
        new_status = client_svc.toggle_active(created["id"])
        self.assertFalse(new_status)
        new_status = client_svc.toggle_active(created["id"])
        self.assertTrue(new_status)

    def test_quote_and_conversion_to_project(self):
        client_svc = ClientService()
        client = client_svc.create_client(name="Acme Corp", email="acme@test.com")

        quote_svc = QuoteService()
        items = [
            {"description": "Diseño UI/UX", "quantity": 1, "unit": "un", "unit_price": 500000},
            {"description": "Desarrollo Frontend Flet", "quantity": 2, "unit": "mes", "unit_price": 1000000}
        ]
        quote = quote_svc.create_quote(
            client_id=client["id"],
            items_data=items,
            notes="Cotización de desarrollo"
        )
        self.assertIsNotNone(quote["id"])
        self.assertEqual(quote["total_amount"], 2500000 * 1.19)  # Subtotal 2.500.000 + 19% IVA

        # Accept quote
        quote_svc.change_status(quote["id"], QuoteStatus.ACCEPTED)

        # Convert to project
        proj = quote_svc.convert_to_project(quote["id"])
        self.assertIsNotNone(proj["id"])

        project_svc = ProjectService()
        project_svc.update_progress(proj["id"], 50, "Avance primera mitad")
        p = project_svc.get_project(proj["id"])
        self.assertEqual(p["progress"], 50)

    def test_quote_update_and_soft_delete(self):
        client_svc = ClientService()
        client = client_svc.create_client(name="Soft Delete Test Client", email="soft@test.com")

        quote_svc = QuoteService()
        q = quote_svc.create_quote(
            client_id=client["id"],
            items_data=[{"description": "Item 1", "quantity": 1, "unit": "un", "unit_price": 100000}]
        )
        quote_id = q["id"]

        # Update quote items
        updated = quote_svc.update_quote(
            quote_id=quote_id,
            items_data=[
                {"description": "Item 1 Modificado", "quantity": 2, "unit": "un", "unit_price": 150000},
                {"description": "Item 2 Nuevo", "quantity": 1, "unit": "mes", "unit_price": 200000}
            ],
            notes="Actualizado en PoC"
        )
        self.assertIsNotNone(updated)
        # Subtotal: 300,000 + 200,000 = 500,000. Total c/IVA 19%: 595,000
        self.assertEqual(updated["total_amount"], 595000)

        # Soft delete
        deleted = quote_svc.delete_quote(quote_id)
        self.assertTrue(deleted)

        # Ensure excluded from default list_quotes
        active_quotes = quote_svc.list_quotes()
        active_ids = [item["id"] for item in active_quotes]
        self.assertNotIn(quote_id, active_ids)

        # Ensure present when filtering by QuoteStatus.DELETED
        deleted_quotes = quote_svc.list_quotes(status=QuoteStatus.DELETED)
        deleted_ids = [item["id"] for item in deleted_quotes]
        self.assertIn(quote_id, deleted_ids)

        # Restore
        restored = quote_svc.restore_quote(quote_id, restored_status=QuoteStatus.DRAFT)
        self.assertTrue(restored)
        active_quotes_after = quote_svc.list_quotes()
        active_ids_after = [item["id"] for item in active_quotes_after]
        self.assertIn(quote_id, active_ids_after)

    def test_quote_filtering_by_client_and_date(self):
        client_svc = ClientService()
        c1 = client_svc.create_client(name="Filtro C1", email="c1@test.com")
        c2 = client_svc.create_client(name="Filtro C2", email="c2@test.com")

        quote_svc = QuoteService()
        q1 = quote_svc.create_quote(
            client_id=c1["id"], items_data=[{"description": "A", "quantity": 1, "unit_price": 100}]
        )
        q2 = quote_svc.create_quote(
            client_id=c2["id"], items_data=[{"description": "B", "quantity": 1, "unit_price": 200}]
        )

        # Filter by client
        c1_quotes = quote_svc.list_quotes(client_id=c1["id"])
        c1_ids = [q["id"] for q in c1_quotes]
        self.assertIn(q1["id"], c1_ids)
        self.assertNotIn(q2["id"], c1_ids)

        # Filter by issue_date
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_quotes = quote_svc.list_quotes(issue_date=today_str)
        today_ids = [q["id"] for q in today_quotes]
        self.assertIn(q1["id"], today_ids)
        self.assertIn(q2["id"], today_ids)

    def test_finance_invoices_and_payments(self):
        client_svc = ClientService()
        client = client_svc.create_client(name="Finanzas Test", email="fin@test.com")

        fin_svc = FinanceService()
        invoice = fin_svc.create_invoice(
            type=InvoiceType.ISSUED,
            client_id=client["id"],
            number="FAC-001",
            net_amount=1000000,
            tax_amount=190000,
            total_amount=1190000
        )
        self.assertIsNotNone(invoice["id"])

        # Check initial summary
        inv_data = fin_svc.get_invoice(invoice["id"])
        self.assertEqual(inv_data["status"], PaymentStatus.PENDING)
        self.assertEqual(inv_data["balance"], 1190000)

        # Register partial payment
        pay1 = fin_svc.register_payment(invoice["id"], amount=500000, payment_method="Transferencia")
        self.assertEqual(pay1["status"], PaymentStatus.PARTIAL)
        self.assertEqual(pay1["balance"], 690000)

        # Register remaining payment
        pay2 = fin_svc.register_payment(invoice["id"], amount=690000, payment_method="Transferencia")
        self.assertEqual(pay2["status"], PaymentStatus.PAID)
        self.assertEqual(pay2["balance"], 0.0)

    def test_purchase_orders_and_project_conversion(self):
        client_svc = ClientService()
        quote_svc = QuoteService()
        po_svc = PurchaseOrderService()

        client = client_svc.create_client(name="PO Client Test", email="po@test.com")
        quote = quote_svc.create_quote(
            client_id=client["id"],
            items_data=[{"description": "Consulting", "quantity": 1, "unit": "mes", "unit_price": 500000}]
        )

        # Create PO linked to quote
        po = po_svc.create_order(
            client_id=client["id"],
            quote_id=quote["id"],
            number="OC-2026-999",
            amount=595000,
            document_path="documents/purchase_orders/test_oc.pdf",
            notes="Orden de compra oficial enviada por cliente"
        )
        self.assertIsNotNone(po["id"])
        self.assertEqual(po["number"], "OC-2026-999")
        self.assertEqual(po["status"], "ACCEPTED")

        # List POs
        orders = po_svc.list_orders(client_id=client["id"])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["quote_number"], quote["number"])

        # Update PO
        updated_po = po_svc.update_order(po["id"], amount=600000, notes="Monto reajustado")
        self.assertEqual(updated_po["amount"], 600000)

        # Convert PO to project
        proj = po_svc.convert_to_project(po["id"])
        self.assertIsNotNone(proj["id"])
        self.assertTrue("OC-2026-999" in proj["name"])

        # Delete PO
        deleted = po_svc.delete_order(po["id"])
        self.assertTrue(deleted)
        orders_after = po_svc.list_orders(client_id=client["id"])
        self.assertEqual(len(orders_after), 0)

    def test_invoice_categories_update_and_documents(self):
        client_svc = ClientService()
        fin_svc = FinanceService()

        client = client_svc.create_client(name="Category Test Client", email="cat@test.com")

        # Create invoice with category
        inv = fin_svc.create_invoice(
            type=InvoiceType.RECEIVED,
            number="FAC-REC-001",
            client_id=client["id"],
            net_amount=150000,
            category="Servicios Cloud & Hosting",
            document_path="documents/invoices/received/fac_001.pdf"
        )
        self.assertIsNotNone(inv["id"])

        # Update invoice
        updated = fin_svc.update_invoice(
            invoice_id=inv["id"],
            net_amount=200000,
            category="Licencias de Software"
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["total_amount"], 238000)  # 200,000 + 19% IVA

        # List invoices filtered by category
        cloud_invoices = fin_svc.list_invoices(category="Servicios Cloud & Hosting")
        self.assertEqual(len(cloud_invoices), 0)  # changed to Licencias

        lic_invoices = fin_svc.list_invoices(category="Licencias de Software")
        self.assertTrue(len(lic_invoices) >= 1)

        # List available categories
        cats = fin_svc.list_categories()
        self.assertIn("Licencias de Software", cats)

    def test_project_invoices_linking_and_unlinking(self):
        client_svc = ClientService()
        project_svc = ProjectService()
        fin_svc = FinanceService()

        client = client_svc.create_client(name="Proyecto Invoices Client", email="proj_inv@test.com")
        proj = project_svc.create_project(name="Proyecto Web y Facturación", client_id=client["id"])

        # Create invoice directly linked to project
        inv = fin_svc.create_invoice(
            type=InvoiceType.ISSUED,
            number="FAC-PROJ-101",
            client_id=client["id"],
            project_id=proj["id"],
            net_amount=500000,
            category="Servicios Profesionales & Honorarios",
            notes="Factura creada directamente desde el proyecto"
        )
        self.assertIsNotNone(inv["id"])

        # Verify it appears in Project's invoice list
        p_data = project_svc.get_project(proj["id"])
        self.assertTrue(len(p_data["invoices"]) >= 1)
        self.assertEqual(p_data["invoices"][0]["number"], "FAC-PROJ-101")
        self.assertEqual(p_data["invoices"][0]["total_amount"], 595000)

        # Verify it appears in Finances
        fin_invoices = fin_svc.list_invoices(project_id=proj["id"])
        self.assertEqual(len(fin_invoices), 1)
        self.assertEqual(fin_invoices[0]["project_name"], "Proyecto Web y Facturación")

        # Unlink invoice from project
        success = fin_svc.unlink_invoice_from_project(inv["id"])
        self.assertTrue(success)

        # Verify it no longer appears in project invoices
        p_data_after = project_svc.get_project(proj["id"])
        self.assertEqual(len(p_data_after["invoices"]), 0)

        # Verify it is STILL present in Finances without losing data
        inv_in_fin = fin_svc.get_invoice(inv["id"])
        self.assertIsNotNone(inv_in_fin)
        self.assertIsNone(inv_in_fin["project_id"])
        self.assertEqual(inv_in_fin["number"], "FAC-PROJ-101")

    def test_delete_invoice_with_audit_reason(self):
        client_svc = ClientService()
        project_svc = ProjectService()
        fin_svc = FinanceService()

        client = client_svc.create_client(name="Audit Client", email="audit@test.com")
        proj = project_svc.create_project(name="Audit Project", client_id=client["id"])

        inv = fin_svc.create_invoice(
            type=InvoiceType.RECEIVED,
            number="FAC-ERR-999",
            client_id=client["id"],
            project_id=proj["id"],
            net_amount=100000,
            notes="Factura con error de digitación"
        )

        # Delete with explicit audit reason
        reason = "Error de digitación en monto neto; factura rechazada antes de validación fiscal"
        deleted = fin_svc.delete_invoice(inv["id"], reason=reason)
        self.assertTrue(deleted)

        # Verify invoice is gone from database
        self.assertIsNone(fin_svc.get_invoice(inv["id"]))

        # Verify audit trail in client events
        c_events = client_svc.get_client(client["id"])["events"]
        audit_events = [ev for ev in c_events if "eliminada del sistema" in ev["description"]]
        self.assertTrue(len(audit_events) >= 1)
        self.assertIn("FAC-ERR-999", audit_events[0]["description"])
        self.assertIn(reason, audit_events[0]["description"])

    def test_credit_note_annulment(self):
        client_svc = ClientService()
        project_svc = ProjectService()
        fin_svc = FinanceService()

        client = client_svc.create_client(name="SII NC Client", email="sii@test.com")
        proj = project_svc.create_project(name="Proyecto SII", client_id=client["id"])

        # Create original invoice
        inv = fin_svc.create_invoice(
            type=InvoiceType.ISSUED,
            number="FAC-SII-500",
            client_id=client["id"],
            project_id=proj["id"],
            net_amount=1000000,
            tax_amount=190000,
            total_amount=1190000
        )

        inv_summary_before = fin_svc.get_invoice(inv["id"])
        self.assertEqual(inv_summary_before["status"], PaymentStatus.PENDING)
        self.assertEqual(inv_summary_before["balance"], 1190000)

        # Issue Credit Note for full annulment
        nc = fin_svc.create_credit_note(
            reference_invoice_id=inv["id"],
            number="NC-001",
            amount=1190000,
            reason="1. Anula Documento de Referencia - Resciliación mutua de contrato",
            is_total_annulment=True,
            document_path="documents/invoices/credit_notes/nc_001.pdf"
        )
        self.assertIsNotNone(nc["id"])
        self.assertEqual(nc["reference_invoice_number"], "FAC-SII-500")

        # Verify original invoice is now ANNULLED and balance is 0
        inv_summary_after = fin_svc.get_invoice(inv["id"])
        self.assertEqual(inv_summary_after["status"], PaymentStatus.ANNULLED)
        self.assertEqual(inv_summary_after["balance"], 0.0)
        self.assertEqual(len(inv_summary_after["credit_notes"]), 1)
        self.assertEqual(inv_summary_after["credit_notes"][0]["number"], "NC-001")

        # Verify Credit Note exists in listing as CREDIT_NOTE type
        nc_list = fin_svc.list_invoices(invoice_type=InvoiceType.CREDIT_NOTE)
        nc_numbers = [item["number"] for item in nc_list]
        self.assertIn("NC-001", nc_numbers)

    def test_sii_native_invoice_parser(self):
        from app.services.sii_invoice_parser import parse_sii_document
        sample_pdf = Path("test_invoice/20231226_1.pdf")
        if sample_pdf.exists():
            parsed = parse_sii_document(str(sample_pdf))
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["number"], "27")
            self.assertEqual(parsed["document_type"], "FACTURA ELECTRONICA")
            self.assertEqual(parsed["issue_date"], "2023-12-26")
            self.assertEqual(parsed["net_amount"], 1350000.0)
            self.assertEqual(parsed["tax_amount"], 256500.0)
            self.assertEqual(parsed["total_amount"], 1606500.0)
            self.assertIn("77.520.747-7", parsed["emisor_tax_id"])
            self.assertIn("77.185.288-2", parsed["receiver_tax_id"])

    def test_auth_service_lifecycle_and_security(self):
        from app.services.auth_service import AuthService
        test_profile_path = DATA_DIR / "test_auth_profile.json"
        if test_profile_path.exists():
            test_profile_path.unlink()

        auth_svc = AuthService(profile_path=test_profile_path)
        self.assertFalse(auth_svc.is_profile_configured())

        custom_storage = DATA_DIR / "test_initial_storage"
        custom_storage.mkdir(parents=True, exist_ok=True)

        # Create initial profile with storage_path
        profile = auth_svc.create_profile(
            user_name="Juan Pérez",
            company_name="Soluciones TI SpA",
            password="MasterPassword2026",
            pin="123456",
            storage_path=str(custom_storage),
            turso_cloud_url="libsql://test-db.turso.io"
        )
        self.assertTrue(auth_svc.is_profile_configured())
        self.assertEqual(profile["user_name"], "Juan Pérez")
        self.assertEqual(profile["company_name"], "Soluciones TI SpA")
        self.assertEqual(profile["storage_path"], str(custom_storage.resolve()))
        self.assertTrue(profile["has_turso_cloud"])

        # Create dummy file in initial storage to test migration
        sample_file = custom_storage / "test_doc.txt"
        sample_file.write_text("contenido de prueba")

        # Migrate to new storage path
        new_storage = DATA_DIR / "test_migrated_storage"
        migrated = auth_svc.migrate_storage_path(str(new_storage), move_existing=True)
        self.assertTrue(migrated["success"])
        self.assertGreaterEqual(migrated["files_moved"], 1)
        self.assertTrue((new_storage / "test_doc.txt").exists())

        # Verify profile updated
        p_info = auth_svc.get_profile_info()
        self.assertEqual(p_info["storage_path"], str(new_storage.resolve()))

        # Validate Master Password
        self.assertTrue(auth_svc.verify_password("MasterPassword2026"))
        self.assertFalse(auth_svc.verify_password("WrongPassword"))

        # Validate PIN
        self.assertTrue(auth_svc.verify_pin("123456"))
        self.assertFalse(auth_svc.verify_pin("000000"))

        # Update PIN with correct vs wrong master password
        self.assertFalse(auth_svc.update_pin("WrongMaster", "654321"))
        self.assertTrue(auth_svc.update_pin("MasterPassword2026", "654321"))
        self.assertTrue(auth_svc.verify_pin("654321"))
        self.assertFalse(auth_svc.verify_pin("123456"))

        # Update Master Password
        self.assertFalse(auth_svc.update_password("WrongOld", "NewMaster2026"))
        self.assertTrue(auth_svc.update_password("MasterPassword2026", "NewMaster2026"))
        self.assertTrue(auth_svc.verify_password("NewMaster2026"))
        self.assertFalse(auth_svc.verify_password("MasterPassword2026"))

        # Cleanup
        if test_profile_path.exists():
            test_profile_path.unlink()
        if custom_storage.exists():
            shutil.rmtree(custom_storage, ignore_errors=True)
        if new_storage.exists():
            shutil.rmtree(new_storage, ignore_errors=True)

    def test_sii_invoice_parser_and_creation(self):
        sample_path = Path("test_invoice/20231226_1.pdf")
        if not sample_path.exists():
            self.skipTest("Sample invoice PDF not found in test_invoice/")

        parsed = parse_sii_document(str(sample_path))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["number"], "27")
        self.assertEqual(parsed["net_amount"], 1350000.0)
        self.assertEqual(parsed["tax_amount"], 256500.0)
        self.assertEqual(parsed["total_amount"], 1606500.0)
        self.assertIn("RETAMALES", parsed["emisor_name"])
        self.assertEqual(parsed["issue_date"], "2023-12-26")

        # Create invoice using parsed supplier data
        fin_svc = FinanceService()
        inv = fin_svc.create_invoice(
            type=InvoiceType.RECEIVED,
            number=parsed["number"],
            issuer_name=parsed["emisor_name"],
            issuer_tax_id=parsed["emisor_tax_id"],
            receiver_name=parsed["receiver_name"],
            receiver_tax_id=parsed["receiver_tax_id"],
            net_amount=parsed["net_amount"],
            tax_amount=parsed["tax_amount"],
            total_amount=parsed["total_amount"],
            category="Servicios",
            notes=parsed.get("description", "")
        )
        self.assertIsNotNone(inv["id"])
        self.assertEqual(inv["number"], "27")

        # Verify list_invoices shows the provider name
        invoices = fin_svc.list_invoices(invoice_type=InvoiceType.RECEIVED)
        found = next((i for i in invoices if i["number"] == "27"), None)
        self.assertIsNotNone(found)
        self.assertIn("RETAMALES", found["client_name"])
        self.assertEqual(found["net_amount"], 1350000.0)
        self.assertEqual(found["total_amount"], 1606500.0)

    def test_phase2_document_management_and_payment_evidence(self):
        """Valida gestión documental de Fase 2: adjuntos retroactivos a facturas y vouchers de pago."""
        fin_svc = FinanceService()

        # 1. Crear factura sin documento adjunto
        inv = fin_svc.create_invoice(
            type=InvoiceType.ISSUED,
            number="TEST-F2-001",
            net_amount=100000,
            tax_amount=19000,
            total_amount=119000,
            category="Consultoría"
        )
        inv_id = inv["id"]
        inv_detail = fin_svc.get_invoice(inv_id)
        self.assertIsNotNone(inv_detail)
        self.assertFalse(bool(inv_detail["document_path"]))

        # 2. Adjuntar factura retroactivamente
        dummy_invoice_file = DATA_DIR / "dummy_factura.pdf"
        dummy_invoice_file.write_text("DUMMY INVOICE CONTENT", encoding="utf-8")
        try:
            saved_inv_path = fin_svc.attach_invoice_document(inv_id, str(dummy_invoice_file))
            self.assertIsNotNone(saved_inv_path)
            self.assertTrue(Path(saved_inv_path).exists())

            inv_updated = fin_svc.get_invoice(inv_id)
            self.assertEqual(inv_updated["document_path"], saved_inv_path)

            # 3. Registrar pago parcial sin voucher
            pay_res = fin_svc.register_payment(
                invoice_id=inv_id,
                amount=50000,
                payment_method="Transferencia",
                reference="TR-001"
            )
            pay_id = pay_res["payment_id"]
            self.assertEqual(pay_res["balance"], 69000.0)
            self.assertEqual(pay_res["status"], PaymentStatus.PARTIAL)

            inv_after_pay = fin_svc.get_invoice(inv_id)
            payment_item = next(p for p in inv_after_pay["payments"] if p["id"] == pay_id)
            self.assertEqual(payment_item["evidence_path"], "")

            # 4. Adjuntar comprobante de pago (voucher) retroactivamente
            dummy_voucher = DATA_DIR / "dummy_voucher.png"
            dummy_voucher.write_text("DUMMY VOUCHER RECEIPT", encoding="utf-8")
            try:
                saved_voucher_path = fin_svc.attach_payment_evidence(pay_id, str(dummy_voucher))
                self.assertIsNotNone(saved_voucher_path)
                self.assertTrue(Path(saved_voucher_path).exists())

                inv_after_voucher = fin_svc.get_invoice(inv_id)
                v_item = next(p for p in inv_after_voucher["payments"] if p["id"] == pay_id)
                self.assertEqual(v_item["evidence_path"], saved_voucher_path)
            finally:
                if dummy_voucher.exists():
                    dummy_voucher.unlink()
        finally:
            if dummy_invoice_file.exists():
                dummy_invoice_file.unlink()

    def test_phase3_dashboard_and_traceability(self):
        """Valida que los servicios de la Fase 3 calculen indicadores, vencimientos, documentación y timeline."""
        dash_svc = DashboardService()

        # 1. Indicadores extendidos
        metrics = dash_svc.get_metrics()
        self.assertIn("collection_rate", metrics)
        self.assertIn("payment_rate", metrics)
        self.assertIn("avg_project_progress", metrics)
        self.assertIn("missing_invoice_docs", metrics)
        self.assertIn("missing_vouchers", metrics)
        self.assertIn("missing_po_docs", metrics)
        self.assertIsInstance(metrics["collection_rate"], float)
        self.assertIsInstance(metrics["payment_rate"], float)

        # 2. Vencimientos y pendientes
        deadlines = dash_svc.get_deadlines()
        self.assertIsInstance(deadlines, list)
        if deadlines:
            dl = deadlines[0]
            self.assertIn("type_label", dl)
            self.assertIn("number", dl)
            self.assertIn("counterparty", dl)
            self.assertIn("days_diff", dl)
            self.assertIn("is_overdue", dl)
            self.assertIn("balance", dl)

        # 3. Auditoría de documentación faltante
        missing_audit = dash_svc.get_missing_documentation()
        self.assertIn("invoices", missing_audit)
        self.assertIn("payments", missing_audit)
        self.assertIn("purchase_orders", missing_audit)
        self.assertIn("total_missing", missing_audit)
        self.assertEqual(
            missing_audit["total_missing"],
            len(missing_audit["invoices"]) + len(missing_audit["payments"]) + len(missing_audit["purchase_orders"])
        )

        # 4. Línea de tiempo de actividad (Timeline)
        timeline = dash_svc.get_activity_timeline(limit=10)
        self.assertIsInstance(timeline, list)
        if timeline:
            ev = timeline[0]
            self.assertIn("timestamp", ev)
            self.assertIn("date_str", ev)
            self.assertIn("category", ev)
            self.assertIn("title", ev)
            self.assertIn("description", ev)

    def test_export_service_phase4(self):
        """Valida que ExportService genere libros contables, conciliación y reportes HTML."""
        exp_svc = ExportService()

        # 1. Presets de fecha
        start_m, end_m = exp_svc.get_preset_dates("THIS_MONTH")
        self.assertTrue(len(start_m) == 10 and len(end_m) == 10)
        self.assertTrue(start_m <= end_m)

        start_lm, end_lm = exp_svc.get_preset_dates("LAST_MONTH")
        self.assertTrue(len(start_lm) == 10 and len(end_lm) == 10)
        self.assertTrue(start_lm <= end_lm)

        start_y, end_y = exp_svc.get_preset_dates("THIS_YEAR")
        self.assertTrue(start_y.endswith("-01-01"))

        # 2. Resumen de período (período amplio para abarcar datos de tests anteriores)
        summary = exp_svc.get_period_summary("2020-01-01", "2030-12-31")
        self.assertIn("sales_net", summary)
        self.assertIn("sales_vat_debit", summary)
        self.assertIn("purchases_vat_credit", summary)
        self.assertIn("f29_estimated_vat", summary)
        self.assertIn("cashflow_collected", summary)
        self.assertIn("cashflow_paid", summary)
        self.assertIn("cashflow_net", summary)

        # 3. Exportación de Libro de Ventas (CSV)
        sales_csv = exp_svc.export_sales_book_csv("2020-01-01", "2030-12-31", delimiter=";")
        self.assertTrue(Path(sales_csv).exists())
        content_sales = Path(sales_csv).read_text(encoding="utf-8-sig")
        self.assertIn("Folio Factura;Tipo DTE", content_sales)
        self.assertIn("RUT Receptor / Cliente", content_sales)

        # 4. Exportación de Libro de Compras (CSV)
        purchases_csv = exp_svc.export_purchases_book_csv("2020-01-01", "2030-12-31", delimiter=";")
        self.assertTrue(Path(purchases_csv).exists())
        content_purchases = Path(purchases_csv).read_text(encoding="utf-8-sig")
        self.assertIn("Folio Factura;Tipo DTE", content_purchases)
        self.assertIn("RUT Emisor / Proveedor", content_purchases)

        # 5. Exportación de Conciliación de Pagos (CSV)
        reconcile_csv = exp_svc.export_payments_reconciliation_csv("2020-01-01", "2030-12-31", delimiter=";")
        self.assertTrue(Path(reconcile_csv).exists())
        content_reconcile = Path(reconcile_csv).read_text(encoding="utf-8-sig")
        self.assertIn("ID Pago;Fecha Pago;Tipo Flujo;Folio Factura;Contraparte", content_reconcile)

        # 6. Exportación de Documentos Faltantes (CSV)
        missing_csv = exp_svc.export_missing_documents_csv(delimiter=";")
        self.assertTrue(Path(missing_csv).exists())
        content_missing = Path(missing_csv).read_text(encoding="utf-8-sig")
        self.assertIn("Categoría;Tipo de Documento;Identificador / Folio", content_missing)

        # 7. Generación de Reporte Ejecutivo Financiero (HTML)
        exec_html = exp_svc.generate_executive_report_html("2020-01-01", "2030-12-31")
        self.assertTrue(Path(exec_html).exists())
        content_html = Path(exec_html).read_text(encoding="utf-8")
        self.assertIn("REPORTE CONTABLE Y FINANCIERO", content_html)
        self.assertIn("window.print()", content_html)

        # 8. Generación de Reporte de Auditoría de Documentos Faltantes (HTML)
        missing_html = exp_svc.generate_missing_documents_report_html()
        self.assertTrue(Path(missing_html).exists())
        content_m_html = Path(missing_html).read_text(encoding="utf-8")
        self.assertIn("Auditoría de Documentación Faltante", content_m_html)
        self.assertIn("window.print()", content_m_html)


if __name__ == "__main__":
    unittest.main()
