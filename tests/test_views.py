import unittest
from unittest.mock import MagicMock
import flet as ft
from app.db.session import init_db
from app.main import main
from app.views.dashboard_view import DashboardView
from app.views.company_view import CompanyView
from app.views.clients_view import ClientsView
from app.views.quotes_view import QuotesView
from app.views.projects_view import ProjectsView
from app.views.finances_view import FinancesView
from app.views.exports_view import ExportsView
from app.views.settings_view import SettingsView
from app.views.auth_view import AuthView
from app.services.auth_service import AuthService


class TestViewsInstantiation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.mock_page = MagicMock(spec=ft.Page)
        self.mock_page.overlay = []
        self.mock_page.services = []

    def test_dashboard_view(self):
        view = DashboardView(self.mock_page)
        self.assertIsNotNone(view.content)
        view.open_missing_docs_modal()
        view.refresh()

    def test_company_view(self):
        view = CompanyView(self.mock_page)
        self.assertIsNotNone(view.content)

    def test_clients_view(self):
        view = ClientsView(self.mock_page)
        self.assertIsNotNone(view.content)

    def test_quotes_view(self):
        view = QuotesView(self.mock_page)
        self.assertIsNotNone(view.content)

    def test_projects_view(self):
        view = ProjectsView(self.mock_page)
        self.assertIsNotNone(view.content)

    def test_finances_view(self):
        view = FinancesView(self.mock_page)
        self.assertIsNotNone(view.content)
        self.assertEqual(view.current_subview, "ALL_INVOICES")
        view.switch_subview("ISSUED_INVOICES")
        self.assertEqual(view.current_subview, "ISSUED_INVOICES")
        view.switch_subview("RECEIVED_INVOICES")
        self.assertEqual(view.current_subview, "RECEIVED_INVOICES")
        view.switch_subview("PURCHASE_ORDERS")
        self.assertEqual(view.current_subview, "PURCHASE_ORDERS")

    def test_exports_view(self):
        view = ExportsView(self.mock_page)
        self.assertIsNotNone(view.content)
        # Test preset change
        view.preset_dropdown.value = "THIS_YEAR"
        view.on_preset_changed(None)
        self.assertTrue(view.start_date_field.value.endswith("-01-01"))
        # Test manual summary and recent files refresh
        view.refresh_summary()
        view.refresh_recent_files()
        # Test export triggers
        view.export_sales_book()
        view.export_purchases_book()
        view.export_payments()
        view.export_executive_html()
        view.export_missing_csv()
        view.export_missing_html()
        self.assertIsNotNone(view.recent_files_container.content)

    def test_settings_view(self):
        view = SettingsView(self.mock_page)
        self.assertIsNotNone(view.content)

    def test_auth_view(self):
        auth_service = AuthService()
        auth_view = AuthView(
            auth_service=auth_service,
            on_authenticated=lambda: None,
            page_ref=self.mock_page,
        )
        control = auth_view.build()
        self.assertIsNotNone(control)

    def test_main_shell_layout(self):
        main(self.mock_page)
        self.assertTrue(self.mock_page.add.called)
        self.assertTrue(self.mock_page.update.called)


if __name__ == "__main__":
    unittest.main()
