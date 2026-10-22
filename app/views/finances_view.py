import logging
import os
from typing import Optional, List, Callable
import flet as ft
from app.services.finance_service import FinanceService, save_document, open_document, DEFAULT_EXPENSE_CATEGORIES
from app.services.purchase_order_service import PurchaseOrderService
from app.services.client_service import ClientService
from app.services.quote_service import QuoteService
from app.services.company_service import CompanyService
from app.services.sii_invoice_parser import parse_sii_document
from app.services.ai_service import AIService
from app.services.currency_service import format_currency
from app.models.invoice import InvoiceType, PaymentStatus
from app.components.cards import SectionHeader, StatusChip, StatCard, open_dialog, close_dialog, show_snackbar
from app.constant import (
    TABLE_BGCOLOR,
    CARD_ALT_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_HINT,
    TEXT_LIGHT,
    BTN_PRIMARY_BG,
    BTN_SUCCESS_BG,
    BTN_DANGER_ICON,
    BTN_ACCENT_BG,
    INVOICE_ISSUED_BG,
    INVOICE_RECEIVED_BG,
    INVOICE_CREDIT_NOTE_BG,
    METRIC_PROJECT_COLOR,
    METRIC_SUCCESS_COLOR,
    METRIC_ALERT_COLOR,
    BALANCE_POSITIVE_COLOR,
    BALANCE_NEGATIVE_COLOR,
)

logger = logging.getLogger(__name__)


