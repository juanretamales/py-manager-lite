from typing import Optional, List
import flet as ft
from app.services.client_service import ClientService
from app.services.ai_service import AIService
from app.components.cards import SectionHeader, open_dialog, close_dialog, show_snackbar
from app.constant import (
    CARD_BGCOLOR,
    CARD_ALT_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    BTN_PRIMARY_BG,
    STATUS_THEMES,
    METRIC_CLIENT_COLOR,
)


class ClientsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.client_service = ClientService()
        self.ai_service = AIService()
        self.search_field = ft.TextField(
            hint_text="Buscar por nombre, RUT, contacto o email...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
            dense=True,
            on_change=lambda _: self.load_data()
        )
        self.table_container = ft.Container(expand=True)
        self.build_ui()

    def build_ui(self) -> None:
        header = SectionHeader(
            title="Clientes",
            subtitle="Gestión de cartera de clientes, estados de relación y seguimiento histórico",
            action_button=ft.FilledButton(
                "Nuevo Cliente",
                icon=ft.Icons.PERSON_ADD_ROUNDED,
                on_click=lambda _: self.open_client_modal(),
                bgcolor=BTN_PRIMARY_BG,
            )
        )

        filter_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self.search_field,
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
        search = self.search_field.value.strip() if self.search_field.value else None
        clients = self.client_service.list_clients(search=search)

        rows = []
        for c in clients:
            status_text_color, status_bg_color = (
                STATUS_THEMES["ACTIVE"] if c["active"] else STATUS_THEMES["CANCELLED"]
            )
            status_chip = ft.Container(
                content=ft.Text(
                    "Activo" if c["active"] else "Inactivo",
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=status_text_color
                ),
                bgcolor=status_bg_color,
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            )

            actions = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY_OUTLINED,
                        tooltip="Ver Detalle y Timeline",
                        icon_size=18,
                        on_click=lambda _, cid=c["id"]: self.open_detail_modal(cid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        tooltip="Editar",
                        icon_size=18,
                        on_click=lambda _, cid=c["id"]: self.open_client_modal(cid)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.TOGGLE_ON if c["active"] else ft.Icons.TOGGLE_OFF,
                        tooltip="Desactivar" if c["active"] else "Activar",
                        icon_size=20,
                        icon_color=status_text_color,
                        on_click=lambda _, cid=c["id"]: self.toggle_client_status(cid)
                    )
                ],
                spacing=0,
            )

            legal_name_ctrl = (
                ft.Text(c["legal_name"], size=11, color=TEXT_MUTED)
                if c["legal_name"] else ft.Container()
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(c["name"], weight=ft.FontWeight.BOLD, size=13),
                                    legal_name_ctrl,
                                ],
                                spacing=0,
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ),
                        ft.DataCell(ft.Text(c["tax_id"] or "-")),
                        ft.DataCell(ft.Text(c["contact_name"] or "-")),
                        ft.DataCell(ft.Text(c["email"] or "-")),
                        ft.DataCell(ft.Text(c["phone"] or "-")),
                        ft.DataCell(status_chip),
                        ft.DataCell(actions),
                    ]
                )
            )

        if not rows:
            self.table_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.PERSON_OFF_ROUNDED, size=48, color=TEXT_MUTED),
                        ft.Text("No se encontraron clientes registrados", color=TEXT_MUTED, size=14),
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
                                ft.DataColumn(ft.Text("Cliente / Razón Social", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("RUT", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Contacto", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Email", weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataColumn(ft.Text("Teléfono", weight=ft.FontWeight.BOLD, size=12)),
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
                bgcolor=CARD_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
                expand=True,
            )

        if self.page_ref:
            self.page_ref.update()

    def toggle_client_status(self, client_id: int):
        new_status = self.client_service.toggle_active(client_id)
        msg = "Cliente reactivado." if new_status else "Cliente marcado como inactivo."
        show_snackbar(self.page_ref, msg)
        self.load_data()

    def open_client_modal(self, client_id=None):
        is_edit = client_id is not None
        title_text = "Editar Cliente" if is_edit else "Nuevo Cliente"

        client_data = self.client_service.get_client(client_id) if is_edit else {}

        name_field = ft.TextField(label="Nombre Comercial *", value=client_data.get("name", ""), autofocus=True)
        legal_name_field = ft.TextField(label="Razón Social", value=client_data.get("legal_name", ""))
        tax_id_field = ft.TextField(label="RUT / Identificación Fiscal", value=client_data.get("tax_id", ""))
        activity_field = ft.TextField(label="Giro Comercial", value=client_data.get("business_activity", ""))
        contact_field = ft.TextField(label="Persona de Contacto", value=client_data.get("contact_name", ""))
        email_field = ft.TextField(label="Email", value=client_data.get("email", ""))
        phone_field = ft.TextField(label="Teléfono", value=client_data.get("phone", ""))
        address_field = ft.TextField(label="Dirección", value=client_data.get("address", ""))
        notes_field = ft.TextField(
            label="Notas adicionales",
            value=client_data.get("notes", ""),
            multiline=True,
            min_lines=2
        )

        dialog: Optional[ft.AlertDialog] = None

        def save_action(e):
            if not name_field.value.strip():
                show_snackbar(self.page_ref, "El nombre del cliente es obligatorio.", is_error=True)
                return

            payload = {
                "name": name_field.value.strip(),
                "legal_name": legal_name_field.value.strip(),
                "tax_id": tax_id_field.value.strip(),
                "business_activity": activity_field.value.strip(),
                "contact_name": contact_field.value.strip(),
                "email": email_field.value.strip(),
                "phone": phone_field.value.strip(),
                "address": address_field.value.strip(),
                "notes": notes_field.value.strip(),
            }

            if is_edit:
                self.client_service.update_client(client_id, **payload)
                show_snackbar(self.page_ref, "Cliente actualizado con éxito.")
            else:
                self.client_service.create_client(**payload)
                show_snackbar(self.page_ref, "Cliente creado con éxito.")

            close_dialog(self.page_ref, dialog)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(title_text, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([name_field, legal_name_field]),
                        ft.Row([tax_id_field, activity_field]),
                        ft.Row([contact_field, phone_field]),
                        ft.Row([email_field, address_field]),
                        notes_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=650,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ft.FilledButton("Guardar", on_click=save_action, bgcolor=BTN_PRIMARY_BG),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, dialog)

    def open_detail_modal(self, client_id: int) -> None:
        client = self.client_service.get_client(client_id)
        if not client:
            return

        timeline_items = []
        for ev in client["events"]:
            timeline_items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED, size=14, color=METRIC_CLIENT_COLOR),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                ev["event_type"],
                                                weight=ft.FontWeight.BOLD,
                                                size=11,
                                                color=TEXT_SECONDARY
                                            ),
                                            ft.Text(ev["date"], size=10, color=TEXT_MUTED),
                                        ],
                                        spacing=8,
                                    ),
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

        new_note_field = ft.TextField(hint_text="Registrar una llamada, reunión o nota...", expand=True, dense=True)
        detail_dialog: Optional[ft.AlertDialog] = None

        def add_note_action(e: ft.ControlEvent) -> None:
            if new_note_field.value.strip() and detail_dialog:
                self.client_service.add_event(client_id, "NOTE", new_note_field.value.strip())
                new_note_field.value = ""
                close_dialog(self.page_ref, detail_dialog)
                self.open_detail_modal(client_id)

        active_color, _ = STATUS_THEMES["ACTIVE"] if client["active"] else STATUS_THEMES["CANCELLED"]
        contact_summary = (
            f"Contacto: {client['contact_name'] or '-'} | "
            f"Email: {client['email'] or '-'} | Tel: {client['phone'] or '-'}"
        )
        timeline_controls: List[ft.Control] = (
            list(timeline_items) if timeline_items
            else [ft.Text("Sin eventos aún.", size=12, color=TEXT_MUTED)]
        )

        ai_summary_container = ft.Container()

        def generate_ai_summary(_: ft.ControlEvent) -> None:
            ai_summary_container.content = ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.PURPLE_700),
                    ft.Text("Generando resumen ejecutivo con IA...", size=12, italic=True, color=TEXT_MUTED),
                ],
                spacing=8,
            )
            if self.page_ref:
                self.page_ref.update()

            summary = self.ai_service.summarize_client_history(
                client_name=client["name"],
                legal_name=client.get("legal_name") or "",
                tax_id=client.get("tax_id") or "",
                notes=client.get("events") or [],
            )

            ai_summary_container.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.PURPLE_700),
                                ft.Text(
                                    "Resumen Ejecutivo (IA)",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.PURPLE_900,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Text(summary, size=11, color=TEXT_PRIMARY),
                    ],
                    spacing=6,
                ),
                padding=10,
                bgcolor=ft.Colors.PURPLE_50,
                border_radius=6,
                border=ft.Border.all(1, ft.Colors.PURPLE_200),
            )
            if self.page_ref:
                self.page_ref.update()

        ai_summary_btn = (
            ft.TextButton(
                "Resumen Ejecutivo IA",
                icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                icon_color=ft.Colors.PURPLE_700,
                on_click=generate_ai_summary,
            )
            if self.ai_service.is_feature_enabled("summarize_client")
            else ft.Container()
        )

        detail_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Text(f"Detalle: {client['name']}", weight=ft.FontWeight.BOLD),
                    ft.Row(
                        controls=[
                            ai_summary_btn,
                            ft.Text("Activo" if client["active"] else "Inactivo", size=12, color=active_color),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(f"Razón Social: {client['legal_name'] or '-'}", size=12),
                                    ft.Text(f"RUT: {client['tax_id'] or '-'}", size=12),
                                    ft.Text(contact_summary, size=12),
                                    ft.Text(f"Dirección: {client['address'] or '-'}", size=12),
                                    ft.Text(f"Notas: {client['notes'] or '-'}", size=12, italic=True),
                                ],
                                spacing=4,
                            ),
                            padding=12,
                            bgcolor=CARD_ALT_BGCOLOR,
                            border_radius=6,
                        ),
                        ai_summary_container,
                        ft.Text(
                            "Historial y Timeline de Interacciones",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                            color=TEXT_SECONDARY
                        ),
                        ft.Container(
                            content=ft.ListView(
                                controls=timeline_controls,
                                height=200,
                            ),
                            border=ft.Border.all(1, BORDER_COLOR),
                            border_radius=6,
                            padding=8,
                        ),
                        ft.Row(
                            controls=[
                                new_note_field,
                                ft.FilledButton("Agregar Nota", on_click=add_note_action, bgcolor=BTN_PRIMARY_BG)
                            ],
                            spacing=8,
                        )
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=650,
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, detail_dialog))
            ]
        )
        open_dialog(self.page_ref, detail_dialog)
