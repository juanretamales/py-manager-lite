import os
from datetime import datetime
from typing import Optional
import flet as ft
from app.services.export_service import ExportService, get_preset_dates
from app.services.currency_service import format_currency
from app.services.finance_service import open_document
from app.services.ai_service import AIService
from app.components.cards import SectionHeader, open_dialog, close_dialog, show_snackbar
from app.constant import (
    CARD_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    BTN_PRIMARY_BG,
    METRIC_PROJECT_COLOR,
    METRIC_SUCCESS_COLOR,
    METRIC_ALERT_COLOR,
    METRIC_PENDING_PAY_COLOR,
    METRIC_PENDING_COLLECT_COLOR,
    BALANCE_POSITIVE_COLOR,
    BALANCE_NEGATIVE_COLOR,
)


class ExportsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.export_service = ExportService()
        self.ai_service = AIService()

        # Date filter controls
        preset_s, preset_e = get_preset_dates("THIS_MONTH")
        self.preset_dropdown = ft.Dropdown(
            label="Período Predefinido",
            options=[
                ft.dropdown.Option(key="THIS_MONTH", text="Mes Actual"),
                ft.dropdown.Option(key="LAST_MONTH", text="Mes Anterior"),
                ft.dropdown.Option(key="THIS_YEAR", text="Año en Curso"),
                ft.dropdown.Option(key="ALL", text="Todo el Historial"),
            ],
            value="THIS_MONTH",
            width=180,
            dense=True,
            on_select=self.on_preset_changed,
        )

        self.start_date_field = ft.TextField(
            label="Desde (YYYY-MM-DD)",
            value=preset_s or "",
            width=160,
            dense=True,
        )
        self.end_date_field = ft.TextField(
            label="Hasta (YYYY-MM-DD)",
            value=preset_e or "",
            width=160,
            dense=True,
        )

        self.delimiter_dropdown = ft.Dropdown(
            label="Formato CSV (Excel)",
            options=[
                ft.dropdown.Option(key=";", text="; (Punto y coma - Excel Chile/ES)"),
                ft.dropdown.Option(key=",", text=", (Coma estándar internacional)"),
            ],
            value=";",
            width=260,
            dense=True,
        )

        self.summary_container = ft.Container()
        self.recent_files_container = ft.Container()

        self.build_ui()

    def on_preset_changed(self, e: ft.ControlEvent) -> None:
        preset = self.preset_dropdown.value
        s, end = get_preset_dates(preset or "THIS_MONTH")
        self.start_date_field.value = s or ""
        self.end_date_field.value = end or ""
        self.refresh_summary()

    def show_ai_diagnosis_dialog(self) -> None:
        """Presenta un modal con el análisis cualitativo y tributario generado por IA para el período."""
        s = self.start_date_field.value.strip() if self.start_date_field.value else None
        end = self.end_date_field.value.strip() if self.end_date_field.value else None
        period_label = f"{s or 'Histórico'} a {end or 'Actualidad'}"

        summary = self.export_service.get_summary_metrics(s, end)
        top_expenses = self.export_service.get_top_expenses(s, end, limit=5)
        client_billing = self.export_service.get_client_billing(s, end, limit=5)

        diagnosis_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.ProgressRing(width=20, height=20, stroke_width=2, color=ft.Colors.PURPLE_700),
                            ft.Text("Analizando métricas financieras del período con IA...", size=13, italic=True),
                        ],
                        spacing=10,
                    )
                ],
                tight=True,
            ),
            width=650,
            padding=16,
        )

        detail_dialog: Optional[ft.AlertDialog] = None

        def close_modal(e: ft.ControlEvent) -> None:
            if detail_dialog:
                close_dialog(self.page_ref, detail_dialog)

        detail_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_700, size=22),
                    ft.Text(f"Diagnóstico Financiero IA ({period_label})", weight=ft.FontWeight.BOLD, size=15),
                ],
                spacing=8,
            ),
            content=diagnosis_content,
            actions=[
                ft.TextButton("Cerrar", on_click=close_modal),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(self.page_ref, detail_dialog)

        # Llamar al servicio de IA
        analysis_text = self.ai_service.assist_report_analysis(
            period_label=period_label,
            metrics=summary,
            top_expenses=top_expenses,
            client_billing=client_billing,
        )

        diagnosis_content.content = ft.Column(
            controls=[
                ft.Text(
                    analysis_text,
                    size=12,
                    selectable=True,
                    color=TEXT_PRIMARY,
                ),
            ],
            tight=True,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        if self.page_ref:
            self.page_ref.update()

    def build_ui(self) -> None:
        header = SectionHeader(
            title="Reportes y Exportación Contable",
            subtitle=(
                "Generación de libros tributarios (compras y ventas), conciliación de cobros/pagos, "
                "auditoría documental y reportes ejecutivos en CSV/PDF"
            ),
            action_button=ft.OutlinedButton(
                "Abrir Carpeta de Exportaciones",
                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                on_click=lambda _: self.open_exports_folder(),
            ),
        )

        # Filters Bar
        filter_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self.preset_dropdown,
                    self.start_date_field,
                    self.end_date_field,
                    self.delimiter_dropdown,
                    ft.FilledButton(
                        "Actualizar Período",
                        icon=ft.Icons.FILTER_ALT_ROUNDED,
                        bgcolor=BTN_PRIMARY_BG,
                        on_click=lambda _: self.refresh_summary(),
                    ),
                    ft.FilledButton(
                        "Diagnóstico Ejecutivo IA",
                        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                        bgcolor=ft.Colors.PURPLE_700,
                        visible=self.ai_service.is_feature_enabled("assist_reports"),
                        on_click=lambda _: self.show_ai_diagnosis_dialog(),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(bottom=16),
        )

        # Export Action Cards
        actions_grid = self.build_actions_grid()

        self.content = ft.ListView(
            controls=[
                header,
                filter_bar,
                self.summary_container,
                ft.Container(height=16),
                ft.Text("Opciones de Exportación para Contador y Gestión", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                actions_grid,
                ft.Container(height=24),
                ft.Text("Archivos Exportados Recientemente", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                self.recent_files_container,
            ],
            spacing=0,
            expand=True,
        )

        self.refresh_summary()

    def refresh_summary(self) -> None:
        s = self.start_date_field.value.strip() or None
        end = self.end_date_field.value.strip() or None
        summary = self.export_service.get_period_summary(s, end)

        vat_val = summary["vat_balance"]
        vat_color = BALANCE_POSITIVE_COLOR if vat_val >= 0 else BALANCE_NEGATIVE_COLOR
        vat_label = "IVA Débito a Pagar (F29)" if vat_val >= 0 else "Remanente Crédito Fiscal"

        cash_val = summary["operational_cash_flow"]
        cash_color = BALANCE_POSITIVE_COLOR if cash_val >= 0 else BALANCE_NEGATIVE_COLOR

        self.summary_container.content = ft.Row(
            controls=[
                self._build_mini_kpi(
                    title="Ventas del Período",
                    value=format_currency(summary["sales_total"]),
                    sub=f"Neto: {format_currency(summary['sales_net'])} | IVA: {format_currency(summary['sales_tax'])}",
                    icon=ft.Icons.TRENDING_UP_ROUNDED,
                    color=METRIC_SUCCESS_COLOR,
                ),
                self._build_mini_kpi(
                    title="Gastos del Período",
                    value=format_currency(summary["purchases_total"]),
                    sub=(
                        f"Neto: {format_currency(summary['purchases_net'])} | "
                        f"IVA: {format_currency(summary['purchases_tax'])}"
                    ),
                    icon=ft.Icons.TRENDING_DOWN_ROUNDED,
                    color=METRIC_PENDING_PAY_COLOR,
                ),
                self._build_mini_kpi(
                    title="Estimación IVA F29",
                    value=format_currency(abs(vat_val)),
                    sub=vat_label,
                    icon=ft.Icons.CALCULATE_ROUNDED,
                    color=vat_color,
                ),
                self._build_mini_kpi(
                    title="Flujo Caja en Período",
                    value=format_currency(cash_val),
                    sub=(
                        f"Cobrado: {format_currency(summary['collected_cash'])} | "
                        f"Pagado: {format_currency(summary['paid_cash'])}"
                    ),
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                    color=cash_color,
                ),
            ],
            spacing=14,
        )

        self.refresh_recent_files()
        if self.page_ref:
            self.page_ref.update()

    def _build_mini_kpi(
        self,
        title: str,
        value: str,
        sub: str,
        icon: ft.Icon,
        color: ft.Colors,
    ) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=24, color=color),
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        border_radius=8,
                        padding=10,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(title, size=11, color=TEXT_MUTED, weight=ft.FontWeight.W_500),
                            ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                            ft.Text(sub, size=10, color=TEXT_MUTED),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

    def build_actions_grid(self) -> ft.Column:
        # Tarjeta 1: Libro de Ventas
        card_ventas = self._build_action_card(
            title="Libro de Ventas (CSV / Excel)",
            desc="Detalle completo de facturas emitidas, folios, RUTs de clientes, netos, IVA (19%) y saldos.",
            icon=ft.Icons.RECEIPT_LONG_ROUNDED,
            icon_color=METRIC_SUCCESS_COLOR,
            primary_btn_text="Exportar CSV Ventas",
            on_primary_click=lambda _: self.export_sales_book(),
        )

        # Tarjeta 2: Libro de Compras
        card_compras = self._build_action_card(
            title="Libro de Compras y Gastos (CSV)",
            desc="Detalle de facturas recibidas de proveedores, IVA crédito fiscal, categorías contables y estado.",
            icon=ft.Icons.SHOPPING_BAG_ROUNDED,
            icon_color=METRIC_PENDING_PAY_COLOR,
            primary_btn_text="Exportar CSV Compras",
            on_primary_click=lambda _: self.export_purchases_book(),
        )

        # Tarjeta 3: Conciliación de Pagos
        card_pagos = self._build_action_card(
            title="Conciliación de Cobros y Pagos (CSV)",
            desc=(
                "Registro cronológico de abonos monetarios, medios de pago, referencias bancarias y voucher."
            ),
            icon=ft.Icons.PAYMENTS_ROUNDED,
            icon_color=METRIC_PENDING_COLLECT_COLOR,
            primary_btn_text="Exportar CSV Pagos",
            on_primary_click=lambda _: self.export_payments(),
        )

        # Tarjeta 4: Reporte Financiero Ejecutivo (HTML/PDF)
        card_executive = self._build_action_card(
            title="Reporte Financiero Ejecutivo (HTML / PDF)",
            desc="Informe formal listo para imprimir o guardar en PDF con membrete corporativo, KPIs y tablas.",
            icon=ft.Icons.PRINT_ROUNDED,
            icon_color=METRIC_PROJECT_COLOR,
            primary_btn_text="Generar y Abrir PDF / HTML",
            on_primary_click=lambda _: self.export_executive_html(),
        )

        # Tarjeta 5: Auditoría de Documentos Faltantes
        card_missing = self._build_action_card(
            title="Auditoría de Documentos Faltantes",
            desc="Reporte para carpeta tributaria de facturas sin PDF, pagos sin comprobante y OCs sin archivo.",
            icon=ft.Icons.FOLDER_SPECIAL_ROUNDED,
            icon_color=METRIC_ALERT_COLOR,
            primary_btn_text="Descargar CSV Auditoría",
            on_primary_click=lambda _: self.export_missing_csv(),
            secondary_btn_text="Ver Informe Imprimible (PDF)",
            on_secondary_click=lambda _: self.export_missing_html(),
        )

        return ft.Column(
            controls=[
                ft.Row([card_ventas, card_compras], spacing=14),
                ft.Row([card_pagos, card_executive], spacing=14),
                ft.Row([card_missing], spacing=14),
            ],
            spacing=14,
        )

    def _build_action_card(
        self,
        title: str,
        desc: str,
        icon: ft.Icon,
        icon_color: ft.Colors,
        primary_btn_text: str,
        on_primary_click: callable,
        secondary_btn_text: Optional[str] = None,
        on_secondary_click: Optional[callable] = None,
    ) -> ft.Container:
        actions = [
            ft.FilledButton(
                primary_btn_text,
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                bgcolor=BTN_PRIMARY_BG,
                on_click=on_primary_click,
            )
        ]
        if secondary_btn_text and on_secondary_click:
            actions.append(
                ft.OutlinedButton(
                    secondary_btn_text,
                    icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                    on_click=on_secondary_click,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(icon, size=24, color=icon_color),
                            ft.Text(title, weight=ft.FontWeight.BOLD, size=14),
                        ],
                        spacing=8,
                    ),
                    ft.Text(desc, size=12, color=TEXT_MUTED),
                    ft.Container(height=4),
                    ft.Row(controls=actions, spacing=8),
                ],
                spacing=6,
            ),
            padding=16,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
            expand=True,
        )

    def export_sales_book(self) -> None:
        s = self.start_date_field.value.strip() or None
        end = self.end_date_field.value.strip() or None
        sep = self.delimiter_dropdown.value or ";"
        try:
            path = self.export_service.export_sales_book_csv(s, end, delimiter=sep)
            show_snackbar(self.page_ref, f"Libro de Ventas exportado con éxito: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al exportar ventas: {ex}", is_error=True)

    def export_purchases_book(self) -> None:
        s = self.start_date_field.value.strip() or None
        end = self.end_date_field.value.strip() or None
        sep = self.delimiter_dropdown.value or ";"
        try:
            path = self.export_service.export_purchases_book_csv(s, end, delimiter=sep)
            show_snackbar(self.page_ref, f"Libro de Compras exportado con éxito: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al exportar compras: {ex}", is_error=True)

    def export_payments(self) -> None:
        s = self.start_date_field.value.strip() or None
        end = self.end_date_field.value.strip() or None
        sep = self.delimiter_dropdown.value or ";"
        try:
            path = self.export_service.export_payments_reconciliation_csv(s, end, delimiter=sep)
            show_snackbar(self.page_ref, f"Conciliación de pagos exportada: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al exportar pagos: {ex}", is_error=True)

    def export_executive_html(self) -> None:
        s = self.start_date_field.value.strip() or None
        end = self.end_date_field.value.strip() or None
        try:
            path = self.export_service.generate_executive_report_html(s, end)
            show_snackbar(self.page_ref, f"Reporte ejecutivo generado: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al generar reporte: {ex}", is_error=True)

    def export_missing_csv(self) -> None:
        sep = self.delimiter_dropdown.value or ";"
        try:
            path = self.export_service.export_missing_documents_csv(delimiter=sep)
            show_snackbar(self.page_ref, f"Auditoría documental exportada: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al exportar auditoría: {ex}", is_error=True)

    def export_missing_html(self) -> None:
        try:
            path = self.export_service.generate_missing_documents_report_html()
            show_snackbar(self.page_ref, f"Informe imprimible de auditoría generado: {os.path.basename(path)}")
            open_document(path)
            self.refresh_recent_files()
        except Exception as ex:
            show_snackbar(self.page_ref, f"Error al generar informe: {ex}", is_error=True)

    def open_exports_folder(self) -> None:
        folder = str(self.export_service.exports_dir)
        opened = open_document(folder)
        if not opened:
            show_snackbar(self.page_ref, f"Carpeta de exportaciones: {folder}")

    def refresh_recent_files(self) -> None:
        exports_dir = self.export_service.exports_dir
        if not exports_dir.exists():
            return

        all_files = sorted(
            [f for f in exports_dir.iterdir() if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:8]

        rows = []
        for f in all_files:
            size_kb = f.stat().st_size / 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            ext = f.suffix.lower()
            icon_file = ft.Icons.TABLE_VIEW_ROUNDED if ext == ".csv" else ft.Icons.PRINT_ROUNDED
            color_file = ft.Colors.GREEN_700 if ext == ".csv" else ft.Colors.INDIGO_700

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Row([
                                ft.Icon(icon_file, size=16, color=color_file),
                                ft.Text(f.name, weight=ft.FontWeight.W_500, size=12),
                            ], spacing=6)
                        ),
                        ft.DataCell(ft.Text(f"{size_kb:.1f} KB", size=11)),
                        ft.DataCell(ft.Text(mtime, size=11)),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                tooltip="Abrir archivo",
                                icon_size=18,
                                on_click=lambda _, p=str(f): open_document(p),
                            )
                        ),
                    ]
                )
            )

        if not rows:
            self.recent_files_container.content = ft.Container(
                content=ft.Text("Aún no se han generado exportaciones.", color=TEXT_MUTED, size=12),
                padding=12,
            )
        else:
            self.recent_files_container.content = ft.Container(
                content=ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Nombre de Archivo", weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataColumn(ft.Text("Tamaño", weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataColumn(ft.Text("Fecha de Generación", weight=ft.FontWeight.BOLD, size=12)),
                        ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD, size=12)),
                    ],
                    rows=rows,
                    heading_row_height=36,
                    data_row_min_height=38,
                    column_spacing=18,
                ),
                bgcolor=CARD_BGCOLOR,
                border_radius=8,
                border=ft.Border.all(1, BORDER_COLOR),
            )
