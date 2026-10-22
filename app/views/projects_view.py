import logging
import os
from typing import Optional, Callable
import flet as ft
from app.services.project_service import ProjectService
from app.services.client_service import ClientService
from app.services.company_service import CompanyService
from app.services.finance_service import FinanceService, save_document, open_document, DEFAULT_EXPENSE_CATEGORIES
from app.services.sii_invoice_parser import parse_sii_document
from app.services.ai_service import AIService
from app.services.currency_service import format_currency
from app.models.project import ProjectStatus
from app.models.invoice import InvoiceType
from app.components.cards import SectionHeader, StatusChip, open_dialog, close_dialog, show_snackbar
from app.constant import (
    TABLE_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    TEXT_HINT,
    TEXT_LIGHT,
    BTN_PRIMARY_BG,
    INVOICE_ISSUED_BG,
    INVOICE_RECEIVED_BG,
    INVOICE_CREDIT_NOTE_BG,
    METRIC_PROJECT_COLOR,
    METRIC_SUCCESS_COLOR,
    BALANCE_NEGATIVE_COLOR,
)

logger = logging.getLogger(__name__)


class ProjectsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.project_service = ProjectService()
        self.client_service = ClientService()
        self.finance_service = FinanceService()
        self.company_service = CompanyService()
        self.ai_service = AIService()

        # FilePicker for uploading project invoice attachments
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.active_file_target = None

        self.status_filter = ft.Dropdown(
            label="Filtrar por Estado",
            options=[ft.dropdown.Option(key="ALL", text="Todos los Estados")] + [
                ft.dropdown.Option(key=s, text=s) for s in ProjectStatus.ALL
            ],
            value="ALL",
            width=200,
            dense=True,
            on_select=lambda _: self.load_data()
        )
        self.table_container = ft.Container(expand=True)
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

    def trigger_file_picker(self, target_callback) -> None:
        # DECISIÓN TÉCNICA: En Flet 1.0+, FilePicker hereda de Service y debe residir en page.services,
        # NUNCA en page.overlay (que generaría TimeoutException en el cliente Flutter al invocar pick_files).
        self.active_file_target = target_callback
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
                logger.error("Error al invocar FilePicker en Proyectos: %s", ex)
                if self.page_ref:
                    show_snackbar(self.page_ref, f"Error al abrir selector de archivos: {ex}", is_error=True)

        if self.page_ref:
            self.page_ref.run_task(_pick)

    def open_file_safe(self, path: str):
        if not path or not os.path.exists(path):
            show_snackbar(self.page_ref, "El archivo adjunto no existe o no se encuentra disponible.", is_error=True)
            return
        success = open_document(path)
        if not success:
            show_snackbar(self.page_ref, f"No se pudo abrir el archivo en: {path}", is_error=True)

    def build_ui(self):
        # DECISIÓN TÉCNICA: Registrar FilePicker como Service de la página
        if self.page_ref and hasattr(self.page_ref, "services") and self.file_picker not in self.page_ref.services:
            self.page_ref.services.append(self.file_picker)
        header = SectionHeader(
            title="Proyectos",
            subtitle="Seguimiento de proyectos en ejecución, avances porcentuales y bitácora de eventos",
            action_button=ft.FilledButton(
                "Nuevo Proyecto",
                icon=ft.Icons.ADD_TASK_ROUNDED,
                on_click=lambda _: self.open_create_project_modal(),
                bgcolor=BTN_PRIMARY_BG,
            )
        )

        filter_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self.status_filter,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="Recargar",
                        on_click=lambda _: self.load_data()
                    )
                ],
                spacing=12,
            ),
            padding=ft.Padding.symmetric(vertical=4),
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=8),
                filter_bar,
                ft.Container(height=8),
                self.table_container,
            ],
            spacing=0,
            expand=True,
        )

        self.load_data()

    def load_data(self):
        status_val = self.status_filter.value
        status = None if status_val == "ALL" else status_val
        projects = self.project_service.list_projects(status=status)

        rows = []
        for p in projects:
            progress_bar = ft.Row(
                controls=[
                    ft.ProgressBar(value=p["progress"] / 100, width=80, color=METRIC_PROJECT_COLOR),
                    ft.Text(f"{p['progress']}%", size=11, color=TEXT_SECONDARY, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            actions = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        tooltip="Actualizar Avance / Estado",
                        icon_size=18,
                        on_click=lambda _, pid=p["id"]: self.open_update_progress_modal(pid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.HISTORY_ROUNDED,
                        tooltip="Bitácora de Eventos",
                        icon_size=18,
                        on_click=lambda _, pid=p["id"]: self.open_project_detail_modal(pid)
                    )
                ],
                spacing=0,
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(p["name"], weight=ft.FontWeight.BOLD, size=13),
                                    (
                                        ft.Text(f"Cotiz: {p['quote_number']}", size=11, color=TEXT_HINT)
                                        if p["quote_number"] != "-" else ft.Container()
                                    ),
                                ],
                                spacing=0,
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ),
                        ft.DataCell(ft.Text(p["client_name"])),
                        ft.DataCell(ft.Text(p["start_date"])),
                        ft.DataCell(progress_bar),
                        ft.DataCell(StatusChip(p["status"])),
                        ft.DataCell(actions),
                    ]
                )
            )

        if not rows:
            self.table_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OFF_ROUNDED, size=48, color=TEXT_HINT),
                        ft.Text("No hay proyectos registrados", color=TEXT_MUTED, size=14),
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
                                ft.DataColumn(ft.Text("Proyecto", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Inicio", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Progreso", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12)),
                            ],
                            rows=rows,
                            heading_row_height=42,
                            data_row_min_height=48,
                            column_spacing=20,
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

    def open_create_project_modal(self):
        clients = self.client_service.list_clients(active_only=True)
        if not clients:
            show_snackbar(self.page_ref, "Debe tener al menos un cliente para asociar al proyecto.", is_error=True)
            return

        client_dropdown = ft.Dropdown(
            label="Cliente *",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients],
            value=str(clients[0]["id"]),
            expand=True,
        )
        name_field = ft.TextField(label="Nombre del Proyecto *", expand=True)
        description_field = ft.TextField(label="Descripción / Alcance", multiline=True, min_lines=2, expand=True)
        status_dropdown = ft.Dropdown(
            label="Estado Inicial",
            options=[ft.dropdown.Option(key=s, text=s) for s in ProjectStatus.ALL],
            value=ProjectStatus.ACTIVE,
            width=200,
        )
        dialog = None

        def save_project(e):
            if not name_field.value.strip():
                show_snackbar(self.page_ref, "El nombre del proyecto es obligatorio.", is_error=True)
                return

            self.project_service.create_project(
                client_id=int(client_dropdown.value),
                name=name_field.value.strip(),
                description=description_field.value.strip(),
                status=status_dropdown.value,
                progress=0
            )
            show_snackbar(self.page_ref, "Proyecto creado con éxito.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text("Nuevo Proyecto", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        client_dropdown,
                        name_field,
                        status_dropdown,
                        description_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=600,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Proyecto", on_click=save_project, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_update_progress_modal(self, project_id: int):
        project = self.project_service.get_project(project_id)
        if not project:
            return

        progress_slider = ft.Slider(min=0, max=100, divisions=20, value=project["progress"], label="{value}%")
        progress_label = ft.Text(f"{project['progress']}%", weight=ft.FontWeight.BOLD)

        def on_slider_change(e):
            progress_label.value = f"{int(e.control.value)}%"
            if self.page_ref:
                self.page_ref.update()

        progress_slider.on_change = on_slider_change

        status_dropdown = ft.Dropdown(
            label="Estado",
            options=[ft.dropdown.Option(key=s, text=s) for s in ProjectStatus.ALL],
            value=project["status"],
            width=220,
        )
        notes_field = ft.TextField(label="Hito o nota del avance (opcional)", multiline=True, min_lines=2)

        dialog = None

        def save_update(e):
            new_prog = int(progress_slider.value)
            new_stat = status_dropdown.value
            note = notes_field.value.strip() or None

            self.project_service.update_project(project_id, status=new_stat)
            self.project_service.update_progress(project_id, new_prog, notes=note)

            show_snackbar(self.page_ref, "Avance y estado del proyecto actualizados.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Actualizar Progreso: {project['name']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([ft.Text("Porcentaje de avance:"), progress_label]),
                        progress_slider,
                        status_dropdown,
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=550,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Avance", on_click=save_update, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_project_detail_modal(self, project_id: int):
        project = self.project_service.get_project(project_id)
        if not project:
            return

        detail_dialog = None

        def refresh_modal():
            close_dialog(self.page_ref, detail_dialog)
            self.load_data()
            self.open_project_detail_modal(project_id)

        # Timeline Items
        events = project["events"]
        timeline_items = []
        for ev in events:
            timeline_items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=14, color=METRIC_PROJECT_COLOR),
                            ft.Column(
                                controls=[
                                    ft.Row([
                                        ft.Text(
                                            ev["event_type"],
                                            weight=ft.FontWeight.BOLD,
                                            size=11,
                                            color=TEXT_SECONDARY
                                        ),
                                        ft.Text(ev["date"], size=10, color=TEXT_HINT),
                                    ], spacing=8),
                                    ft.Text(ev["description"], size=12, color=TEXT_PRIMARY),
                                ],
                                spacing=2,
                                expand=True,
                            )
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )

        # Invoices Table Rows
        invoices = project.get("invoices", [])
        invoice_rows = []
        for inv in invoices:
            is_issued = inv["type"] == InvoiceType.ISSUED
            is_nc = inv["type"] == InvoiceType.CREDIT_NOTE

            if is_nc:
                badge_bg = INVOICE_CREDIT_NOTE_BG
                badge_text = "Nota Crédito"
            elif is_issued:
                badge_bg = INVOICE_ISSUED_BG
                badge_text = "Emitida (Venta)"
            else:
                badge_bg = INVOICE_RECEIVED_BG
                badge_text = "Recibida (Gasto)"

            type_badge = ft.Container(
                content=ft.Text(badge_text, size=9, weight=ft.FontWeight.BOLD, color=TEXT_LIGHT),
                bgcolor=badge_bg,
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=5, vertical=2),
            )

            # Document preview button
            if inv["has_document"]:
                doc_ctrl = ft.IconButton(
                    icon=ft.Icons.ATTACH_FILE_ROUNDED,
                    icon_color=METRIC_SUCCESS_COLOR,
                    icon_size=16,
                    tooltip="Abrir documento adjunto",
                    on_click=lambda _, p=inv["document_path"]: self.open_file_safe(p)
                )
            else:
                doc_ctrl = ft.Text("-", size=11, color=TEXT_MUTED)

            # Unlink button
            unlink_btn = ft.IconButton(
                icon=ft.Icons.LINK_OFF_ROUNDED,
                tooltip="Desvincular del proyecto (se mantiene en Finanzas)",
                icon_size=17,
                icon_color=ft.Colors.ORANGE_800,
                on_click=lambda _, iid=inv["id"], num=inv["number"]: self.confirm_unlink_invoice_modal(
                    iid, num, project_id, refresh_modal
                )
            )

            invoice_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(type_badge),
                        ft.DataCell(ft.Text(inv["number"], weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataCell(
                            ft.Text(
                                inv.get("issuer_name") or inv.get("client_name") or "-",
                                size=11,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS
                            )
                        ),
                        ft.DataCell(ft.Text(format_currency(inv["total_amount"]), size=12)),
                        ft.DataCell(
                            ft.Text(
                                format_currency(inv["balance"]),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=BALANCE_NEGATIVE_COLOR if inv["balance"] > 0 else TEXT_PRIMARY
                            )
                        ),
                        ft.DataCell(StatusChip(inv["status"])),
                        ft.DataCell(doc_ctrl),
                        ft.DataCell(unlink_btn),
                    ]
                )
            )

        if invoice_rows:
            invoices_table = ft.Container(
                content=ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Tipo", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("N°", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Proveedor / Contraparte", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Saldo", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Doc", weight=ft.FontWeight.BOLD, size=11)),
                        ft.DataColumn(ft.Text("Desvincular", weight=ft.FontWeight.BOLD, size=11)),
                    ],
                    rows=invoice_rows,
                    heading_row_height=34,
                    data_row_min_height=38,
                    column_spacing=12,
                ),
                border=ft.Border.all(1, BORDER_COLOR),
                border_radius=6,
                padding=4,
            )
        else:
            invoices_table = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=24, color=TEXT_HINT),
                        ft.Text("No hay facturas vinculadas a este proyecto aún.", size=12, color=TEXT_MUTED),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=16,
                alignment=ft.Alignment(0, 0),
                bgcolor=TABLE_BGCOLOR,
                border_radius=6,
                border=ft.Border.all(1, BORDER_COLOR),
            )

        detail_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Text(project["name"], weight=ft.FontWeight.BOLD),
                    StatusChip(project["status"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                content=ft.ListView(
                    controls=[
                        # Project summary
                        ft.Row([
                            ft.Text(f"Cliente: {project['client_name']}", size=13, weight=ft.FontWeight.W_500),
                            ft.Text(f"Cotización: {project['quote_number']}", size=12, color=TEXT_MUTED),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"Descripción: {project['description'] or 'Sin descripción'}", size=12),
                        ft.Row([
                            ft.Text(f"Progreso actual: {project['progress']}%", weight=ft.FontWeight.BOLD),
                            ft.ProgressBar(value=project["progress"] / 100, width=150, color=METRIC_PROJECT_COLOR),
                        ], spacing=12),
                        ft.Divider(height=1),

                        # Invoices Section
                        ft.Row(
                            controls=[
                                ft.Row([
                                    ft.Icon(ft.Icons.RECEIPT_ROUNDED, size=18, color=METRIC_PROJECT_COLOR),
                                    ft.Text("Facturas y Costos del Proyecto", weight=ft.FontWeight.BOLD, size=13),
                                ], spacing=6),
                                ft.FilledButton(
                                    "Subir Factura al Proyecto",
                                    icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                                    height=32,
                                    bgcolor=BTN_PRIMARY_BG,
                                    on_click=lambda _: self.open_upload_project_invoice_modal(project, refresh_modal)
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        invoices_table,
                        ft.Divider(height=1),

                        # Timeline / Events Section
                        ft.Row([
                            ft.Icon(ft.Icons.HISTORY_ROUNDED, size=18, color=METRIC_PROJECT_COLOR),
                            ft.Text("Bitácora de Avances y Eventos", weight=ft.FontWeight.BOLD, size=13),
                        ], spacing=6),
                        ft.Container(
                            content=ft.ListView(
                                controls=(
                                    timeline_items if timeline_items
                                    else [ft.Text("Sin avances registrados aún.", size=12, color=TEXT_HINT)]
                                ),
                                height=140,
                            ),
                            border=ft.Border.all(1, BORDER_COLOR),
                            border_radius=6,
                            padding=8,
                        )
                    ],
                    spacing=12,
                ),
                width=740,
                height=520,
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, detail_dialog))
            ]
        )
        open_dialog(self.page_ref, detail_dialog)

    def open_upload_project_invoice_modal(self, project: dict, on_success):
        project_id = project["id"]
        client_id = project["client_id"]

        type_dropdown = ft.Dropdown(
            label="Tipo de Factura *",
            options=[
                ft.dropdown.Option(key=InvoiceType.ISSUED, text="Factura Emitida al Cliente (Venta)"),
                ft.dropdown.Option(key=InvoiceType.RECEIVED, text="Factura Recibida de Proveedor (Gasto)"),
            ],
            value=InvoiceType.RECEIVED,
            expand=True,
        )
        number_field = ft.TextField(label="N° de Factura *", expand=True)

        provider_field = ft.TextField(
            label="Proveedor / Contraparte *",
            expand=True,
            hint_text="Ej: AWS, Ferretería, Subcontratista, etc."
        )
        date_field = ft.TextField(
            label="Fecha Emisión (YYYY-MM-DD)",
            hint_text="YYYY-MM-DD",
            width=200
        )

        net_field = ft.TextField(label="Neto ($) *", value="100000", width=140)
        tax_field = ft.TextField(label="IVA 19% ($)", value="19000", width=140)
        total_field = ft.TextField(label="Total ($) *", value="119000", width=160)

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
            label="Categoría",
            options=[ft.dropdown.Option(key=cat, text=cat) for cat in DEFAULT_EXPENSE_CATEGORIES],
            value=DEFAULT_EXPENSE_CATEGORIES[0],
            expand=True,
        )
        notes_field = ft.TextField(label="Descripción / Notas", multiline=True, min_lines=2)

        attached_file_path = [None]
        file_status_text = ft.Text("Sin archivo adjunto", size=12, color=TEXT_MUTED)
        parsed_doc_data: dict = {}

        def update_provider_from_parsed() -> None:
            if not parsed_doc_data:
                return
            if type_dropdown.value == InvoiceType.RECEIVED:
                provider_field.value = parsed_doc_data.get("emisor_name") or ""
            else:
                provider_field.value = parsed_doc_data.get("receiver_name") or project["client_name"]

        type_dropdown.on_select = lambda _: (update_provider_from_parsed(), self.page_ref.update())

        def on_doc_picked(path, name):
            attached_file_path[0] = path
            file_status_text.value = f"Archivo listo: {name}"
            file_status_text.color = METRIC_SUCCESS_COLOR

            # Auto-parse SII PDF / XML document
            parsed = parse_sii_document(path)

            # DECISIÓN DE ARQUITECTURA: Extracción con IA si el módulo está habilitado para facturas
            if self.ai_service.is_feature_enabled("invoices"):
                file_status_text.value = f"🤖 Analizando con IA ({name})..."
                file_status_text.color = ft.Colors.PURPLE_700
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
                if parsed.get("due_date"):
                    date_field.value = parsed["due_date"]
                elif parsed.get("issue_date"):
                    date_field.value = parsed["issue_date"]

                # DECISIÓN TÉCNICA: Identificación de Proveedor vs Venta comparando con empresa propia
                company = self.company_service.get_company()
                my_rut = (company.get("tax_id") or "").replace(".", "").replace("-", "").upper()
                r_rut = (parsed.get("receiver_tax_id") or "").replace(".", "").replace("-", "").upper()
                e_rut = (parsed.get("emisor_tax_id") or "").replace(".", "").replace("-", "").upper()

                if my_rut and r_rut and my_rut == r_rut:
                    type_dropdown.value = InvoiceType.RECEIVED
                elif my_rut and e_rut and my_rut == e_rut:
                    type_dropdown.value = InvoiceType.ISSUED
                elif parsed.get("emisor_name"):
                    type_dropdown.value = InvoiceType.RECEIVED

                if parsed.get("category") and parsed["category"] in DEFAULT_EXPENSE_CATEGORIES:
                    category_dropdown.value = parsed["category"]

                update_provider_from_parsed()

                sii_num = parsed.get("number", "")
                sii_tot = parsed.get("total_amount", 0)
                prov_label = (
                    parsed.get("emisor_name", "Proveedor")
                    if type_dropdown.value == InvoiceType.RECEIVED
                    else (parsed.get("receiver_name") or project["client_name"])
                )

                if parsed.get("ai_processed"):
                    prov_title = self.ai_service.get_config().get("provider", "IA").capitalize()
                    file_status_text.value = (
                        f"🤖 IA ({prov_title}) #{sii_num} | {prov_label[:20]} | ${sii_tot:,.0f} | {name}"
                    )
                    file_status_text.color = ft.Colors.PURPLE_700
                    show_snackbar(
                        self.page_ref,
                        f"🤖 Factura extraída con IA ({prov_title}): #{sii_num} - Total: ${sii_tot:,.0f}",
                    )
                else:
                    file_status_text.value = f"⚡ SII Folio #{sii_num} | {prov_label[:24]} | ${sii_tot:,.0f} | {name}"
                    show_snackbar(
                        self.page_ref,
                        f"⚡ Factura Folio #{sii_num} leída: '{prov_label[:25]}', Total: ${sii_tot:,.0f}",
                    )

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
            on_doc_picked(attached_file_path[0], os.path.basename(attached_file_path[0]))

        ai_btn = ft.OutlinedButton(
            "Extraer con IA",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            on_click=reanalyze_with_ai,
        )

        upload_dialog: Optional[ft.AlertDialog] = None

        def save_invoice(e: ft.ControlEvent) -> None:
            if not number_field.value.strip():
                show_snackbar(self.page_ref, "El N° de factura es obligatorio.", is_error=True)
                return

            try:
                net = float(net_field.value)
                tax = float(tax_field.value)
                tot = float(total_field.value)
            except ValueError:
                show_snackbar(self.page_ref, "Montos numéricos inválidos.", is_error=True)
                return

            inv_type = type_dropdown.value
            final_doc_path = None
            if attached_file_path[0]:
                subfolder = "invoices/issued" if inv_type == InvoiceType.ISSUED else "invoices/received"
                final_doc_path = save_document(
                    attached_file_path[0], subfolder, prefix=f"FAC_{number_field.value.strip()}"
                )

            default_desc = f"Factura cargada directamente al proyecto '{project['name']}'"
            prov_clean = provider_field.value.strip()
            self.finance_service.create_invoice(
                type=inv_type,
                number=number_field.value.strip(),
                client_id=client_id,
                project_id=project_id,
                issuer_name=(
                    prov_clean or parsed_doc_data.get("emisor_name")
                    if inv_type == InvoiceType.RECEIVED else None
                ),
                issuer_tax_id=parsed_doc_data.get("emisor_tax_id") if inv_type == InvoiceType.RECEIVED else None,
                receiver_name=(
                    prov_clean or parsed_doc_data.get("receiver_name") or project["client_name"]
                    if inv_type == InvoiceType.ISSUED else None
                ),
                receiver_tax_id=parsed_doc_data.get("receiver_tax_id") if inv_type == InvoiceType.ISSUED else None,
                issue_date=parsed_doc_data.get("issue_date") or date_field.value.strip() or None,
                net_amount=net,
                tax_amount=tax,
                total_amount=tot,
                category=category_dropdown.value,
                document_path=final_doc_path,
                notes=notes_field.value.strip() or default_desc
            )

            inv_num_clean = number_field.value.strip()
            show_snackbar(self.page_ref, f"Factura #{inv_num_clean} subida y vinculada al proyecto con éxito.")
            if upload_dialog:
                close_dialog(self.page_ref, upload_dialog)
            if callable(on_success):
                on_success()

        upload_dialog = ft.AlertDialog(
            title=ft.Text(f"Subir Factura al Proyecto: {project['name']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"Cliente asociado: {project['client_name']}", size=12, color=TEXT_SECONDARY),
                        ft.Row([type_dropdown, number_field]),
                        ft.Row([provider_field, date_field]),
                        ft.Row([net_field, tax_field, total_field]),
                        category_dropdown,
                        ft.Row([attach_btn, ai_btn, file_status_text], spacing=12),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=640,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, upload_dialog)),
                ft.FilledButton("Guardar y Vincular", on_click=save_invoice, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, upload_dialog)

    def confirm_unlink_invoice_modal(
        self,
        invoice_id: int,
        invoice_number: str,
        project_id: int,
        on_success: Optional[Callable[[], None]] = None
    ) -> None:
        unlink_dialog: Optional[ft.AlertDialog] = None

        def do_unlink(e: ft.ControlEvent) -> None:
            success = self.finance_service.unlink_invoice_from_project(invoice_id)
            if success:
                msg = f"Factura #{invoice_number} desvinculada del proyecto. Permanece registrada en Finanzas."
                show_snackbar(self.page_ref, msg)
            else:
                show_snackbar(self.page_ref, "No se pudo desvincular la factura.", is_error=True)
            if unlink_dialog:
                close_dialog(self.page_ref, unlink_dialog)
            if callable(on_success):
                on_success()

        unlink_dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LINK_OFF_ROUNDED, color=ft.Colors.ORANGE_800),
                ft.Text(f"Desvincular Factura #{invoice_number}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("¿Deseas desvincular esta factura del proyecto?"),
                        ft.Text("• La factura NO se eliminará del sistema.", size=12, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "• Seguirá existiendo intacta en la sección de Finanzas / Facturación.",
                            size=12,
                            color=TEXT_MUTED
                        ),
                        ft.Text(
                            "• Se registrará una anotación en la bitácora del proyecto.",
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
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, unlink_dialog)),
                ft.FilledButton("Sí, Desvincular", on_click=do_unlink, bgcolor=ft.Colors.ORANGE_800),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, unlink_dialog)