class FinancesView(ft.Container):
    def __init__(self, page: ft.Page, on_navigate_tab: Optional[Callable[[int], None]] = None) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.on_navigate_tab = on_navigate_tab
        self.finance_service = FinanceService()
        self.po_service = PurchaseOrderService()
        self.client_service = ClientService()
        self.quote_service = QuoteService()
        self.company_service = CompanyService()
        self.ai_service = AIService()

        # Active tab: "ALL_INVOICES", "ISSUED_INVOICES", "RECEIVED_INVOICES", "PURCHASE_ORDERS"
        self.current_subview = "ALL_INVOICES"
        self.kpis_container = ft.Container(padding=ft.Padding.only(bottom=12))

        # FilePicker for document attachments
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.active_file_target = None  # Reference to the control or callback expecting the picked file

        # Invoices Filters
        self.type_filter = ft.Dropdown(
            label="Tipo de Factura",
            options=[
                ft.dropdown.Option(key="ALL", text="Todas las Facturas"),
                ft.dropdown.Option(key=InvoiceType.ISSUED, text="Facturas Emitidas (Ventas)"),
                ft.dropdown.Option(key=InvoiceType.RECEIVED, text="Facturas Recibidas (Gastos)"),
                ft.dropdown.Option(key=InvoiceType.CREDIT_NOTE, text="Notas de Crédito (SII)"),
            ],
            value="ALL",
            width=220,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        self.category_filter = ft.Dropdown(
            label="Categoría de Gasto",
            options=[ft.dropdown.Option(key="ALL", text="Todas las Categorías")] + [
                ft.dropdown.Option(key=cat, text=cat) for cat in DEFAULT_EXPENSE_CATEGORIES
            ],
            value="ALL",
            width=260,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        self.client_filter = ft.Dropdown(
            label="Cliente / Contraparte",
            options=[ft.dropdown.Option(key="ALL", text="Todos los Clientes")],
            value="ALL",
            width=220,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        # Purchase Orders Filters
        self.po_status_filter = ft.Dropdown(
            label="Estado OC",
            options=[
                ft.dropdown.Option(key="ALL", text="Todos los Estados"),
                ft.dropdown.Option(key="ACCEPTED", text="Aceptada"),
                ft.dropdown.Option(key="PENDING", text="Pendiente"),
                ft.dropdown.Option(key="REJECTED", text="Rechazada"),
                ft.dropdown.Option(key="CANCELLED", text="Cancelada"),
            ],
            value="ALL",
            width=180,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        self.po_client_filter = ft.Dropdown(
            label="Cliente",
            options=[ft.dropdown.Option(key="ALL", text="Todos los Clientes")],
            value="ALL",
            width=220,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        self.table_container = ft.Container(expand=True)
        self.header_action_button = ft.Container()
        self.build_ui()

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            picked_path = e.files[0].path
            picked_name = e.files[0].name
            if callable(self.active_file_target):
                self.active_file_target(picked_path, picked_name)
            elif isinstance(self.active_file_target, ft.TextField):
                self.active_file_target.value = picked_path
                if self.page_ref:
                    self.page_ref.update()

    def trigger_file_picker(self, target_callback_or_field) -> None:
        # DECISIÓN TÉCNICA: En Flet 1.0+, FilePicker hereda de Service y debe residir en page.services,
        # NUNCA en page.overlay (que generaría TimeoutException en el cliente Flutter al invocar pick_files).
        self.active_file_target = target_callback_or_field
        if self.page_ref and hasattr(self.page_ref, "services") and self.file_picker not in self.page_ref.services:
            self.page_ref.services.append(self.file_picker)
            self.page_ref.update()

        async def _pick() -> None:
            try:
                files = await self.file_picker.pick_files(
                    allow_multiple=False,
                    allowed_extensions=["pdf", "png", "jpg", "jpeg", "docx", "xlsx"]
                )
                if files and len(files) > 0:
                    picked_path = files[0].path
                    picked_name = files[0].name
                    if callable(self.active_file_target):
                        self.active_file_target(picked_path, picked_name)
                    elif isinstance(self.active_file_target, ft.TextField):
                        self.active_file_target.value = picked_path
                        if self.page_ref:
                            self.page_ref.update()
            except Exception as ex:
                logger.error("Error al invocar FilePicker en Finanzas: %s", ex)
                if self.page_ref:
                    show_snackbar(self.page_ref, f"Error al abrir selector de archivos: {ex}", is_error=True)

        if self.page_ref:
            self.page_ref.run_task(_pick)

    def refresh_client_options(self):
        clients = self.client_service.list_clients()
        seen = set()
        options = [ft.dropdown.Option(key="ALL", text="Todos los Clientes")]
        for c in clients:
            name = c["name"].strip()
            if name and name not in seen:
                seen.add(name)
                options.append(ft.dropdown.Option(key=str(c["id"]), text=name))
        self.client_filter.options = options
        self.po_client_filter.options = options

    def switch_subview(self, subview: str):
        self.current_subview = subview
        if subview == "ALL_INVOICES":
            self.type_filter.value = "ALL"
        elif subview == "ISSUED_INVOICES":
            self.type_filter.value = InvoiceType.ISSUED
        elif subview == "RECEIVED_INVOICES":
            self.type_filter.value = InvoiceType.RECEIVED
        self.build_header_and_filters()
        self.load_data()

    def build_ui(self):
        # DECISIÓN TÉCNICA: Registrar FilePicker como Service de la página
        if self.page_ref and hasattr(self.page_ref, "services") and self.file_picker not in self.page_ref.services:
            self.page_ref.services.append(self.file_picker)

        self.refresh_client_options()
        self.build_header_and_filters()

    def build_header_and_filters(self):
        is_po = self.current_subview == "PURCHASE_ORDERS"

        # Action Button based on active view
        controls_list: List[ft.Control] = []
        if self.on_navigate_tab:
            controls_list.append(
                ft.OutlinedButton(
                    "Exportar / Reportes",
                    icon=ft.Icons.FILE_DOWNLOAD_ROUNDED,
                    tooltip="Abrir panel de exportaciones y reportes tributarios para contador",
                    on_click=lambda _: self.on_navigate_tab(6) if self.on_navigate_tab else None,
                )
            )

        if not is_po:
            controls_list.extend([
                ft.OutlinedButton(
                    "Cargar Factura SII",
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    on_click=lambda _: self.trigger_file_picker(
                        lambda path, name: self.open_create_invoice_modal(
                            initial_file_path=path, initial_file_name=name
                        )
                    ),
                ),
                ft.FilledButton(
                    "Registrar Factura",
                    icon=ft.Icons.RECEIPT_LONG_ROUNDED,
                    on_click=lambda _: self.open_create_invoice_modal(),
                    bgcolor=BTN_PRIMARY_BG,
                ),
            ])
        else:
            controls_list.append(
                ft.FilledButton(
                    "Nueva Orden de Compra",
                    icon=ft.Icons.NOTE_ADD_ROUNDED,
                    on_click=lambda _: self.open_create_po_modal(),
                    bgcolor=BTN_PRIMARY_BG,
                )
            )

        action_btn = ft.Row(controls=controls_list, spacing=8)

        header = SectionHeader(
            title="Gestión Documental y Financiera",
            subtitle=(
                "Control integral de facturación emitida, facturas recibidas (gastos), órdenes de compra, "
                "pagos y evidencias"
            ),
            action_button=action_btn
        )

        # 4 First-class Subview Tabs for Phase 2
        is_all = self.current_subview == "ALL_INVOICES"
        is_issued = self.current_subview == "ISSUED_INVOICES"
        is_received = self.current_subview == "RECEIVED_INVOICES"

        subview_switcher = ft.Container(
            content=ft.Row(
                controls=[
                    ft.FilledButton(
                        "Todas las Facturas",
                        icon=ft.Icons.RECEIPT_LONG_ROUNDED,
                        bgcolor=BTN_PRIMARY_BG if is_all else ft.Colors.BLUE_GREY_100,
                        color=TEXT_LIGHT if is_all else TEXT_PRIMARY,
                        on_click=lambda _: self.switch_subview("ALL_INVOICES")
                    ),
                    ft.FilledButton(
                        "Facturas Emitidas (Ventas)",
                        icon=ft.Icons.TRENDING_UP_ROUNDED,
                        bgcolor=INVOICE_ISSUED_BG if is_issued else ft.Colors.BLUE_GREY_100,
                        color=TEXT_LIGHT if is_issued else TEXT_PRIMARY,
                        on_click=lambda _: self.switch_subview("ISSUED_INVOICES")
                    ),
                    ft.FilledButton(
                        "Facturas Recibidas (Gastos)",
                        icon=ft.Icons.TRENDING_DOWN_ROUNDED,
                        bgcolor=INVOICE_RECEIVED_BG if is_received else ft.Colors.BLUE_GREY_100,
                        color=TEXT_LIGHT if is_received else TEXT_PRIMARY,
                        on_click=lambda _: self.switch_subview("RECEIVED_INVOICES")
                    ),
                    ft.FilledButton(
                        "Órdenes de Compra (OC)",
                        icon=ft.Icons.DESCRIPTION_ROUNDED,
                        bgcolor=METRIC_PROJECT_COLOR if is_po else ft.Colors.BLUE_GREY_100,
                        color=TEXT_LIGHT if is_po else TEXT_PRIMARY,
                        on_click=lambda _: self.switch_subview("PURCHASE_ORDERS")
                    ),
                ],
                spacing=8,
            ),
            padding=ft.Padding.only(bottom=8),
        )

        # Filters Bar based on active subview
        if not is_po:
            filter_controls = [
                self.type_filter,
                self.category_filter,
                self.client_filter,
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    tooltip="Recargar",
                    on_click=lambda _: self.load_data()
                )
            ]
        else:
            filter_controls = [
                self.po_status_filter,
                self.po_client_filter,
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    tooltip="Recargar",
                    on_click=lambda _: self.load_data()
                )
            ]

        filter_bar = ft.Container(
            content=ft.Row(controls=filter_controls, spacing=12),
            padding=ft.Padding.symmetric(vertical=4),
        )

        self.content = ft.Column(
            controls=[
                header,
                subview_switcher,
                self.kpis_container,
                filter_bar,
                ft.Container(height=8),
                self.table_container,
            ],
            spacing=0,
            expand=True,
        )

        self.load_data()

    def load_data(self):
        if self.current_subview == "PURCHASE_ORDERS":
            self.load_purchase_orders()
        else:
            self.load_invoices()

    # =========================================================================
    # 1. SECCIÓN FACTURACIÓN Y PAGOS
    # =========================================================================
    def load_invoices(self):
        type_val = self.type_filter.value
        inv_type = None if type_val == "ALL" else type_val

        cat_val = self.category_filter.value
        category = None if cat_val == "ALL" else cat_val

        client_val = self.client_filter.value
        client_id = None if client_val == "ALL" else int(client_val)

        invoices = self.finance_service.list_invoices(
            invoice_type=inv_type,
            client_id=client_id,
            category=category
        )

        # Compute Executive KPI Metrics for Invoices
        all_invs = self.finance_service.list_invoices()
        issued = [i for i in all_invs if i["type"] == InvoiceType.ISSUED]
        received = [i for i in all_invs if i["type"] == InvoiceType.RECEIVED]
        tot_issued = sum(i["total_amount"] for i in issued)
        paid_issued = sum(i["total_paid"] for i in issued)
        pending_collect = sum(i["balance"] for i in issued)
        issued_docs = sum(1 for i in issued if i["has_document"])

        tot_received = sum(i["total_amount"] for i in received)
        paid_received = sum(i["total_paid"] for i in received)
        pending_pay = sum(i["balance"] for i in received)
        received_docs = sum(1 for i in received if i["has_document"])
        tot_docs = sum(1 for i in all_invs if i["has_document"])

        if self.current_subview == "ISSUED_INVOICES":
            self.kpis_container.content = ft.Row(
                controls=[
                    StatCard(
                        "Total Facturado",
                        format_currency(tot_issued),
                        f"{len(issued)} facturas emitidas",
                        ft.Icons.TRENDING_UP_ROUNDED,
                        INVOICE_ISSUED_BG
                    ),
                    StatCard(
                        "Cobrado Efectivo",
                        format_currency(paid_issued),
                        "Pagos de clientes percibidos",
                        ft.Icons.CHECK_CIRCLE_ROUNDED,
                        METRIC_SUCCESS_COLOR
                    ),
                    StatCard(
                        "Por Cobrar",
                        format_currency(pending_collect),
                        "Cuentas activas por cobrar",
                        ft.Icons.PENDING_ACTIONS_ROUNDED,
                        METRIC_ALERT_COLOR
                    ),
                    StatCard(
                        "Respaldos Adjuntos",
                        f"{issued_docs} / {len(issued)}",
                        "Facturas con PDF/XML respaldado",
                        ft.Icons.ATTACH_FILE_ROUNDED,
                        METRIC_PROJECT_COLOR
                    ),
                ],
                spacing=12,
            )
        elif self.current_subview == "RECEIVED_INVOICES":
            self.kpis_container.content = ft.Row(
                controls=[
                    StatCard(
                        "Total Gastos / Compras",
                        format_currency(tot_received),
                        f"{len(received)} facturas proveedores",
                        ft.Icons.TRENDING_DOWN_ROUNDED,
                        INVOICE_RECEIVED_BG
                    ),
                    StatCard(
                        "Pagado a Proveedores",
                        format_currency(paid_received),
                        "Egresos efectivamente pagados",
                        ft.Icons.CHECK_CIRCLE_ROUNDED,
                        METRIC_SUCCESS_COLOR
                    ),
                    StatCard(
                        "Por Pagar (Deuda)",
                        format_currency(pending_pay),
                        "Obligaciones pendientes",
                        ft.Icons.HOURGLASS_EMPTY_ROUNDED,
                        METRIC_ALERT_COLOR
                    ),
                    StatCard(
                        "Respaldos Proveedor",
                        f"{received_docs} / {len(received)}",
                        "Facturas con respaldo digital",
                        ft.Icons.ATTACH_FILE_ROUNDED,
                        METRIC_PROJECT_COLOR
                    ),
                ],
                spacing=12,
            )
        else:
            balance_net = tot_issued - tot_received
            margin_color = BALANCE_POSITIVE_COLOR if balance_net >= 0 else BALANCE_NEGATIVE_COLOR
            self.kpis_container.content = ft.Row(
                controls=[
                    StatCard(
                        "Ventas Totales",
                        format_currency(tot_issued),
                        f"{len(issued)} facturas emitidas",
                        ft.Icons.TRENDING_UP_ROUNDED,
                        INVOICE_ISSUED_BG
                    ),
                    StatCard(
                        "Gastos Totales",
                        format_currency(tot_received),
                        f"{len(received)} facturas proveedores",
                        ft.Icons.TRENDING_DOWN_ROUNDED,
                        INVOICE_RECEIVED_BG
                    ),
                    StatCard(
                        "Margen Facturado",
                        format_currency(balance_net),
                        "Diferencia Ventas - Gastos",
                        ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                        margin_color
                    ),
                    StatCard(
                        "Respaldos Adjuntos",
                        f"{tot_docs} / {len(all_invs)}",
                        "Documentos digitales respaldados",
                        ft.Icons.FOLDER_SPECIAL_ROUNDED,
                        METRIC_PROJECT_COLOR
                    ),
                ],
                spacing=12,
            )

        rows = []
        for inv in invoices:
            is_issued = inv["type"] == InvoiceType.ISSUED
            is_nc = inv["type"] == InvoiceType.CREDIT_NOTE

            if is_nc:
                badge_bg = INVOICE_CREDIT_NOTE_BG
                badge_text = "Nota Crédito"
            elif is_issued:
                badge_bg = INVOICE_ISSUED_BG
                badge_text = "Emitida"
            else:
                badge_bg = INVOICE_RECEIVED_BG
                badge_text = "Recibida"

            type_badge = ft.Container(
                content=ft.Text(badge_text, size=9, weight=ft.FontWeight.BOLD, color=TEXT_LIGHT),
                bgcolor=badge_bg,
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            )

            # Number display with reference if Credit Note
            if is_nc and inv["reference_invoice_number"]:
                number_cell = ft.Column(
                    controls=[
                        ft.Text(inv["number"], weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(f"Ref: Fac #{inv['reference_invoice_number']}", size=10, color=TEXT_HINT),
                    ],
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            else:
                number_cell = ft.Text(inv["number"], weight=ft.FontWeight.BOLD, size=13)

            # Counterparty / Client with project indicator
            if inv["project_name"]:
                client_cell = ft.Column(
                    controls=[
                        ft.Text(inv["client_name"], size=13),
                        ft.Text(
                            f"📁 {inv['project_name']}",
                            size=11,
                            color=METRIC_PROJECT_COLOR,
                            weight=ft.FontWeight.W_500
                        ),
                    ],
                    spacing=1,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            else:
                client_cell = ft.Text(inv["client_name"])

            # Interactive icon to open document
            if inv["has_document"]:
                doc_control = ft.IconButton(
                    icon=ft.Icons.ATTACH_FILE_ROUNDED,
                    icon_color=METRIC_SUCCESS_COLOR,
                    tooltip="Clic para abrir documento adjunto",
                    icon_size=18,
                    on_click=lambda _, p=inv["document_path"]: self.open_file_safe(p)
                )
            else:
                doc_control = ft.Icon(
                    ft.Icons.FILE_PRESENT_OUTLINED,
                    size=16,
                    color=METRIC_ALERT_COLOR,
                    tooltip="Sin documento adjunto"
                )

            actions = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.PAYMENTS_ROUNDED,
                        tooltip="Registrar Pago",
                        icon_size=18,
                        icon_color=BTN_SUCCESS_BG,
                        visible=(inv["balance"] > 0 and not is_nc and inv["status"] != PaymentStatus.ANNULLED),
                        on_click=lambda _, iid=inv["id"]: self.open_payment_modal(iid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ASSIGNMENT_RETURN_ROUNDED,
                        tooltip="Emitir Nota de Crédito SII (anular o corregir)",
                        icon_size=18,
                        icon_color=ft.Colors.PURPLE_600,
                        visible=(not is_nc and inv["status"] != PaymentStatus.ANNULLED),
                        on_click=lambda _, iid=inv["id"]: self.open_credit_note_modal(iid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY_OUTLINED,
                        tooltip="Ver Historial de Pagos, Notas de Crédito y Evidencias",
                        icon_size=18,
                        on_click=lambda _, iid=inv["id"]: self.open_invoice_detail_modal(iid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        tooltip="Modificar Factura",
                        icon_size=18,
                        visible=(not is_nc and inv["status"] != PaymentStatus.ANNULLED),
                        on_click=lambda _, iid=inv["id"]: self.open_edit_invoice_modal(iid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.LINK_OFF_ROUNDED,
                        tooltip=f"Desvincular del proyecto '{inv['project_name']}'",
                        icon_size=18,
                        icon_color=ft.Colors.ORANGE_800,
                        visible=bool(inv["project_id"]),
                        on_click=lambda _, iid=inv["id"], num=inv["number"], pnm=inv["project_name"]: (
                            self.confirm_unlink_from_finances(iid, num, pnm)
                        )
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        tooltip="Eliminar Factura (con motivo)",
                        icon_size=18,
                        icon_color=BTN_DANGER_ICON,
                        on_click=lambda _, iid=inv["id"], num=inv["number"]: self.confirm_delete_invoice_modal(iid, num)
                    )
                ],
                spacing=0,
            )

            balance_color = BALANCE_NEGATIVE_COLOR if inv["balance"] > 0 else TEXT_PRIMARY

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(type_badge),
                        ft.DataCell(number_cell),
                        ft.DataCell(client_cell),
                        ft.DataCell(ft.Text(inv["category"], size=12)),
                        ft.DataCell(ft.Text(inv["issue_date"])),
                        ft.DataCell(ft.Text(inv["due_date"])),
                        ft.DataCell(ft.Text(format_currency(inv["total_amount"]))),
                        ft.DataCell(ft.Text(format_currency(inv["total_paid"]), color=BALANCE_POSITIVE_COLOR)),
                        ft.DataCell(
                            ft.Text(format_currency(inv["balance"]), weight=ft.FontWeight.BOLD, color=balance_color)
                        ),
                        ft.DataCell(StatusChip(inv["status"])),
                        ft.DataCell(doc_control),
                        ft.DataCell(actions),
                    ]
                )
            )

        if not rows:
            self.table_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_ROUNDED, size=48, color=TEXT_HINT),
                        ft.Text("No hay facturas registradas con los filtros seleccionados", color=TEXT_MUTED, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=40,
                alignment=ft.Alignment(0, 0),
                bgcolor=TABLE_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
            )
        else:
            self.table_container.content = ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("Tipo", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("N°", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Contraparte / Cliente", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Categoría", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Emisión", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Vencimiento", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Pagado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Saldo", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Doc", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12)),
                            ],
                            rows=rows,
                            heading_row_height=42,
                            data_row_min_height=48,
                            column_spacing=14,
                        )
                    ],
                    expand=True,
                ),
                bgcolor=TABLE_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
                expand=True,
            )

        if self.page_ref:
            self.page_ref.update()

    def open_file_safe(self, path: str):
        if not path or not os.path.exists(path):
            show_snackbar(self.page_ref, "El archivo adjunto no existe o no se encuentra disponible.", is_error=True)
            return
        success = open_document(path)
        if not success:
            show_snackbar(self.page_ref, f"No se pudo abrir el archivo en: {path}", is_error=True)

    def open_create_invoice_modal(
        self,
        initial_file_path: Optional[str] = None,
        initial_file_name: Optional[str] = None
    ) -> None:
        clients = self.client_service.list_clients(active_only=True)

        type_dropdown = ft.Dropdown(
            label="Tipo de Factura *",
            options=[
                ft.dropdown.Option(key=InvoiceType.ISSUED, text="Factura Emitida (Venta)"),
                ft.dropdown.Option(key=InvoiceType.RECEIVED, text="Factura Recibida (Gasto)"),
            ],
            value=InvoiceType.ISSUED,
            expand=True,
        )
        number_field = ft.TextField(label="N° Factura *", expand=True)

        client_dropdown = ft.Dropdown(
            label="Cliente asociado (para emitidas)",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients] if clients else [],
            expand=True,
        )
        client_container = ft.Container(
            content=client_dropdown,
            expand=True,
            visible=(type_dropdown.value == InvoiceType.ISSUED),
        )
        counterparty_field = ft.TextField(
            label=(
                "Proveedor / Emisor *"
                if type_dropdown.value == InvoiceType.RECEIVED
                else "Nombre Cliente / Receptor externo"
            ),
            expand=True,
        )

        net_field = ft.TextField(label="Monto Neto ($) *", value="100000", width=160)
        tax_field = ft.TextField(label="IVA 19% ($)", value="19000", width=160)
        total_field = ft.TextField(label="Total ($) *", value="119000", width=180)

        def on_net_change(e):
            try:
                net = float(net_field.value)
                tax = round(net * 0.19, 2)
                tot = round(net + tax, 2)
                tax_field.value = str(int(tax))
                total_field.value = str(int(tot))
                if self.page_ref:
                    self.page_ref.update()
            except ValueError:
                pass

        net_field.on_change = on_net_change

        category_dropdown = ft.Dropdown(
            label="Categoría de Gasto / Servicio",
            options=[ft.dropdown.Option(key=cat, text=cat) for cat in DEFAULT_EXPENSE_CATEGORIES],
            value=DEFAULT_EXPENSE_CATEGORIES[0],
            expand=True,
        )

        def classify_category_ai() -> None:
            desc = notes_field.value.strip() if notes_field.value else ""
            prov = counterparty_field.value.strip() if counterparty_field.value else ""
            if not desc and not prov:
                show_snackbar(
                    self.page_ref,
                    "Ingresa una glosa/descripción o emisor para clasificar el gasto.",
                    is_error=True,
                )
                return
            show_snackbar(self.page_ref, "Clasificando gasto con IA...")
            res = self.ai_service.classify_expense(
                description=desc,
                emisor=prov,
                allowed_categories=DEFAULT_EXPENSE_CATEGORIES,
            )
            cat = res.get("category")
            if cat and cat in DEFAULT_EXPENSE_CATEGORIES:
                category_dropdown.value = cat
                if self.page_ref:
                    self.page_ref.update()
                show_snackbar(self.page_ref, f"Categoría sugerida por IA: '{cat}'")

        ai_classify_btn = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            icon_color=ft.Colors.PURPLE_700,
            tooltip="Clasificar categoría de gasto con IA (Fase 6)",
            visible=self.ai_service.is_feature_enabled("classify_expenses"),
            on_click=lambda _: classify_category_ai(),
        )

        due_date_field = ft.TextField(label="Fecha Vencimiento (YYYY-MM-DD)", hint_text="Opcional", width=220)

        # File Attachment
        selected_file_text = ft.Text("Ningún archivo adjunto", size=12, color=TEXT_MUTED)
        attached_file_path = [None]
        parsed_doc_data: dict = {}

        def update_counterparty_from_parsed() -> None:
            inv_t = type_dropdown.value
            if inv_t == InvoiceType.RECEIVED:
                # DECISIÓN DE NEGOCIO: En facturas recibidas (gastos), el emisor es el Proveedor
                client_container.visible = False
                counterparty_field.label = "Proveedor / Emisor *"
                if parsed_doc_data:
                    prov = parsed_doc_data.get("emisor_name") or ""
                    counterparty_field.value = prov
            else:
                # En facturas emitidas (ventas), el receptor es el Cliente
                client_container.visible = True
                counterparty_field.label = "Nombre Cliente / Receptor externo (si no está registrado)"
                if parsed_doc_data:
                    r_rut = (
                        (parsed_doc_data.get("receiver_tax_id") or "")
                        .replace(".", "")
                        .replace("-", "")
                        .strip()
                        .upper()
                    )
                    r_name = (parsed_doc_data.get("receiver_name") or "").strip().upper()
                    matched_id = None
                    for c in clients:
                        c_rut = (c.get("tax_id") or "").replace(".", "").replace("-", "").strip().upper()
                        c_name = (c.get("name") or "").strip().upper()
                        rut_matches = bool(r_rut and c_rut and r_rut == c_rut)
                        name_matches = bool(r_name and c_name and (c_name in r_name or r_name in c_name))
                        if rut_matches or name_matches:
                            matched_id = str(c["id"])
                            break
                    if matched_id:
                        client_dropdown.value = matched_id
                        counterparty_field.value = ""
                    elif parsed_doc_data.get("receiver_name"):
                        client_dropdown.value = None
                        counterparty_field.value = parsed_doc_data["receiver_name"]

        type_dropdown.on_select = lambda _: (
            update_counterparty_from_parsed(),
            self.page_ref.update() if self.page_ref else None,
        )

        notes_field = ft.TextField(label="Notas adicionales", multiline=True, min_lines=2, expand=True)

        def on_doc_picked(path: str, name: str) -> None:
            attached_file_path[0] = path
            selected_file_text.value = f"Archivo listo: {name}"
            selected_file_text.color = METRIC_SUCCESS_COLOR

            # Auto-parse SII PDF / XML document
            parsed = parse_sii_document(path)

            # DECISIÓN DE ARQUITECTURA: Si la IA está habilitada para facturas,
            # consultamos al LLM agnóstico (Gemini / OpenRouter) para resolver
            # con alta precisión campos faltantes, folios complejos o PDFs no estándar.
            if self.ai_service.is_feature_enabled("invoices"):
                selected_file_text.value = f"🤖 Analizando con IA ({name})..."
                selected_file_text.color = ft.Colors.PURPLE_700
                if self.page_ref:
                    self.page_ref.update()

                ai_parsed = self.ai_service.extract_invoice_data(path, fallback_data=parsed)
                if ai_parsed:
                    parsed = ai_parsed

            if parsed:
                parsed_doc_data.clear()
                parsed_doc_data.update(parsed)

                if parsed.get("number"):
                    number_field.value = str(parsed["number"])
                if parsed.get("net_amount"):
                    net_field.value = str(int(parsed["net_amount"]))
                if parsed.get("tax_amount"):
                    tax_field.value = str(int(parsed["tax_amount"]))
                if parsed.get("total_amount"):
                    total_field.value = str(int(parsed["total_amount"]))
                if parsed.get("description"):
                    notes_field.value = parsed["description"]
                elif parsed.get("number"):
                    notes_field.value = f"Factura SII Folio #{parsed['number']}"
                if parsed.get("due_date"):
                    due_date_field.value = parsed["due_date"]
                elif parsed.get("issue_date"):
                    due_date_field.value = parsed["issue_date"]

                # DECISIÓN DE NEGOCIO:
                # Si el RUT del emisor es el mismo que el de mi empresa -> Emitida automáticamente.
                # En cualquier otro caso -> Recibida automáticamente.
                company = self.company_service.get_company()
                my_rut = (company.get("tax_id") or "").replace(".", "").replace("-", "").strip().upper()
                emisor_rut = (parsed.get("emisor_tax_id") or "").replace(".", "").replace("-", "").strip().upper()

                if my_rut and emisor_rut and my_rut == emisor_rut:
                    type_dropdown.value = InvoiceType.ISSUED
                else:
                    type_dropdown.value = InvoiceType.RECEIVED

                # Inferir categoría si la IA la determinó, o por heurística clásica
                if parsed.get("category") and parsed["category"] in DEFAULT_EXPENSE_CATEGORIES:
                    category_dropdown.value = parsed["category"]
                else:
                    desc_text = f"{parsed.get('description', '')} {parsed.get('emisor_name', '')}".lower()
                    if any(k in desc_text for k in ["cloud", "hosting", "servidor", "aws", "azure", "gcp"]):
                        category_dropdown.value = "Servicios Cloud & Hosting"
                    elif any(k in desc_text for k in ["software", "licencia", "saas", "github"]):
                        category_dropdown.value = "Licencias de Software"
                    elif any(
                        k in desc_text
                        for k in ["luz", "agua", "internet", "enel", "cge", "telecom", "movistar", "entel"]
                    ):
                        category_dropdown.value = "Servicios Básicos (Luz, Agua, Internet)"
                    elif any(k in desc_text for k in ["oficina", "papel", "insumos", "libreria"]):
                        category_dropdown.value = "Insumos de Oficina"
                    elif any(k in desc_text for k in ["marketing", "publicidad", "ads", "meta", "facebook"]):
                        category_dropdown.value = "Publicidad & Marketing"
                    elif any(k in desc_text for k in ["transporte", "flete", "uber", "cabify", "envio", "chilexpress"]):
                        category_dropdown.value = "Transporte & Logística"
                    elif any(k in desc_text for k in ["computador", "notebook", "hardware", "equipamiento"]):
                        category_dropdown.value = "Infraestructura & Equipamiento"
                    elif type_dropdown.value == InvoiceType.RECEIVED:
                        category_dropdown.value = "Servicios Profesionales & Honorarios"

                update_counterparty_from_parsed()

                sii_num = parsed.get("number", "")
                sii_tot = parsed.get("total_amount", 0)
                prov_label = (
                    parsed.get("emisor_name", "Proveedor")
                    if type_dropdown.value == InvoiceType.RECEIVED
                    else (parsed.get("receiver_name") or "Cliente")
                )
                type_label = "Emitida (Venta)" if type_dropdown.value == InvoiceType.ISSUED else "Recibida (Gasto)"

                if parsed.get("ai_processed"):
                    prov_title = self.ai_service.get_config().get("provider", "IA").capitalize()
                    selected_file_text.value = (
                        f"🤖 IA ({prov_title}) #{sii_num} | {type_label} | ${sii_tot:,.0f} | {name}"
                    )
                    selected_file_text.color = ft.Colors.PURPLE_700
                    show_snackbar(
                        self.page_ref,
                        f"🤖 Factura procesada con IA ({prov_title}): #{sii_num} - Total ${sii_tot:,.0f}"
                    )
                else:
                    selected_file_text.value = f"⚡ SII Folio #{sii_num} | {type_label} | ${sii_tot:,.0f} | {name}"
                    show_snackbar(
                        self.page_ref,
                        f"⚡ Factura #{sii_num} ({type_label}): '{prov_label[:25]}', Total ${sii_tot:,.0f}"
                    )
            else:
                show_snackbar(self.page_ref, f"No se pudo extraer información de {name}", is_error=True)

            if self.page_ref:
                self.page_ref.update()

        attach_btn = ft.OutlinedButton(
            "Cargar Factura SII (PDF / XML)",
            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_doc_picked)
        )

        def reanalyze_with_ai(e: ft.ControlEvent) -> None:
            if not attached_file_path[0]:
                show_snackbar(self.page_ref, "Primero adjunta un archivo para analizar con IA.", is_error=True)
                return
            if not self.ai_service.is_configured():
                show_snackbar(
                    self.page_ref,
                    "Configura tu API Key en 'Configuración -> Uso IA' para activar el análisis inteligente.",
                    is_error=True,
                )
                return
            on_doc_picked(
                attached_file_path[0],
                os.path.basename(attached_file_path[0])
            )

        ai_btn = ft.OutlinedButton(
            "Extraer con IA",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            on_click=reanalyze_with_ai,
        )

        dialog: Optional[ft.AlertDialog] = None

        def save_invoice(e: ft.ControlEvent) -> None:
            if not number_field.value.strip():
                show_snackbar(self.page_ref, "El número de factura es obligatorio.", is_error=True)
                return

            try:
                net = float(net_field.value)
                tax = float(tax_field.value)
                tot = float(total_field.value)
            except ValueError:
                show_snackbar(self.page_ref, "Montos numéricos inválidos.", is_error=True)
                return

            inv_type = type_dropdown.value
            client_id = (
                int(client_dropdown.value)
                if (inv_type == InvoiceType.ISSUED and client_dropdown.value)
                else None
            )
            counterparty = counterparty_field.value.strip()

            # Copy file to project documents directory if attached
            final_doc_path = None
            if attached_file_path[0]:
                subfolder = "invoices/issued" if inv_type == InvoiceType.ISSUED else "invoices/received"
                final_doc_path = save_document(
                    attached_file_path[0], subfolder, prefix=f"FAC_{number_field.value.strip()}"
                )

            self.finance_service.create_invoice(
                type=inv_type,
                number=number_field.value.strip(),
                client_id=client_id,
                issuer_name=(
                    counterparty or parsed_doc_data.get("emisor_name")
                    if inv_type == InvoiceType.RECEIVED else None
                ),
                issuer_tax_id=parsed_doc_data.get("emisor_tax_id") if inv_type == InvoiceType.RECEIVED else None,
                receiver_name=(
                    counterparty or parsed_doc_data.get("receiver_name")
                    if inv_type == InvoiceType.ISSUED and not client_id else None
                ),
                receiver_tax_id=parsed_doc_data.get("receiver_tax_id") if inv_type == InvoiceType.ISSUED else None,
                issue_date=parsed_doc_data.get("issue_date"),
                due_date=due_date_field.value.strip() or None,
                net_amount=net,
                tax_amount=tax,
                total_amount=tot,
                category=category_dropdown.value,
                document_path=final_doc_path,
                notes=notes_field.value.strip()
            )

            show_snackbar(self.page_ref, "Factura registrada exitosamente.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text("Registrar Factura", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([type_dropdown, number_field]),
                        ft.Row([client_container, counterparty_field]),
                        ft.Row([net_field, tax_field, total_field]),
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[category_dropdown, ai_classify_btn],
                                    spacing=4,
                                    expand=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                due_date_field,
                            ],
                            spacing=12,
                        ),
                        ft.Container(
                            content=ft.Row([
                                attach_btn,
                                ai_btn,
                                selected_file_text
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                            padding=ft.Padding.symmetric(vertical=4)
                        ),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=700,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Factura", on_click=save_invoice, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        if initial_file_path:
            on_doc_picked(initial_file_path, initial_file_name or os.path.basename(initial_file_path))

        open_dialog(self.page_ref, dialog)

    def open_edit_invoice_modal(self, invoice_id: int):
        inv = self.finance_service.get_invoice(invoice_id)
        if not inv:
            return

        clients = self.client_service.list_clients()
        client_dropdown = ft.Dropdown(
            label="Cliente asociado",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients],
            value=str(inv["client_id"]) if inv["client_id"] else None,
            expand=True,
        )
        number_field = ft.TextField(label="N° Factura *", value=inv["number"], expand=True)
        net_field = ft.TextField(label="Neto ($)", value=str(int(inv["net_amount"])), width=150)
        total_field = ft.TextField(label="Total ($)", value=str(int(inv["total_amount"])), width=160)

        category_dropdown = ft.Dropdown(
            label="Categoría",
            options=[ft.dropdown.Option(key=cat, text=cat) for cat in DEFAULT_EXPENSE_CATEGORIES],
            value=inv["category"] if inv["category"] in DEFAULT_EXPENSE_CATEGORIES else DEFAULT_EXPENSE_CATEGORIES[0],
            expand=True,
        )
        notes_field = ft.TextField(label="Notas", value=inv["notes"], multiline=True, min_lines=2)

        attached_file_path = [inv["document_path"]]
        status_label = (
            f"Archivo actual: {os.path.basename(inv['document_path'])}"
            if inv["document_path"] else "Sin documento adjunto"
        )
        file_status_text = ft.Text(
            status_label,
            size=12,
            color=METRIC_SUCCESS_COLOR if inv["document_path"] else TEXT_MUTED
        )

        def on_doc_picked(path, name):
            attached_file_path[0] = path
            file_status_text.value = f"Nuevo archivo seleccionado: {name}"
            file_status_text.color = METRIC_SUCCESS_COLOR
            if self.page_ref:
                self.page_ref.update()

        attach_btn = ft.OutlinedButton(
            "Cambiar / Adjuntar Documento",
            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_doc_picked)
        )

        dialog: Optional[ft.AlertDialog] = None

        def update_invoice(e: ft.ControlEvent) -> None:
            try:
                net = float(net_field.value)
                tot = float(total_field.value)
            except ValueError:
                show_snackbar(self.page_ref, "Valores numéricos inválidos.", is_error=True)
                return

            final_doc_path = attached_file_path[0]
            if attached_file_path[0] and attached_file_path[0] != inv["document_path"]:
                subfolder = "invoices/issued" if inv["type"] == InvoiceType.ISSUED else "invoices/received"
                final_doc_path = save_document(
                    attached_file_path[0], subfolder, prefix=f"FAC_{number_field.value.strip()}"
                )

            self.finance_service.update_invoice(
                invoice_id=invoice_id,
                number=number_field.value.strip(),
                client_id=int(client_dropdown.value) if client_dropdown.value else None,
                net_amount=net,
                total_amount=tot,
                category=category_dropdown.value,
                document_path=final_doc_path,
                notes=notes_field.value.strip()
            )
            show_snackbar(self.page_ref, f"Factura #{number_field.value} actualizada.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Modificar Factura #{inv['number']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([number_field, client_dropdown]),
                        ft.Row([net_field, total_field, category_dropdown]),
                        ft.Row([attach_btn, file_status_text], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=680,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Cambios", on_click=update_invoice, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_payment_modal(self, invoice_id: int):
        invoice = self.finance_service.get_invoice(invoice_id)
        if not invoice:
            return

        balance = invoice["balance"]
        amount_field = ft.TextField(label="Monto del Pago ($) *", value=str(int(balance)), width=180)
        method_dropdown = ft.Dropdown(
            label="Medio de Pago",
            options=[
                ft.dropdown.Option(key="Transferencia", text="Transferencia Bancaria"),
                ft.dropdown.Option(key="Efectivo", text="Efectivo"),
                ft.dropdown.Option(key="Cheque", text="Cheque"),
                ft.dropdown.Option(key="Tarjeta", text="Tarjeta de Débito/Crédito"),
                ft.dropdown.Option(key="Otro", text="Otro"),
            ],
            value="Transferencia",
            expand=True,
        )
        ref_field = ft.TextField(label="N° Operación / Referencia", expand=True)

        attached_evidence_path = [None]
        evidence_status_text = ft.Text("Sin comprobante adjunto", size=12, color=TEXT_MUTED)

        def on_evidence_picked(path, name):
            attached_evidence_path[0] = path
            evidence_status_text.value = f"Comprobante listo: {name}"
            evidence_status_text.color = METRIC_SUCCESS_COLOR
            if self.page_ref:
                self.page_ref.update()

        evidence_btn = ft.OutlinedButton(
            "Adjuntar Comprobante",
            icon=ft.Icons.RECEIPT_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_evidence_picked)
        )

        notes_field = ft.TextField(label="Notas", multiline=True, min_lines=2, expand=True)
        dialog = None

        def save_payment(e):
            try:
                pay_amt = float(amount_field.value)
                if pay_amt <= 0:
                    raise ValueError()
            except ValueError:
                show_snackbar(self.page_ref, "El monto debe ser un número positivo.", is_error=True)
                return

            final_evidence_path = None
            if attached_evidence_path[0]:
                final_evidence_path = save_document(
                    attached_evidence_path[0], "payments", prefix=f"PAY_{invoice['number']}"
                )

            self.finance_service.register_payment(
                invoice_id=invoice_id,
                amount=pay_amt,
                payment_method=method_dropdown.value,
                reference=ref_field.value.strip(),
                evidence_path=final_evidence_path,
                notes=notes_field.value.strip()
            )

            show_snackbar(self.page_ref, f"Pago de ${pay_amt:,.0f} registrado exitosamente.")
            if dialog:
                close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Registrar Pago para Factura #{invoice['number']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Row([
                                ft.Text(f"Total Factura: ${invoice['total_amount']:,.0f}"),
                                ft.Text(
                                    f"Saldo Pendiente: ${balance:,.0f}",
                                    weight=ft.FontWeight.BOLD,
                                    color=BALANCE_NEGATIVE_COLOR
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=10,
                            bgcolor=CARD_ALT_BGCOLOR,
                            border_radius=6,
                        ),
                        ft.Row([amount_field, method_dropdown]),
                        ref_field,
                        ft.Row([evidence_btn, evidence_status_text], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=620,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Confirmar Pago", on_click=save_payment, bgcolor=BTN_SUCCESS_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def _attach_evidence_to_payment(
        self, payment_id: int, file_path: str, invoice_id: int, dialog: Optional[ft.AlertDialog]
    ) -> None:
        saved = self.finance_service.attach_payment_evidence(payment_id, file_path)
        if saved:
            if self.page_ref:
                show_snackbar(self.page_ref, "Comprobante de pago adjuntado exitosamente.")
                if dialog:
                    close_dialog(self.page_ref, dialog)
                self.load_data()
                self.open_invoice_detail_modal(invoice_id)
        else:
            if self.page_ref:
                show_snackbar(self.page_ref, "No se pudo guardar el comprobante.", is_error=True)

    def _attach_document_to_invoice(
        self, invoice_id: int, file_path: str, dialog: Optional[ft.AlertDialog]
    ) -> None:
        saved = self.finance_service.attach_invoice_document(invoice_id, file_path)
        if saved:
            if self.page_ref:
                show_snackbar(self.page_ref, "Documento de factura adjuntado exitosamente.")
                if dialog:
                    close_dialog(self.page_ref, dialog)
                self.load_data()
                self.open_invoice_detail_modal(invoice_id)
        else:
            if self.page_ref:
                show_snackbar(self.page_ref, "No se pudo guardar el archivo adjunto.", is_error=True)

    def open_invoice_detail_modal(self, invoice_id: int) -> None:
        inv = self.finance_service.get_invoice(invoice_id)
        if not inv:
            return

        detail_dialog: Optional[ft.AlertDialog] = None

        payment_rows = []
        for p in inv["payments"]:
            # Evidence button or indicator
            if p["evidence_path"]:
                evidence_control = ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                            icon_color=METRIC_SUCCESS_COLOR,
                            icon_size=18,
                            tooltip="Clic para ver comprobante de transferencia",
                            on_click=lambda _, ep=p["evidence_path"]: self.open_file_safe(ep),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                            icon_color=TEXT_MUTED,
                            icon_size=16,
                            tooltip="Reemplazar comprobante",
                            on_click=lambda _, pid=p["id"]: self.trigger_file_picker(
                                lambda path, name, pid=pid: self._attach_evidence_to_payment(
                                    pid, path, invoice_id, detail_dialog
                                )
                            ),
                        ),
                    ],
                    spacing=0,
                )
            else:
                evidence_control = ft.OutlinedButton(
                    "Subir Voucher",
                    icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                    height=28,
                    style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8)),
                    on_click=lambda _, pid=p["id"]: self.trigger_file_picker(
                        lambda path, name, pid=pid: self._attach_evidence_to_payment(
                            pid, path, invoice_id, detail_dialog
                        )
                    ),
                )

            payment_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(p["payment_date"])),
                        ft.DataCell(ft.Text(format_currency(p["amount"]), weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(p["payment_method"])),
                        ft.DataCell(ft.Text(p["reference"])),
                        ft.DataCell(evidence_control),
                    ]
                )
            )

        fallback_payment_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text("Sin pagos registrados")),
                ft.DataCell(ft.Text("-")),
                ft.DataCell(ft.Text("-")),
                ft.DataCell(ft.Text("-")),
                ft.DataCell(ft.Text("-")),
            ]
        )

        payments_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Medio", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Referencia", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Comprobante", weight=ft.FontWeight.BOLD, size=12)),
            ],
            rows=payment_rows if payment_rows else [fallback_payment_row],
            heading_row_height=38,
            data_row_min_height=40,
            column_spacing=18,
        )

        # Credit notes table if any
        cn_rows = []
        for cn in inv.get("credit_notes", []):
            if cn["has_document"]:
                cn_doc_ctrl = ft.IconButton(
                    icon=ft.Icons.ATTACH_FILE_ROUNDED,
                    icon_color=METRIC_SUCCESS_COLOR,
                    icon_size=16,
                    tooltip="Abrir archivo de Nota de Crédito",
                    on_click=lambda _, p=cn["document_path"]: self.open_file_safe(p)
                )
            else:
                cn_doc_ctrl = ft.Text("-", size=11, color=TEXT_MUTED)

            cn_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(cn["number"], weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataCell(
                            ft.Text(format_currency(cn["total_amount"]), size=12, color=ft.Colors.PURPLE_800)
                        ),
                        ft.DataCell(ft.Text(cn["reason"] or "-", size=11)),
                        ft.DataCell(ft.Text(cn["issue_date"] or "-", size=11)),
                        ft.DataCell(cn_doc_ctrl),
                    ]
                )
            )

        cn_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("N° NC", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Monto NC", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Motivo SII", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Doc", weight=ft.FontWeight.BOLD, size=11)),
            ],
            rows=cn_rows if cn_rows else [],
            heading_row_height=34,
            data_row_min_height=36,
            column_spacing=14,
        )

        if inv["type"] == InvoiceType.CREDIT_NOTE:
            type_str = "Nota de Crédito"
        elif inv["type"] == InvoiceType.ISSUED:
            type_str = "Emitida"
        else:
            type_str = "Recibida"

        bal_color = BALANCE_NEGATIVE_COLOR if inv['balance'] > 0 else TEXT_PRIMARY

        doc_control = (
            ft.TextButton(
                "Abrir documento adjunto",
                icon=ft.Icons.ATTACH_FILE_ROUNDED,
                on_click=lambda _: self.open_file_safe(inv["document_path"])
            ) if inv["document_path"] else ft.OutlinedButton(
                "Adjuntar Factura (PDF/XML)",
                icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                height=28,
                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8)),
                on_click=lambda _: self.trigger_file_picker(
                    lambda path, name: self._attach_document_to_invoice(
                        invoice_id, path, detail_dialog
                    )
                ),
            )
        )

        detail_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Text(f"Factura #{inv['number']}", weight=ft.FontWeight.BOLD),
                    StatusChip(inv["status"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.Row([
                            ft.Text(f"Tipo: {type_str}"),
                            ft.Text(f"Contraparte: {inv['client_name'] or 'N/A'}", weight=ft.FontWeight.W_500),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text(f"Monto Total: ${inv['total_amount']:,.0f}"),
                            ft.Text(f"Total Pagado: ${inv['total_paid']:,.0f}", color=BALANCE_POSITIVE_COLOR),
                            ft.Text(f"Saldo: ${inv['balance']:,.0f}", weight=ft.FontWeight.BOLD, color=bal_color),
                        ], spacing=16),
                        ft.Row([
                            ft.Text(f"Categoría: {inv['category'] or 'General'}", size=12),
                            doc_control
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=1),
                        ft.Text("Historial de Pagos y Evidencias", weight=ft.FontWeight.BOLD, size=13),
                        payments_table,
                        *(
                            [
                                ft.Divider(height=1),
                                ft.Row([
                                    ft.Icon(ft.Icons.ASSIGNMENT_RETURN_ROUNDED, size=16, color=ft.Colors.PURPLE_700),
                                    ft.Text(
                                        "Notas de Crédito Emitidas para esta Factura",
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=ft.Colors.PURPLE_900
                                    ),
                                ], spacing=6),
                                cn_table
                            ] if cn_rows else []
                        )
                    ],
                    spacing=12,
                ),
                width=680,
                height=450,
            ),
            actions=[
                ft.FilledButton(
                    "Registrar Pago",
                    icon=ft.Icons.PAYMENTS_ROUNDED,
                    bgcolor=BTN_SUCCESS_BG,
                    visible=(
                        inv["balance"] > 0
                        and inv["type"] != InvoiceType.CREDIT_NOTE
                        and inv["status"] != PaymentStatus.ANNULLED
                    ),
                    on_click=lambda _: (
                        close_dialog(self.page_ref, detail_dialog),
                        self.open_payment_modal(invoice_id),
                    ),
                ),
                ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, detail_dialog))
            ]
        )
        open_dialog(self.page_ref, detail_dialog)

    def open_credit_note_modal(self, invoice_id: int):
        inv = self.finance_service.get_invoice(invoice_id)
        if not inv:
            return

        is_annulment_options = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="TOTAL", label="Anulación Total (Factura queda sin efecto/saldo $0)"),
                ft.Radio(value="PARTIAL", label="Ajuste / Descuento Parcial"),
            ], spacing=16),
            value="TOTAL"
        )

        nc_number_field = ft.TextField(
            label="N° Folio Nota de Crédito SII *",
            hint_text="Ej: NC-105 o Folio SII",
            expand=True
        )

        amount_field = ft.TextField(
            label="Monto de la Nota de Crédito ($) *",
            value=str(int(inv["total_amount"])),
            width=220
        )

        def on_type_choice_change(e):
            if is_annulment_options.value == "TOTAL":
                amount_field.value = str(int(inv["total_amount"]))
                amount_field.read_only = True
            else:
                amount_field.read_only = False
            if self.page_ref:
                self.page_ref.update()

        is_annulment_options.on_change = on_type_choice_change
        amount_field.read_only = True

        reason_dropdown = ft.Dropdown(
            label="Motivo de Emisión SII *",
            options=[
                ft.dropdown.Option(
                    key="1. Anula Documento de Referencia",
                    text="1. Anula Documento de Referencia"
                ),
                ft.dropdown.Option(
                    key="2. Corrige Texto Documento de Referencia",
                    text="2. Corrige Texto Referencia"
                ),
                ft.dropdown.Option(
                    key="3. Corrige Montos / Descuento",
                    text="3. Corrige Montos / Descuento"
                ),
                ft.dropdown.Option(
                    key="Devolución de mercaderías / servicios no prestados",
                    text="Devolución de mercaderías / servicios"
                ),
                ft.dropdown.Option(
                    key="Error de facturación previo a cobro",
                    text="Error de facturación previo a cobro"
                ),
                ft.dropdown.Option(
                    key="Otro motivo justificado",
                    text="Otro motivo justificado"
                ),
            ],
            value="1. Anula Documento de Referencia",
            expand=True,
        )

        notes_field = ft.TextField(
            label="Detalle / Observaciones de la Nota de Crédito",
            multiline=True,
            min_lines=2,
            hint_text="Explica detalladamente la causa de emisión de la NC para auditoría..."
        )

        attached_nc_path = [None]
        nc_file_status = ft.Text("Sin archivo adjunto", size=12, color=TEXT_MUTED)

        def on_nc_file_picked(path, name):
            attached_nc_path[0] = path
            nc_file_status.value = f"PDF Listo: {name}"
            nc_file_status.color = METRIC_SUCCESS_COLOR
            if self.page_ref:
                self.page_ref.update()

        attach_btn = ft.OutlinedButton(
            "Adjuntar PDF Nota de Crédito SII",
            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_nc_file_picked)
        )

        dialog: Optional[ft.AlertDialog] = None

        def save_credit_note(e: ft.ControlEvent) -> None:
            if not nc_number_field.value.strip():
                show_snackbar(self.page_ref, "Debes ingresar el N° de Nota de Crédito.", is_error=True)
                return

            try:
                amt = float(amount_field.value)
                if amt <= 0:
                    show_snackbar(self.page_ref, "El monto debe ser mayor a 0.", is_error=True)
                    return
            except ValueError:
                show_snackbar(self.page_ref, "Monto numérico inválido.", is_error=True)
                return

            is_total = (is_annulment_options.value == "TOTAL")
            final_reason = f"{reason_dropdown.value}"
            if notes_field.value.strip():
                final_reason += f" - {notes_field.value.strip()}"

            final_doc_path = None
            if attached_nc_path[0]:
                final_doc_path = save_document(
                    attached_nc_path[0],
                    "invoices/credit_notes",
                    prefix=f"NC_{nc_number_field.value.strip()}"
                )

            self.finance_service.create_credit_note(
                reference_invoice_id=invoice_id,
                number=nc_number_field.value.strip(),
                amount=amt,
                reason=final_reason,
                is_total_annulment=is_total,
                document_path=final_doc_path
            )

            msg = (
                f"Nota de Crédito #{nc_number_field.value.strip()} emitida con éxito. "
                f"Factura #{inv['number']} actualizada."
            )
            show_snackbar(self.page_ref, msg)
            if dialog:
                close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.ASSIGNMENT_RETURN_ROUNDED, color=ft.Colors.PURPLE_700),
                ft.Text(f"Emitir Nota de Crédito SII (Factura #{inv['number']})", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        # SII Educational Notice
                        ft.Container(
                            content=ft.Column([
                                ft.Text(
                                    "Normativa Tributaria SII (Chile)",
                                    weight=ft.FontWeight.BOLD,
                                    size=12,
                                    color=ft.Colors.PURPLE_900
                                ),
                                ft.Text(
                                    "En el SII las facturas emitidas no se pueden eliminar. La anulación formal "
                                    "o ajuste de montos se realiza mediante una Nota de Crédito electrónica, "
                                    "garantizando la validez contable y tributaria.",
                                    size=11,
                                    color=ft.Colors.PURPLE_800
                                ),
                            ], spacing=2),
                            bgcolor=ft.Colors.PURPLE_50,
                            border=ft.Border.all(1, ft.Colors.PURPLE_200),
                            border_radius=6,
                            padding=8,
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Text(f"Factura Original: #{inv['number']}", weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(f"Total: ${inv['total_amount']:,.0f}", size=12),
                                ft.Text(
                                    f"Saldo Actual: ${inv['balance']:,.0f}",
                                    weight=ft.FontWeight.BOLD,
                                    size=12,
                                    color=BALANCE_NEGATIVE_COLOR if inv['balance'] > 0 else TEXT_PRIMARY
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            bgcolor=CARD_ALT_BGCOLOR,
                            border_radius=6,
                            padding=8,
                        ),
                        is_annulment_options,
                        ft.Row([nc_number_field, amount_field]),
                        reason_dropdown,
                        ft.Row([attach_btn, nc_file_status], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=660,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Emitir Nota de Crédito SII", on_click=save_credit_note, bgcolor=ft.Colors.PURPLE_700),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def confirm_delete_invoice_modal(self, invoice_id: int, invoice_number: str):
        inv = self.finance_service.get_invoice(invoice_id)
        is_nc = inv["type"] == InvoiceType.CREDIT_NOTE if inv else False

        reason_field = ft.TextField(
            label="Motivo obligatorio de la eliminación (quedará en auditoría) *",
            multiline=True,
            min_lines=2,
            hint_text="Ej: Registro duplicado por error de tipeo previo a la emisión en el SII..."
        )

        dialog: Optional[ft.AlertDialog] = None

        def do_delete(e: ft.ControlEvent) -> None:
            reason = reason_field.value.strip()
            if len(reason) < 4:
                show_snackbar(self.page_ref, "Debes ingresar un motivo detallado para la eliminación.", is_error=True)
                return

            self.finance_service.delete_invoice(invoice_id, reason=reason)
            msg = f"Factura #{invoice_number} eliminada del sistema. Motivo registrado en auditoría."
            show_snackbar(self.page_ref, msg)
            if dialog:
                close_dialog(self.page_ref, dialog)
            self.load_data()

        def switch_to_credit_note(e: ft.ControlEvent) -> None:
            if dialog:
                close_dialog(self.page_ref, dialog)
            self.open_credit_note_modal(invoice_id)

        actions: List[ft.Control] = [
            ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
        ]

        if not is_nc:
            actions.append(
                ft.OutlinedButton(
                    "Emitir Nota de Crédito en su lugar",
                    icon=ft.Icons.ASSIGNMENT_RETURN_ROUNDED,
                    on_click=switch_to_credit_note
                )
            )

        actions.append(
            ft.FilledButton("Eliminar Factura Definitivamente", on_click=do_delete, bgcolor=ft.Colors.RED_700)
        )

        warning_text = (
            "Las facturas ya emitidas electrónicamente en el SII NO deben eliminarse. "
            "La anulación formal se hace mediante una Nota de Crédito. Use la eliminación únicamente "
            "para pruebas, borradores o errores de registro previo a la emisión fiscal."
        )

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_600),
                ft.Text(f"Eliminar Factura #{invoice_number}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Column([
                                ft.Text(
                                    "⚠️ ADVERTENCIA TRIBUTARIA SII",
                                    weight=ft.FontWeight.BOLD,
                                    size=12,
                                    color=ft.Colors.RED_900
                                ),
                                ft.Text(warning_text, size=11, color=ft.Colors.RED_800),
                            ], spacing=2),
                            bgcolor=ft.Colors.RED_50,
                            border=ft.Border.all(1, ft.Colors.RED_200),
                            border_radius=6,
                            padding=8,
                        ),
                        ft.Text(
                            "Para continuar, es requisito registrar el motivo en la bitácora de auditoría:",
                            size=12
                        ),
                        reason_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=560,
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def confirm_unlink_from_finances(self, invoice_id: int, invoice_number: str, project_name: str) -> None:
        dialog: Optional[ft.AlertDialog] = None

        def do_unlink(e: ft.ControlEvent) -> None:
            success = self.finance_service.unlink_invoice_from_project(invoice_id)
            if success:
                show_snackbar(
                    self.page_ref,
                    f"Factura #{invoice_number} desvinculada del proyecto '{project_name}'."
                )
            else:
                show_snackbar(self.page_ref, "No se pudo desvincular la factura.", is_error=True)
            if dialog:
                close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LINK_OFF_ROUNDED, color=ft.Colors.ORANGE_800),
                ft.Text(f"Desvincular Factura #{invoice_number}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"¿Deseas desvincular esta factura del proyecto '{project_name}'?"),
                        ft.Text(
                            "• La factura se mantendrá intacta en esta sección de Finanzas.",
                            size=12,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            "• El proyecto dejará de tenerla asociada a sus costos/ventas.",
                            size=12,
                            color=TEXT_MUTED
                        ),
                    ],
                    spacing=6,
                    tight=True,
                ),
                width=480,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Sí, Desvincular", on_click=do_unlink, bgcolor=ft.Colors.ORANGE_800),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    # =========================================================================
    # 2. SECCIÓN ÓRDENES DE COMPRA (PURCHASE ORDERS)
    # =========================================================================
    def load_purchase_orders(self) -> None:
        status_val = self.po_status_filter.value
        status = None if status_val == "ALL" else status_val

        client_val = self.po_client_filter.value
        client_id = None if client_val == "ALL" else int(client_val)

        orders = self.po_service.list_orders(client_id=client_id, status=status)

        # Compute Executive KPI Metrics for Purchase Orders
        all_pos = self.po_service.list_orders()
        tot_po_amount = sum(po["amount"] for po in all_pos)
        accepted_pos = [p for p in all_pos if p["status"] == "ACCEPTED"]
        accepted_amount = sum(p["amount"] for p in accepted_pos)
        pending_pos = [p for p in all_pos if p["status"] == "PENDING"]
        pending_amount = sum(p["amount"] for p in pending_pos)
        po_docs = sum(1 for p in all_pos if p["has_document"])

        self.kpis_container.content = ft.Row(
            controls=[
                StatCard(
                    "Total en OCs",
                    format_currency(tot_po_amount),
                    f"{len(all_pos)} órdenes registradas",
                    ft.Icons.DESCRIPTION_ROUNDED,
                    METRIC_PROJECT_COLOR
                ),
                StatCard(
                    "OCs Aceptadas",
                    format_currency(accepted_amount),
                    f"{len(accepted_pos)} listas para operar",
                    ft.Icons.CHECK_CIRCLE_ROUNDED,
                    METRIC_SUCCESS_COLOR
                ),
                StatCard(
                    "OCs Pendientes",
                    format_currency(pending_amount),
                    f"{len(pending_pos)} por confirmar",
                    ft.Icons.PENDING_ACTIONS_ROUNDED,
                    METRIC_ALERT_COLOR
                ),
                StatCard(
                    "Respaldos Adjuntos",
                    f"{po_docs} / {len(all_pos)}",
                    "OCs con archivo PDF original",
                    ft.Icons.ATTACH_FILE_ROUNDED,
                    INVOICE_ISSUED_BG
                ),
            ],
            spacing=12,
        )

        rows = []
        for po in orders:
            # Document icon or opener
            if po["has_document"]:
                doc_btn = ft.IconButton(
                    icon=ft.Icons.ATTACH_FILE_ROUNDED,
                    icon_color=METRIC_SUCCESS_COLOR,
                    tooltip="Clic para abrir PDF de la OC",
                    icon_size=18,
                    on_click=lambda _, p=po["document_path"]: self.open_file_safe(p)
                )
            else:
                doc_btn = ft.Icon(
                    ft.Icons.FILE_PRESENT_OUTLINED,
                    size=16,
                    color=METRIC_ALERT_COLOR,
                    tooltip="Sin documento original adjunto"
                )

            actions = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                        tooltip="Iniciar Proyecto desde esta OC",
                        icon_size=18,
                        icon_color=BTN_ACCENT_BG,
                        visible=(not po["has_project"] and po["status"] == "ACCEPTED"),
                        on_click=lambda _, pid=po["id"]: self.convert_po_to_project(pid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        tooltip="Modificar Orden de Compra",
                        icon_size=18,
                        on_click=lambda _, pid=po["id"]: self.open_edit_po_modal(pid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        tooltip="Eliminar OC",
                        icon_size=18,
                        icon_color=BTN_DANGER_ICON,
                        on_click=lambda _, pid=po["id"]: self.delete_purchase_order(pid)
                    )
                ],
                spacing=0
            )

            po_quote_str = f"Cotiz: {po['quote_number']}" if po["quote_number"] != "-" else "-"

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(po["number"], weight=ft.FontWeight.BOLD, size=13)),
                        ft.DataCell(ft.Text(po["client_name"])),
                        ft.DataCell(ft.Text(po_quote_str, size=12)),
                        ft.DataCell(ft.Text(po["issue_date"])),
                        ft.DataCell(ft.Text(format_currency(po["amount"]), weight=ft.FontWeight.BOLD)),
                        ft.DataCell(StatusChip(po["status"])),
                        ft.DataCell(doc_btn),
                        ft.DataCell(ft.Text(po["project_name"], size=12, color=TEXT_MUTED)),
                        ft.DataCell(actions),
                    ]
                )
            )

        if not rows:
            self.table_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=48, color=TEXT_HINT),
                        ft.Text("No hay órdenes de compra registradas", color=TEXT_MUTED, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=40,
                alignment=ft.Alignment(0, 0),
                bgcolor=TABLE_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
            )
        else:
            self.table_container.content = ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("N° OC", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Cotización", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Doc", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Proyecto Asociado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12)),
                            ],
                            rows=rows,
                            heading_row_height=42,
                            data_row_min_height=48,
                            column_spacing=16,
                        )
                    ],
                    expand=True,
                ),
                bgcolor=TABLE_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
                expand=True,
            )

        if self.page_ref:
            self.page_ref.update()

    def open_create_po_modal(self, default_quote_id: Optional[int] = None) -> None:
        clients = self.client_service.list_clients(active_only=True)
        if not clients:
            show_snackbar(self.page_ref, "Debe tener al menos un cliente registrado.", is_error=True)
            return

        client_dropdown = ft.Dropdown(
            label="Cliente *",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients],
            value=str(clients[0]["id"]),
            expand=True,
        )

        quotes = self.quote_service.list_quotes(client_id=int(client_dropdown.value))
        quote_dropdown = ft.Dropdown(
            label="Cotización vinculada (opcional)",
            options=[ft.dropdown.Option(key="NONE", text="Sin cotización")] + [
                ft.dropdown.Option(key=str(q["id"]), text=f"{q['number']} - ${q['total_amount']:,.0f}")
                for q in quotes
            ],
            value="NONE",
            expand=True,
        )

        def on_client_change(e: ft.ControlEvent) -> None:
            cid = int(client_dropdown.value)
            c_quotes = self.quote_service.list_quotes(client_id=cid)
            quote_dropdown.options = [ft.dropdown.Option(key="NONE", text="Sin cotización")] + [
                ft.dropdown.Option(key=str(q["id"]), text=f"{q['number']} - ${q['total_amount']:,.0f}")
                for q in c_quotes
            ]
            quote_dropdown.value = "NONE"
            if self.page_ref:
                self.page_ref.update()

        client_dropdown.on_select = on_client_change

        number_field = ft.TextField(label="N° Orden de Compra * (ej: OC-2026-081)", expand=True)
        amount_field = ft.TextField(label="Monto ($) *", value="1000000", width=200)

        status_dropdown = ft.Dropdown(
            label="Estado Inicial",
            options=[
                ft.dropdown.Option(key="ACCEPTED", text="Aceptada"),
                ft.dropdown.Option(key="PENDING", text="Pendiente"),
            ],
            value="ACCEPTED",
            width=180,
        )

        attached_doc_path = [None]
        doc_status_text = ft.Text("Ningún archivo adjunto", size=12, color=TEXT_MUTED)

        def on_po_file_picked(path: str, name: str) -> None:
            attached_doc_path[0] = path
            doc_status_text.value = f"Archivo adjunto: {name}"
            doc_status_text.color = METRIC_SUCCESS_COLOR
            if self.page_ref:
                self.page_ref.update()

        attach_btn = ft.OutlinedButton(
            "Adjuntar OC (PDF / Imagen)",
            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_po_file_picked)
        )

        notes_field = ft.TextField(label="Notas / Términos de la OC", multiline=True, min_lines=2, expand=True)
        dialog = None

        def save_po(e: ft.ControlEvent) -> None:
            if not number_field.value.strip():
                show_snackbar(self.page_ref, "El número de OC es obligatorio.", is_error=True)
                return

            try:
                amt = float(amount_field.value)
            except ValueError:
                show_snackbar(self.page_ref, "Monto inválido.", is_error=True)
                return

            qid = int(quote_dropdown.value) if (quote_dropdown.value and quote_dropdown.value != "NONE") else None

            final_doc_path = None
            if attached_doc_path[0]:
                po_num = number_field.value.strip()
                final_doc_path = save_document(
                    attached_doc_path[0], "purchase_orders", prefix=f"OC_{po_num}"
                )

            self.po_service.create_order(
                client_id=int(client_dropdown.value),
                quote_id=qid,
                number=number_field.value.strip(),
                amount=amt,
                status=status_dropdown.value,
                document_path=final_doc_path,
                notes=notes_field.value.strip()
            )

            show_snackbar(self.page_ref, f"Orden de Compra #{number_field.value} registrada.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text("Registrar Orden de Compra", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([client_dropdown, quote_dropdown]),
                        ft.Row([number_field, amount_field, status_dropdown]),
                        ft.Row([attach_btn, doc_status_text], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=680,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Orden de Compra", on_click=save_po, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_edit_po_modal(self, po_id: int) -> None:
        po = self.po_service.get_order(po_id)
        if not po:
            return

        clients = self.client_service.list_clients()
        client_dropdown = ft.Dropdown(
            label="Cliente *",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients],
            value=str(po["client_id"]),
            expand=True,
        )

        number_field = ft.TextField(label="N° Orden de Compra", value=po["number"], expand=True)
        amount_field = ft.TextField(label="Monto ($)", value=str(int(po["amount"])), width=180)

        status_dropdown = ft.Dropdown(
            label="Estado",
            options=[
                ft.dropdown.Option(key="ACCEPTED", text="Aceptada"),
                ft.dropdown.Option(key="PENDING", text="Pendiente"),
                ft.dropdown.Option(key="REJECTED", text="Rechazada"),
                ft.dropdown.Option(key="CANCELLED", text="Cancelada"),
            ],
            value=po["status"],
            width=180,
        )

        attached_doc_path = [po["document_path"]]
        current_name = os.path.basename(po["document_path"]) if po.get("document_path") else None
        doc_status_text = ft.Text(
            f"Archivo actual: {current_name}" if current_name else "Sin documento adjunto",
            size=12,
            color=METRIC_SUCCESS_COLOR if current_name else TEXT_MUTED
        )

        def on_po_file_picked(path: str, name: str) -> None:
            attached_doc_path[0] = path
            doc_status_text.value = f"Nuevo archivo listo: {name}"
            doc_status_text.color = METRIC_SUCCESS_COLOR
            if self.page_ref:
                self.page_ref.update()

        attach_btn = ft.OutlinedButton(
            "Cambiar / Adjuntar OC",
            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
            on_click=lambda _: self.trigger_file_picker(on_po_file_picked)
        )

        notes_field = ft.TextField(label="Notas", value=po["notes"], multiline=True, min_lines=2)
        dialog = None

        def update_po(e: ft.ControlEvent) -> None:
            try:
                amt = float(amount_field.value)
            except ValueError:
                show_snackbar(self.page_ref, "Monto inválido.", is_error=True)
                return

            final_doc_path = attached_doc_path[0]
            if attached_doc_path[0] and attached_doc_path[0] != po["document_path"]:
                po_num = number_field.value.strip()
                final_doc_path = save_document(
                    attached_doc_path[0], "purchase_orders", prefix=f"OC_{po_num}"
                )

            self.po_service.update_order(
                po_id=po_id,
                client_id=int(client_dropdown.value),
                number=number_field.value.strip(),
                amount=amt,
                status=status_dropdown.value,
                document_path=final_doc_path,
                notes=notes_field.value.strip()
            )

            show_snackbar(self.page_ref, f"Orden de Compra #{number_field.value} actualizada.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Modificar Orden de Compra #{po['number']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        client_dropdown,
                        ft.Row([number_field, amount_field, status_dropdown]),
                        ft.Row([attach_btn, doc_status_text], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=650,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Cambios", on_click=update_po, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def convert_po_to_project(self, po_id: int) -> None:
        proj = self.po_service.convert_to_project(po_id)
        if proj:
            show_snackbar(self.page_ref, f"¡Proyecto '{proj['name']}' iniciado exitosamente!")
            self.load_data()

    def delete_purchase_order(self, po_id: int) -> None:
        self.po_service.delete_order(po_id)
        show_snackbar(self.page_ref, "Orden de Compra eliminada.")
        self.load_data()
