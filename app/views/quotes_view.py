from typing import Optional, Callable, Dict, Any
import flet as ft
from app.services.quote_service import QuoteService
from app.services.client_service import ClientService
from app.services.currency_service import format_currency
from app.services.ai_service import AIService
from app.models.quote import QuoteStatus
from app.components.cards import SectionHeader, StatusChip, open_dialog, close_dialog, show_snackbar
from app.constant import (
    CARD_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    BTN_PRIMARY_BG,
    BTN_DANGER_ICON,
    STATUS_THEMES,
    METRIC_PROJECT_COLOR,
)


class QuotesView(ft.Container):
    def __init__(
        self,
        page: ft.Page,
        on_project_created: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.on_project_created = on_project_created
        self.quote_service = QuoteService()
        self.client_service = ClientService()
        self.ai_service = AIService()

        # Filtro de Estado
        self.status_filter = ft.Dropdown(
            label="Estado",
            options=[
                ft.dropdown.Option(key="ALL", text="Todos los Estados (Activos)"),
                ft.dropdown.Option(key=QuoteStatus.DRAFT, text="Borrador"),
                ft.dropdown.Option(key=QuoteStatus.SENT, text="Enviada"),
                ft.dropdown.Option(key=QuoteStatus.NEGOTIATION, text="Negociación"),
                ft.dropdown.Option(key=QuoteStatus.ACCEPTED, text="Aceptada"),
                ft.dropdown.Option(key=QuoteStatus.REJECTED, text="Rechazada"),
                ft.dropdown.Option(key=QuoteStatus.EXPIRED, text="Expirada"),
                ft.dropdown.Option(key=QuoteStatus.DELETED, text="🗑️ Eliminadas (Ocultas)"),
            ],
            value="ALL",
            width=220,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        # Filtro de Clientes
        self.client_filter = ft.Dropdown(
            label="Cliente",
            options=[ft.dropdown.Option(key="ALL", text="Todos los Clientes")],
            value="ALL",
            width=220,
            dense=True,
            on_select=lambda _: self.load_data()
        )

        # Filtro de Fecha de Emisión
        self.date_filter = ft.TextField(
            label="Fecha Emisión",
            hint_text="YYYY-MM-DD",
            width=150,
            dense=True,
            on_submit=lambda _: self.load_data(),
        )

        # DatePicker para selección gráfica de fecha
        self.date_picker = ft.DatePicker(
            on_change=self.on_date_picked
        )

        self.table_container = ft.Container(expand=True)
        self.build_ui()

    def on_date_picked(self, e):
        if e.control.value:
            self.date_filter.value = e.control.value.strftime("%Y-%m-%d")
            if self.page_ref:
                self.page_ref.update()
            self.load_data()

    def open_date_picker(self, e):
        self.date_picker.open = True
        if self.page_ref:
            self.page_ref.update()

    def clear_date_filter(self, e):
        self.date_filter.value = ""
        if self.page_ref:
            self.page_ref.update()
        self.load_data()

    def build_ui(self):
        # Register date_picker in page overlay
        if self.page_ref and self.date_picker not in self.page_ref.overlay:
            self.page_ref.overlay.append(self.date_picker)

        # Populate clients dropdown
        self.refresh_client_options()

        header = SectionHeader(
            title="Cotizaciones",
            subtitle="Presupuestos comerciales a clientes, desglose de ítems e historial de estados",
            action_button=ft.FilledButton(
                "Nueva Cotización",
                icon=ft.Icons.ADD_ROUNDED,
                on_click=lambda _: self.open_create_quote_modal(),
                bgcolor=BTN_PRIMARY_BG,
            )
        )

        filter_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self.status_filter,
                    self.client_filter,
                    ft.Row(
                        controls=[
                            self.date_filter,
                            ft.IconButton(
                                icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
                                tooltip="Seleccionar fecha con calendario",
                                on_click=self.open_date_picker,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLEAR_ROUNDED,
                                tooltip="Limpiar filtro de fecha",
                                icon_size=18,
                                on_click=self.clear_date_filter,
                            )
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="Recargar lista",
                        on_click=lambda _: self.load_data()
                    )
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
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

    def refresh_client_options(self):
        clients = self.client_service.list_clients()
        seen_names = set()
        options = [ft.dropdown.Option(key="ALL", text="Todos los Clientes")]
        for c in clients:
            name = c["name"].strip()
            if name and name not in seen_names:
                seen_names.add(name)
                options.append(ft.dropdown.Option(key=name, text=name))
        self.client_filter.options = options

    def load_data(self):
        # 1. Filtro de Estado
        status_val = self.status_filter.value
        status = None if status_val == "ALL" else status_val

        # 2. Filtro de Cliente (por nombre único)
        client_val = self.client_filter.value
        client_name = None if (not client_val or client_val == "ALL") else client_val

        # 3. Filtro de Fecha
        date_val = self.date_filter.value.strip() if self.date_filter.value else None

        quotes = self.quote_service.list_quotes(client_name=client_name, status=status, issue_date=date_val)

        rows = []
        for q in quotes:
            is_deleted = q["status"] == QuoteStatus.DELETED

            actions_list = [
                ft.IconButton(
                    icon=ft.Icons.VISIBILITY_OUTLINED,
                    tooltip="Ver Detalle de Ítems",
                    icon_size=18,
                    on_click=lambda _, qid=q["id"]: self.open_quote_detail_modal(qid)
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT_ROUNDED,
                    tooltip="Modificar Cotización",
                    icon_size=18,
                    on_click=lambda _, qid=q["id"]: self.open_edit_quote_modal(qid)
                ),
            ]

            if is_deleted:
                # Acciones específicas para cotizaciones eliminadas
                actions_list.append(
                    ft.IconButton(
                        icon=ft.Icons.RESTORE_FROM_TRASH_ROUNDED,
                        tooltip="Restaurar a Borrador",
                        icon_size=18,
                        icon_color=STATUS_THEMES["ACCEPTED"][0],
                        on_click=lambda _, qid=q["id"]: self.restore_quote(qid)
                    )
                )
            else:
                # Acciones para cotizaciones activas
                actions_list.extend([
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                        tooltip="Aceptar Cotización",
                        icon_size=18,
                        icon_color=STATUS_THEMES["ACCEPTED"][0],
                        visible=(q["status"] != QuoteStatus.ACCEPTED),
                        on_click=lambda _, qid=q["id"]: self.change_quote_status(qid, QuoteStatus.ACCEPTED)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                        tooltip="Convertir a Proyecto",
                        icon_size=18,
                        icon_color=METRIC_PROJECT_COLOR,
                        visible=(q["status"] == QuoteStatus.ACCEPTED and not q["has_project"]),
                        on_click=lambda _, qid=q["id"]: self.convert_to_project(qid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        tooltip="Mover a Eliminadas (Ocultar)",
                        icon_size=18,
                        icon_color=BTN_DANGER_ICON,
                        on_click=lambda _, qid=q["id"]: self.delete_quote(qid)
                    )
                ])

            actions = ft.Row(controls=actions_list, spacing=0)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(q["number"], weight=ft.FontWeight.BOLD, size=13)),
                        ft.DataCell(ft.Text(q["client_name"])),
                        ft.DataCell(ft.Text(q["issue_date"])),
                        ft.DataCell(ft.Text(f"{q['items_count']} ítems", size=12, color=TEXT_MUTED)),
                        ft.DataCell(ft.Text(format_currency(q['subtotal']))),
                        ft.DataCell(ft.Text(format_currency(q['total_amount']), weight=ft.FontWeight.BOLD)),
                        ft.DataCell(StatusChip(q["status"])),
                        ft.DataCell(actions),
                    ]
                )
            )

        if not rows:
            if status == QuoteStatus.DELETED:
                empty_msg = "No hay cotizaciones eliminadas"
            else:
                empty_msg = "No se encontraron cotizaciones con los filtros aplicados"
            self.table_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.REQUEST_QUOTE_OUTLINED, size=48, color=TEXT_MUTED),
                        ft.Text(empty_msg, color=TEXT_MUTED, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=40,
                alignment=ft.Alignment(0, 0),
                bgcolor=CARD_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
            )
        else:
            self.table_container.content = ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("N°", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Emisión", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Ítems", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Neto", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Total (c/IVA)", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12)),
                            ],
                            rows=rows,
                            heading_row_height=42,
                            data_row_min_height=48,
                            column_spacing=18,
                        )
                    ],
                    expand=True,
                ),
                bgcolor=CARD_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
                expand=True,
            )

        if self.page_ref:
            self.page_ref.update()

    def change_quote_status(self, quote_id: int, new_status: str):
        self.quote_service.change_status(quote_id, new_status)
        show_snackbar(self.page_ref, f"Cotización actualizada a estado: {new_status}")
        self.load_data()

    def convert_to_project(self, quote_id: int):
        proj = self.quote_service.convert_to_project(quote_id)
        if proj:
            show_snackbar(self.page_ref, f"¡Proyecto '{proj['name']}' generado con éxito!")
            self.load_data()
            if self.on_project_created:
                self.on_project_created()

    def delete_quote(self, quote_id: int):
        self.quote_service.delete_quote(quote_id)
        show_snackbar(self.page_ref, "Cotización movida a Eliminadas (oculta).")
        self.load_data()

    def restore_quote(self, quote_id: int):
        self.quote_service.restore_quote(quote_id, restored_status=QuoteStatus.DRAFT)
        show_snackbar(self.page_ref, "Cotización restaurada al estado Borrador.")
        self.load_data()

    def improve_notes_action(self, notes_field: ft.TextField) -> None:
        """Pule la redacción comercial de notas y condiciones usando IA."""
        raw = (notes_field.value or "").strip()
        if not raw:
            show_snackbar(self.page_ref, "Escribe un borrador previo de notas o condiciones a mejorar.", is_error=True)
            return
        show_snackbar(self.page_ref, "Optimizando redacción comercial con IA...")
        improved = self.ai_service.improve_quote_text(raw)
        if improved and improved != raw:
            notes_field.value = improved
            if self.page_ref:
                self.page_ref.update()
            show_snackbar(self.page_ref, "¡Redacción comercial mejorada con IA!")

    def suggest_desc_action(self, desc_field: ft.TextField) -> None:
        """Sugiere una especificación técnica de alcance detallada para una partida usando IA."""
        raw = (desc_field.value or "").strip()
        if not raw:
            show_snackbar(self.page_ref, "Ingresa primero un concepto o servicio base.", is_error=True)
            return
        show_snackbar(self.page_ref, f"Generando especificación técnica para '{raw}'...")
        suggested = self.ai_service.suggest_item_description(raw)
        if suggested and suggested != raw:
            desc_field.value = suggested
            if self.page_ref:
                self.page_ref.update()
            show_snackbar(self.page_ref, "¡Especificación técnica generada con IA!")

    def open_create_quote_modal(self):
        clients = self.client_service.list_clients(active_only=True)
        if not clients:
            show_snackbar(
                self.page_ref,
                "Debe registrar al menos un cliente antes de crear una cotización.",
                is_error=True
            )
            return

        client_dropdown = ft.Dropdown(
            label="Cliente *",
            options=[ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients],
            value=str(clients[0]["id"]),
            expand=True,
        )
        notes_field = ft.TextField(label="Notas / Condiciones comerciales", multiline=True, min_lines=2, expand=True)

        items_data = [
            {"desc": ft.TextField(label="Descripción del ítem", expand=True, value="Servicios de desarrollo"),
             "qty": ft.TextField(label="Cant.", width=70, value="1"),
             "unit": ft.TextField(label="Unid.", width=80, value="un"),
             "price": ft.TextField(label="Precio Unitario ($)", width=130, value="500000")}
        ]
        items_column = ft.Column(spacing=8)

        subtotal_text = ft.Text("Subtotal: $500,000", size=13, weight=ft.FontWeight.W_500)
        tax_text = ft.Text("IVA (19%): $95,000", size=13, weight=ft.FontWeight.W_500)
        total_text = ft.Text("Total: $595,000", size=15, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)

        def recalculate_totals():
            subtotal = 0.0
            for item in items_data:
                try:
                    qty = float(item["qty"].value)
                    price = float(item["price"].value)
                    subtotal += qty * price
                except ValueError:
                    pass
            tax = round(subtotal * 0.19, 2)
            total = round(subtotal + tax, 2)
            subtotal_text.value = f"Subtotal: {format_currency(subtotal)}"
            tax_text.value = f"IVA (19%): {format_currency(tax)}"
            total_text.value = f"Total: {format_currency(total)}"
            if self.page_ref:
                self.page_ref.update()

        def render_items():
            controls = []
            for idx, item in enumerate(items_data):
                item["qty"].on_change = lambda _: recalculate_totals()
                item["price"].on_change = lambda _: recalculate_totals()

                remove_btn = ft.IconButton(
                    icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED,
                    icon_color=BTN_DANGER_ICON,
                    tooltip="Quitar ítem",
                    visible=len(items_data) > 1,
                    on_click=lambda _, i=idx: remove_item(i)
                )

                ai_desc_btn = ft.IconButton(
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    icon_color=ft.Colors.PURPLE_600,
                    tooltip="Sugerir especificación técnica con IA",
                    icon_size=18,
                    visible=self.ai_service.is_feature_enabled("suggest_descriptions"),
                    on_click=lambda _, itm=item: self.suggest_desc_action(itm["desc"]),
                )

                controls.append(
                    ft.Row(
                        controls=[item["desc"], ai_desc_btn, item["qty"], item["unit"], item["price"], remove_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            items_column.controls = controls
            recalculate_totals()

        def add_item(_):
            items_data.append({
                "desc": ft.TextField(label="Descripción del ítem", expand=True),
                "qty": ft.TextField(label="Cant.", width=70, value="1"),
                "unit": ft.TextField(label="Unid.", width=80, value="un"),
                "price": ft.TextField(label="Precio Unitario ($)", width=130, value="0")
            })
            render_items()

        def remove_item(idx):
            if len(items_data) > 1:
                items_data.pop(idx)
                render_items()

        render_items()
        dialog = None

        def save_quote(e):
            if not client_dropdown.value:
                show_snackbar(self.page_ref, "Seleccione un cliente.", is_error=True)
                return

            parsed_items = []
            for item in items_data:
                desc = item["desc"].value.strip()
                if not desc:
                    continue
                try:
                    qty = float(item["qty"].value)
                    price = float(item["price"].value)
                except ValueError:
                    show_snackbar(self.page_ref, "Cantidad o precio inválido en los ítems.", is_error=True)
                    return

                parsed_items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit": item["unit"].value.strip() or "un",
                    "unit_price": price
                })

            if not parsed_items:
                show_snackbar(self.page_ref, "Agregue al menos un ítem con descripción.", is_error=True)
                return

            self.quote_service.create_quote(
                client_id=int(client_dropdown.value),
                items_data=parsed_items,
                notes=notes_field.value.strip()
            )
            show_snackbar(self.page_ref, "Cotización creada con éxito.")
            close_dialog(self.page_ref, dialog)
            self.refresh_client_options()
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text("Nueva Cotización", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        client_dropdown,
                        ft.Row(
                            controls=[
                                ft.Text("Ítems de la Cotización", weight=ft.FontWeight.BOLD, size=13),
                                ft.TextButton("Agregar Ítem", icon=ft.Icons.ADD_ROUNDED, on_click=add_item)
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        items_column,
                        ft.Container(height=8),
                        ft.Row([subtotal_text, tax_text, total_text], alignment=ft.MainAxisAlignment.END, spacing=16),
                        ft.Divider(height=1),
                        ft.Row(
                            controls=[
                                notes_field,
                                ft.IconButton(
                                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                                    icon_color=ft.Colors.PURPLE_700,
                                    tooltip="Mejorar redacción de notas y condiciones con IA",
                                    visible=self.ai_service.is_feature_enabled("improve_quotes"),
                                    on_click=lambda _: self.improve_notes_action(notes_field),
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=720,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Cotización", on_click=save_quote, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_edit_quote_modal(self, quote_id: int):
        quote = self.quote_service.get_quote(quote_id)
        if not quote:
            show_snackbar(self.page_ref, "No se encontró la cotización.", is_error=True)
            return

        clients = self.client_service.list_clients()
        client_options = [ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in clients]

        client_dropdown = ft.Dropdown(
            label="Cliente *",
            options=client_options,
            value=str(quote["client_id"]),
            expand=True,
        )

        status_options = [
            ft.dropdown.Option(key=QuoteStatus.DRAFT, text="Borrador"),
            ft.dropdown.Option(key=QuoteStatus.SENT, text="Enviada"),
            ft.dropdown.Option(key=QuoteStatus.NEGOTIATION, text="Negociación"),
            ft.dropdown.Option(key=QuoteStatus.ACCEPTED, text="Aceptada"),
            ft.dropdown.Option(key=QuoteStatus.REJECTED, text="Rechazada"),
            ft.dropdown.Option(key=QuoteStatus.EXPIRED, text="Expirada"),
            ft.dropdown.Option(key=QuoteStatus.DELETED, text="Eliminada"),
        ]
        status_dropdown = ft.Dropdown(
            label="Estado",
            options=status_options,
            value=quote["status"],
            width=200,
        )

        notes_field = ft.TextField(
            label="Notas / Condiciones comerciales",
            value=quote["notes"],
            multiline=True,
            min_lines=2,
            expand=True
        )

        # Pre-cargar los ítems existentes
        items_data = []
        for it in quote["items"]:
            qty_str = str(int(it["quantity"]) if it["quantity"].is_integer() else it["quantity"])
            items_data.append({
                "desc": ft.TextField(label="Descripción del ítem", expand=True, value=it["description"]),
                "qty": ft.TextField(label="Cant.", width=70, value=qty_str),
                "unit": ft.TextField(label="Unid.", width=80, value=it["unit"]),
                "price": ft.TextField(label="Precio Unitario ($)", width=130, value=str(int(it["unit_price"])))
            })

        if not items_data:
            items_data.append({
                "desc": ft.TextField(label="Descripción del ítem", expand=True, value=""),
                "qty": ft.TextField(label="Cant.", width=70, value="1"),
                "unit": ft.TextField(label="Unid.", width=80, value="un"),
                "price": ft.TextField(label="Precio Unitario ($)", width=130, value="0")
            })

        items_column = ft.Column(spacing=8)

        subtotal_text = ft.Text(f"Subtotal: ${quote['subtotal']:,.0f}", size=13, weight=ft.FontWeight.W_500)
        tax_text = ft.Text(f"IVA (19%): ${quote['tax_amount']:,.0f}", size=13, weight=ft.FontWeight.W_500)
        total_text = ft.Text(
            f"Total: ${quote['total_amount']:,.0f}",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=TEXT_PRIMARY
        )

        def recalculate_totals():
            subtotal = 0.0
            for item in items_data:
                try:
                    qty = float(item["qty"].value)
                    price = float(item["price"].value)
                    subtotal += qty * price
                except ValueError:
                    pass
            tax = round(subtotal * 0.19, 2)
            total = round(subtotal + tax, 2)
            subtotal_text.value = f"Subtotal: {format_currency(subtotal)}"
            tax_text.value = f"IVA (19%): {format_currency(tax)}"
            total_text.value = f"Total: {format_currency(total)}"
            if self.page_ref:
                self.page_ref.update()

        def render_items():
            controls = []
            for idx, item in enumerate(items_data):
                item["qty"].on_change = lambda _: recalculate_totals()
                item["price"].on_change = lambda _: recalculate_totals()

                remove_btn = ft.IconButton(
                    icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED,
                    icon_color=BTN_DANGER_ICON,
                    tooltip="Quitar ítem",
                    visible=len(items_data) > 1,
                    on_click=lambda _, i=idx: remove_item(i)
                )

                ai_desc_btn = ft.IconButton(
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    icon_color=ft.Colors.PURPLE_600,
                    tooltip="Sugerir especificación técnica con IA",
                    icon_size=18,
                    visible=self.ai_service.is_feature_enabled("suggest_descriptions"),
                    on_click=lambda _, itm=item: self.suggest_desc_action(itm["desc"]),
                )

                controls.append(
                    ft.Row(
                        controls=[item["desc"], ai_desc_btn, item["qty"], item["unit"], item["price"], remove_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            items_column.controls = controls
            recalculate_totals()

        def add_item(_):
            items_data.append({
                "desc": ft.TextField(label="Descripción del ítem", expand=True),
                "qty": ft.TextField(label="Cant.", width=70, value="1"),
                "unit": ft.TextField(label="Unid.", width=80, value="un"),
                "price": ft.TextField(label="Precio Unitario ($)", width=130, value="0")
            })
            render_items()

        def remove_item(idx):
            if len(items_data) > 1:
                items_data.pop(idx)
                render_items()

        render_items()
        dialog = None

        def update_quote_action(e):
            if not client_dropdown.value:
                show_snackbar(self.page_ref, "Seleccione un cliente.", is_error=True)
                return

            parsed_items = []
            for item in items_data:
                desc = item["desc"].value.strip()
                if not desc:
                    continue
                try:
                    qty = float(item["qty"].value)
                    price = float(item["price"].value)
                except ValueError:
                    show_snackbar(self.page_ref, "Cantidad o precio inválido en los ítems.", is_error=True)
                    return

                parsed_items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit": item["unit"].value.strip() or "un",
                    "unit_price": price
                })

            if not parsed_items:
                show_snackbar(self.page_ref, "Agregue al menos un ítem con descripción.", is_error=True)
                return

            self.quote_service.update_quote(
                quote_id=quote_id,
                client_id=int(client_dropdown.value),
                items_data=parsed_items,
                status=status_dropdown.value,
                notes=notes_field.value.strip()
            )
            show_snackbar(self.page_ref, f"Cotización {quote['number']} actualizada con éxito.")
            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Text(f"Modificar Cotización {quote['number']}", weight=ft.FontWeight.BOLD),
                    StatusChip(quote["status"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([client_dropdown, status_dropdown]),
                        ft.Row(
                            controls=[
                                ft.Text("Ítems de la Cotización", weight=ft.FontWeight.BOLD, size=13),
                                ft.TextButton("Agregar Ítem", icon=ft.Icons.ADD_ROUNDED, on_click=add_item)
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        items_column,
                        ft.Container(height=8),
                        ft.Row([subtotal_text, tax_text, total_text], alignment=ft.MainAxisAlignment.END, spacing=16),
                        ft.Divider(height=1),
                        ft.Row(
                            controls=[
                                notes_field,
                                ft.IconButton(
                                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                                    icon_color=ft.Colors.PURPLE_700,
                                    tooltip="Mejorar redacción de notas y condiciones con IA",
                                    visible=self.ai_service.is_feature_enabled("improve_quotes"),
                                    on_click=lambda _: self.improve_notes_action(notes_field),
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=740,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar Cambios", on_click=update_quote_action, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_quote_detail_modal(self, quote_id: int):
        quote = self.quote_service.get_quote(quote_id)
        if not quote:
            return

        item_rows = []
        for it in quote["items"]:
            item_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(it["description"])),
                        ft.DataCell(ft.Text(f"{it['quantity']} {it['unit']}")),
                        ft.DataCell(ft.Text(format_currency(it['unit_price']))),
                        ft.DataCell(ft.Text(format_currency(it['subtotal']), weight=ft.FontWeight.BOLD)),
                    ]
                )
            )

        items_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Descripción", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Cantidad", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Precio Unitario", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD, size=12)),
            ],
            rows=item_rows,
            heading_row_height=38,
            data_row_min_height=42,
            column_spacing=24,
        )

        detail_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Text(f"Cotización {quote['number']}", weight=ft.FontWeight.BOLD),
                    StatusChip(quote["status"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"Cliente: {quote['client_name']}", weight=ft.FontWeight.W_600, size=14),
                        ft.Text(f"Fecha Emisión: {quote['issue_date']}", size=12, color=TEXT_MUTED),
                        items_table,
                        ft.Container(height=8),
                        ft.Row(
                            controls=[
                                ft.Text(f"Subtotal: {format_currency(quote['subtotal'])}", size=13),
                                ft.Text(f"IVA (19%): {format_currency(quote['tax_amount'])}", size=13),
                                ft.Text(
                                    f"Total: {format_currency(quote['total_amount'])}",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXT_PRIMARY
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.END,
                            spacing=16,
                        ),
                        (
                            ft.Text(f"Notas: {quote['notes']}", size=12, italic=True)
                            if quote["notes"] else ft.Container()
                        ),
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=680,
            ),
            actions=[
                ft.FilledButton(
                    "Modificar Cotización",
                    icon=ft.Icons.EDIT_ROUNDED,
                    on_click=lambda _: [
                        close_dialog(self.page_ref, detail_dialog),
                        self.open_edit_quote_modal(quote_id)
                    ],
                    bgcolor=BTN_PRIMARY_BG
                ),
                ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, detail_dialog))
            ]
        )
        open_dialog(self.page_ref, detail_dialog)
