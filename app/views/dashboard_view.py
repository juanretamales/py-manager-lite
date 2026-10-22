from typing import Optional, Callable
import flet as ft
from app.services.dashboard_service import DashboardService
from app.services.quote_service import QuoteService
from app.services.project_service import ProjectService
from app.services.currency_service import format_currency
from app.components.cards import StatCard, StatusChip, SectionHeader, open_dialog, close_dialog
from app.constant import (
    CARD_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    TEXT_HINT,
    BTN_PRIMARY_BG,
    METRIC_QUOTE_COLOR,
    METRIC_PROJECT_COLOR,
    METRIC_CLIENT_COLOR,
    METRIC_ALERT_COLOR,
    METRIC_SUCCESS_COLOR,
    METRIC_PENDING_COLLECT_COLOR,
    METRIC_PENDING_PAY_COLOR,
    BALANCE_POSITIVE_COLOR,
    BALANCE_NEGATIVE_COLOR,
)


class DashboardView(ft.Container):
    def __init__(self, page: ft.Page, on_navigate_tab: Optional[Callable[[int], None]] = None) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.on_navigate_tab = on_navigate_tab
        self.dash_service = DashboardService()
        self.quote_service = QuoteService()
        self.project_service = ProjectService()
        self.build_ui()

    def build_ui(self) -> None:
        metrics = self.dash_service.get_metrics()
        deadlines = self.dash_service.get_deadlines()
        timeline = self.dash_service.get_activity_timeline(limit=8)
        recent_quotes = self.quote_service.list_quotes()[:4]
        active_projects = self.project_service.list_projects()[:4]

        # ---------------------------------------------------------------------
        # 1. Cabecera y Acciones Rápidas
        # ---------------------------------------------------------------------
        header_actions = ft.Row(
            controls=[
                ft.OutlinedButton(
                    f"Auditar Documentos ({metrics['missing_docs_count']})",
                    icon=ft.Icons.FOLDER_SPECIAL_ROUNDED,
                    style=ft.ButtonStyle(
                        color=METRIC_ALERT_COLOR if metrics['missing_docs_count'] > 0 else METRIC_SUCCESS_COLOR
                    ),
                    on_click=lambda _: self.open_missing_docs_modal(),
                ),
                ft.OutlinedButton(
                    "Actualizar",
                    icon=ft.Icons.REFRESH_ROUNDED,
                    on_click=lambda _: self.refresh()
                ),
            ],
            spacing=8,
        )

        header = SectionHeader(
            title="Centro de Mando & Trazabilidad",
            subtitle=(
                "Supervisión ejecutiva, indicadores financieros en tiempo real, "
                "vencimientos y bitácora de actividad"
            ),
            action_button=header_actions,
        )

        # ---------------------------------------------------------------------
        # 2. Fila 1: Tarjetas Métricas Principales (StatCards)
        # ---------------------------------------------------------------------
        missing_color = METRIC_ALERT_COLOR if metrics["missing_docs_count"] > 0 else METRIC_SUCCESS_COLOR
        missing_sub = (
            f"{metrics['missing_invoice_docs']} fac · {metrics['missing_vouchers']} vou · "
            f"{metrics['missing_po_docs']} oc"
        )
        row1 = ft.Row(
            controls=[
                StatCard(
                    title="Cotizaciones Abiertas",
                    value=f"{metrics['open_quotes_count']}",
                    subtitle=f"{format_currency(metrics['open_quotes_amount'])} en negociación",
                    icon=ft.Icons.REQUEST_QUOTE_ROUNDED,
                    icon_color=METRIC_QUOTE_COLOR,
                ),
                StatCard(
                    title="Proyectos Activos",
                    value=f"{metrics['active_projects_count']}",
                    subtitle=f"Avance global: {metrics['avg_project_progress']}%",
                    icon=ft.Icons.WORK_ROUNDED,
                    icon_color=METRIC_PROJECT_COLOR,
                ),
                StatCard(
                    title="Clientes Activos",
                    value=f"{metrics['active_clients_count']}",
                    subtitle="Cartera comercial vigente",
                    icon=ft.Icons.PEOPLE_ROUNDED,
                    icon_color=METRIC_CLIENT_COLOR,
                ),
                StatCard(
                    title="Doc. Sin Respaldo",
                    value=f"{metrics['missing_docs_count']}",
                    subtitle=missing_sub,
                    icon=ft.Icons.ATTACH_FILE_ROUNDED,
                    icon_color=missing_color,
                ),
            ],
            spacing=16,
        )

        # ---------------------------------------------------------------------
        # 3. Fila 2: Indicadores Comparativos (Facturado vs Cobrado & Recibido vs Pagado)
        # ---------------------------------------------------------------------
        sales_progress = metrics["collection_rate"] / 100.0 if metrics["collection_rate"] <= 100 else 1.0
        sales_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=METRIC_SUCCESS_COLOR, size=20),
                                ft.Text("Facturación Emitida (Ventas)", weight=ft.FontWeight.BOLD, size=13),
                            ], spacing=6),
                            ft.Container(
                                content=ft.Text(
                                    f"Cobrado: {metrics['collection_rate']}%",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=METRIC_SUCCESS_COLOR,
                                ),
                                bgcolor=ft.Colors.GREEN_50,
                                border_radius=6,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ProgressBar(value=sales_progress, color=METRIC_SUCCESS_COLOR, bgcolor=ft.Colors.GREEN_50),
                    ft.Row(
                        controls=[
                            ft.Column([
                                ft.Text("Facturado", size=11, color=TEXT_MUTED),
                                ft.Text(format_currency(metrics["total_issued"]), weight=ft.FontWeight.BOLD, size=13),
                            ], spacing=1),
                            ft.Column([
                                ft.Text("Cobrado Efectivo", size=11, color=TEXT_MUTED),
                                ft.Text(
                                    format_currency(metrics["total_collected"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=METRIC_SUCCESS_COLOR,
                                ),
                            ], spacing=1),
                            ft.Column([
                                ft.Text("Por Cobrar", size=11, color=TEXT_MUTED),
                                ft.Text(
                                    format_currency(metrics["pending_collection"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=METRIC_PENDING_COLLECT_COLOR,
                                ),
                            ], spacing=1),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        expense_progress = metrics["payment_rate"] / 100.0 if metrics["payment_rate"] <= 100 else 1.0
        expense_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.TRENDING_DOWN_ROUNDED, color=METRIC_PENDING_PAY_COLOR, size=20),
                                ft.Text("Facturación Recibida (Gastos)", weight=ft.FontWeight.BOLD, size=13),
                            ], spacing=6),
                            ft.Container(
                                content=ft.Text(
                                    f"Pagado: {metrics['payment_rate']}%",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=METRIC_PENDING_PAY_COLOR,
                                ),
                                bgcolor=ft.Colors.RED_50,
                                border_radius=6,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ProgressBar(value=expense_progress, color=METRIC_PENDING_PAY_COLOR, bgcolor=ft.Colors.RED_50),
                    ft.Row(
                        controls=[
                            ft.Column([
                                ft.Text("Total Gastos", size=11, color=TEXT_MUTED),
                                ft.Text(
                                    format_currency(metrics["total_received"]), weight=ft.FontWeight.BOLD, size=13
                                ),
                            ], spacing=1),
                            ft.Column([
                                ft.Text("Pagado Proveedores", size=11, color=TEXT_MUTED),
                                ft.Text(
                                    format_currency(metrics["total_paid"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=METRIC_SUCCESS_COLOR,
                                ),
                            ], spacing=1),
                            ft.Column([
                                ft.Text("Por Pagar", size=11, color=TEXT_MUTED),
                                ft.Text(
                                    format_currency(metrics["pending_payment"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=METRIC_PENDING_PAY_COLOR,
                                ),
                            ], spacing=1),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        row2 = ft.Row(controls=[sales_card, expense_card], spacing=16)

        # ---------------------------------------------------------------------
        # 4. Fila 3: Balance Operacional Registrado
        # ---------------------------------------------------------------------
        balance_val = metrics["operational_balance"]
        balance_color = BALANCE_POSITIVE_COLOR if balance_val >= 0 else BALANCE_NEGATIVE_COLOR
        balance_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=balance_color, size=34),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Balance Operacional en Caja (Cobrado vs Pagado)",
                                size=13,
                                weight=ft.FontWeight.W_500,
                                color=TEXT_MUTED,
                            ),
                            ft.Text(
                                format_currency(balance_val), size=22, weight=ft.FontWeight.BOLD, color=balance_color
                            ),
                            ft.Text(
                                "Diferencia real entre cobros efectivos y egresos abonados. "
                                "Permite vigilar liquidez sin sustituir contabilidad formal.",
                                size=11,
                                color=TEXT_HINT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.FilledButton(
                        "Ir a Finanzas",
                        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                        on_click=lambda _: self.on_navigate_tab(5) if self.on_navigate_tab else None,
                        bgcolor=BTN_PRIMARY_BG,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # ---------------------------------------------------------------------
        # 5. Fila 4: Timelines de Actividad & Vencimientos / Pendientes
        # ---------------------------------------------------------------------
        timeline_items = []
        for ev in timeline:
            cat = ev.get("category", "NOTE")
            if cat == "PAYMENT":
                ev_icon = ft.Icons.PAYMENTS_ROUNDED
                ev_color = METRIC_SUCCESS_COLOR
            elif cat in ("INVOICE", "FACTURACION"):
                ev_icon = ft.Icons.RECEIPT_ROUNDED
                ev_color = METRIC_QUOTE_COLOR
            elif cat == "PROJECT":
                ev_icon = ft.Icons.WORK_ROUNDED
                ev_color = METRIC_PROJECT_COLOR
            elif cat == "QUOTE":
                ev_icon = ft.Icons.REQUEST_QUOTE_ROUNDED
                ev_color = ft.Colors.PURPLE_600
            else:
                ev_icon = ft.Icons.INFO_OUTLINE_ROUNDED
                ev_color = ft.Colors.BLUE_GREY_400

            timeline_items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ev_icon, size=16, color=ev_color),
                                bgcolor=ft.Colors.with_opacity(0.1, ev_color),
                                border_radius=6,
                                padding=6,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row([
                                        ft.Text(ev["title"], weight=ft.FontWeight.BOLD, size=12),
                                        ft.Text(ev["date_str"], size=10, color=TEXT_HINT),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Text(ev["description"], size=11, color=TEXT_MUTED),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )

        if not timeline_items:
            timeline_items.append(
                ft.Text("Aún no hay actividad registrada en la bitácora.", color=TEXT_MUTED, size=12)
            )

        timeline_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.TIMELINE_ROUNDED, color=METRIC_PROJECT_COLOR, size=18),
                                ft.Text("Línea de Tiempo de Actividad", weight=ft.FontWeight.BOLD, size=14),
                            ], spacing=6),
                            ft.Text("Últimos eventos", size=11, color=TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1),
                    ft.Column(controls=timeline_items, spacing=4),
                ],
                spacing=8,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        # Panel de Vencimientos y Pendientes
        deadline_items = []
        for dl in deadlines[:6]:
            if dl["is_overdue"]:
                badge_bg = ft.Colors.RED_50
                badge_fg = ft.Colors.RED_700
                diff_str = f"Venció hace {abs(dl['days_diff'])} días"
            elif dl["is_urgent"]:
                badge_bg = ft.Colors.AMBER_50
                badge_fg = ft.Colors.AMBER_900
                diff_str = f"Vence en {dl['days_diff']} días"
            else:
                badge_bg = ft.Colors.BLUE_GREY_50
                badge_fg = ft.Colors.BLUE_GREY_700
                diff_str = f"Vence en {dl['days_diff']} días" if dl["days_diff"] < 900 else "Sin fecha"

            deadline_items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Row([
                                        ft.Text(
                                            f"{dl['type_label']} #{dl['number']}",
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                        ),
                                        ft.Container(
                                            content=ft.Text(
                                                diff_str,
                                                size=10,
                                                weight=ft.FontWeight.BOLD,
                                                color=badge_fg,
                                            ),
                                            bgcolor=badge_bg,
                                            border_radius=4,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        ),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([
                                        ft.Text(dl["counterparty"][:28], size=11, color=TEXT_MUTED),
                                        ft.Text(f"Saldo: ${dl['balance']:,.0f}", size=11, weight=ft.FontWeight.BOLD),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )

        if not deadline_items:
            deadline_items.append(
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=METRIC_SUCCESS_COLOR, size=16),
                    ft.Text("Al día: no hay vencimientos atrasados.", color=TEXT_MUTED, size=12),
                ], spacing=6)
            )

        deadlines_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.NOTIFICATION_IMPORTANT_ROUNDED, color=METRIC_ALERT_COLOR, size=18),
                                ft.Text("Vencimientos y Pendientes", weight=ft.FontWeight.BOLD, size=14),
                            ], spacing=6),
                            ft.TextButton(
                                "Resolver en Finanzas",
                                on_click=lambda _: self.on_navigate_tab(5) if self.on_navigate_tab else None,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1),
                    ft.Column(controls=deadline_items, spacing=4),
                ],
                spacing=8,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        row3 = ft.Row(
            controls=[timeline_box, deadlines_box],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # ---------------------------------------------------------------------
        # 6. Fila 5: Cotizaciones Recientes & Proyectos en Ejecución
        # ---------------------------------------------------------------------
        quote_rows = []
        for q in recent_quotes:
            quote_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(q["number"], weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Text(q["client_name"][:20])),
                        ft.DataCell(ft.Text(format_currency(q["total_amount"]))),
                        ft.DataCell(StatusChip(q["status"])),
                    ]
                )
            )

        quotes_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("N° Cotización", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
            ],
            rows=quote_rows if quote_rows else [
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text("Sin cotizaciones")),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text("-")),
                    ]
                )
            ],
            heading_row_height=36,
            data_row_min_height=38,
            column_spacing=14,
        )

        quotes_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Cotizaciones en Curso", size=14, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY),
                            ft.TextButton(
                                "Ver todas",
                                on_click=lambda _: self.on_navigate_tab(3) if self.on_navigate_tab else None,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    quotes_table,
                ],
                spacing=6,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        project_rows = []
        for p in active_projects:
            project_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(p["name"][:22], weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Text(p["client_name"][:18])),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.ProgressBar(value=p["progress"] / 100, width=70, color=METRIC_QUOTE_COLOR),
                                    ft.Text(f"{p['progress']}%", size=11, color=TEXT_MUTED),
                                ],
                                spacing=6,
                            )
                        ),
                        ft.DataCell(StatusChip(p["status"])),
                    ]
                )
            )

        projects_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Proyecto", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Progreso", weight=ft.FontWeight.BOLD, size=12)),
                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=12)),
            ],
            rows=project_rows if project_rows else [
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text("Sin proyectos activos")),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text("-")),
                    ]
                )
            ],
            heading_row_height=36,
            data_row_min_height=38,
            column_spacing=14,
        )

        projects_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Proyectos en Ejecución", size=14, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY),
                            ft.TextButton(
                                "Ver todos",
                                on_click=lambda _: self.on_navigate_tab(4) if self.on_navigate_tab else None,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    projects_table,
                ],
                spacing=6,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

        row4 = ft.Row(controls=[quotes_box, projects_box], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)

        self.content = ft.ListView(
            controls=[
                header,
                ft.Container(height=10),
                row1,
                ft.Container(height=12),
                row2,
                ft.Container(height=12),
                balance_card,
                ft.Container(height=16),
                row3,
                ft.Container(height=16),
                row4,
            ],
            spacing=0,
            expand=True,
        )

    def open_missing_docs_modal(self) -> None:
        """Abre un modal detallado de auditoría con la documentación pendiente de respaldo."""
        data = self.dash_service.get_missing_documentation()
        modal: Optional[ft.AlertDialog] = None

        inv_rows = []
        for inv in data["invoices"]:
            inv_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(inv["type_label"], size=11)),
                        ft.DataCell(ft.Text(inv["number"], weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataCell(ft.Text(inv["counterparty"][:22], size=12)),
                        ft.DataCell(ft.Text(format_currency(inv["total_amount"]), size=12)),
                        ft.DataCell(ft.Text(inv["issue_date"], size=11)),
                    ]
                )
            )

        pay_rows = []
        for pay in data["payments"]:
            pay_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"Factura #{pay['invoice_number']}", size=12, weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(format_currency(pay["amount"]), weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataCell(ft.Text(pay["payment_method"], size=11)),
                        ft.DataCell(ft.Text(pay["reference"][:18], size=11)),
                        ft.DataCell(ft.Text(pay["payment_date"], size=11)),
                    ]
                )
            )

        po_rows = []
        for po in data["purchase_orders"]:
            po_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(po["number"], weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataCell(ft.Text(po["client_name"][:22], size=12)),
                        ft.DataCell(ft.Text(format_currency(po["amount"]), size=12)),
                        ft.DataCell(StatusChip(po["status"])),
                        ft.DataCell(ft.Text(po["issue_date"], size=11)),
                    ]
                )
            )

        modal = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, color=METRIC_ALERT_COLOR),
                ft.Text(f"Auditoría Documental ({data['total_missing']} pendientes)", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.Text(
                            "Facturas sin PDF / XML respaldado",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                            color=TEXT_PRIMARY,
                        ),
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("Tipo", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("N°", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Contraparte", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=11)),
                            ],
                            rows=inv_rows if inv_rows else [
                                ft.DataRow(
                                    cells=[
                                        ft.DataCell(ft.Text("Todas las facturas tienen respaldo")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                    ]
                                )
                            ],
                            heading_row_height=32,
                            data_row_min_height=34,
                            column_spacing=12,
                        ),
                        ft.Divider(height=1),
                        ft.Text(
                            "Pagos sin Comprobante de Transferencia (Voucher)",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                            color=TEXT_PRIMARY,
                        ),
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("Documento", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Medio", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Referencia", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=11)),
                            ],
                            rows=pay_rows if pay_rows else [
                                ft.DataRow(
                                    cells=[
                                        ft.DataCell(ft.Text("Todos los pagos tienen voucher")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                    ]
                                )
                            ],
                            heading_row_height=32,
                            data_row_min_height=34,
                            column_spacing=12,
                        ),
                        ft.Divider(height=1),
                        ft.Text(
                            "Órdenes de Compra sin PDF Original",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                            color=TEXT_PRIMARY,
                        ),
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("N° OC", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, size=11)),
                                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=11)),
                            ],
                            rows=po_rows if po_rows else [
                                ft.DataRow(
                                    cells=[
                                        ft.DataCell(ft.Text("Todas las OCs tienen PDF")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                        ft.DataCell(ft.Text("-")),
                                    ]
                                )
                            ],
                            heading_row_height=32,
                            data_row_min_height=34,
                            column_spacing=12,
                        ),
                    ],
                    spacing=10,
                ),
                width=720,
                height=480,
            ),
            actions=[
                ft.FilledButton(
                    "Ir al Módulo de Finanzas",
                    icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                    bgcolor=BTN_PRIMARY_BG,
                    on_click=lambda _: (
                        close_dialog(self.page_ref, modal),
                        self.on_navigate_tab(5) if self.on_navigate_tab else None,
                    ),
                ),
                ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, modal)),
            ],
        )
        open_dialog(self.page_ref, modal)

    def refresh(self) -> None:
        self.build_ui()
        if self.page_ref:
            self.page_ref.update()
