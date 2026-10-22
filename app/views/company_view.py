import flet as ft
from app.services.company_service import CompanyService
from app.components.cards import SectionHeader, show_snackbar
from app.constant import (
    CARD_BGCOLOR,
    BORDER_COLOR,
    TEXT_SECONDARY,
    TEXT_HINT,
    BTN_PRIMARY_BG,
    BTN_ACCENT_BG,
)


class CompanyView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.company_service = CompanyService()
        self.build_ui()

    def build_ui(self) -> None:
        company = self.company_service.get_company()
        canvas = self.company_service.get_canvas(company["id"])

        # Form fields for Company
        self.legal_name = ft.TextField(label="Razón Social / Nombre Legal", value=company["legal_name"], expand=True)
        self.trade_name = ft.TextField(label="Nombre Comercial / Fantasía", value=company["trade_name"], expand=True)
        self.tax_id = ft.TextField(label="RUT / Identificación Fiscal", value=company["tax_id"], expand=True)
        self.business_activity = ft.TextField(label="Giro Comercial", value=company["business_activity"], expand=True)

        self.address = ft.TextField(label="Dirección", value=company["address"], expand=True)
        self.city = ft.TextField(label="Ciudad", value=company["city"], expand=True)
        self.phone = ft.TextField(label="Teléfono", value=company["phone"], expand=True)
        self.email = ft.TextField(label="Email de Contacto", value=company["email"], expand=True)
        self.website = ft.TextField(label="Sitio Web", value=company["website"], expand=True)
        self.bank_info = ft.TextField(
            label="Datos Bancarios (para presupuestos y facturas)",
            value=company["bank_information"],
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True
        )

        def save_company_data(e: ft.ControlEvent) -> None:
            self.company_service.update_company(
                company["id"],
                legal_name=self.legal_name.value.strip(),
                trade_name=self.trade_name.value.strip(),
                tax_id=self.tax_id.value.strip(),
                business_activity=self.business_activity.value.strip(),
                address=self.address.value.strip(),
                city=self.city.value.strip(),
                phone=self.phone.value.strip(),
                email=self.email.value.strip(),
                website=self.website.value.strip(),
                bank_information=self.bank_info.value.strip(),
            )
            show_snackbar(self.page_ref, "Datos de la empresa guardados correctamente.")

        company_form_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Información Comercial y Legal", size=15, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY),
                    ft.Row([self.legal_name, self.trade_name]),
                    ft.Row([self.tax_id, self.business_activity]),
                    ft.Row([self.address, self.city]),
                    ft.Row([self.phone, self.email, self.website]),
                    ft.Row([self.bank_info]),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Guardar Datos de Empresa",
                                icon=ft.Icons.SAVE_ROUNDED,
                                on_click=save_company_data,
                                bgcolor=BTN_PRIMARY_BG,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # Canvas Fields
        self.canvas_value_prop = ft.TextField(
            label="Propuesta de Valor", value=canvas["value_propositions"], multiline=True, min_lines=3
        )
        self.canvas_segments = ft.TextField(
            label="Segmentos de Clientes", value=canvas["customer_segments"], multiline=True, min_lines=3
        )
        self.canvas_channels = ft.TextField(
            label="Canales", value=canvas["channels"], multiline=True, min_lines=3
        )
        self.canvas_relations = ft.TextField(
            label="Relaciones con Clientes", value=canvas["customer_relationships"], multiline=True, min_lines=3
        )
        self.canvas_revenue = ft.TextField(
            label="Fuentes de Ingresos", value=canvas["revenue_streams"], multiline=True, min_lines=3
        )
        self.canvas_resources = ft.TextField(
            label="Recursos Clave", value=canvas["key_resources"], multiline=True, min_lines=3
        )
        self.canvas_activities = ft.TextField(
            label="Actividades Clave", value=canvas["key_activities"], multiline=True, min_lines=3
        )
        self.canvas_partners = ft.TextField(
            label="Socios Clave", value=canvas["key_partners"], multiline=True, min_lines=3
        )
        self.canvas_costs = ft.TextField(
            label="Estructura de Costes", value=canvas["cost_structure"], multiline=True, min_lines=3
        )

        def save_canvas_data(e: ft.ControlEvent) -> None:
            self.company_service.update_canvas(
                company["id"],
                value_propositions=self.canvas_value_prop.value.strip(),
                customer_segments=self.canvas_segments.value.strip(),
                channels=self.canvas_channels.value.strip(),
                customer_relationships=self.canvas_relations.value.strip(),
                revenue_streams=self.canvas_revenue.value.strip(),
                key_resources=self.canvas_resources.value.strip(),
                key_activities=self.canvas_activities.value.strip(),
                key_partners=self.canvas_partners.value.strip(),
                cost_structure=self.canvas_costs.value.strip(),
            )
            show_snackbar(self.page_ref, "Business Model Canvas actualizado correctamente.")

        # Canvas visual grid representation
        canvas_grid = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(content=self.canvas_partners, expand=1),
                        ft.Container(
                            content=ft.Column([self.canvas_activities, self.canvas_resources]),
                            expand=1
                        ),
                        ft.Container(content=self.canvas_value_prop, expand=1),
                        ft.Container(
                            content=ft.Column([self.canvas_relations, self.canvas_channels]),
                            expand=1
                        ),
                        ft.Container(content=self.canvas_segments, expand=1),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=12,
                ),
                ft.Row(
                    controls=[
                        ft.Container(content=self.canvas_costs, expand=1),
                        ft.Container(content=self.canvas_revenue, expand=1),
                    ],
                    spacing=12,
                ),
                ft.Row(
                    controls=[
                        ft.FilledButton(
                            "Guardar Canvas",
                            icon=ft.Icons.SAVE_ROUNDED,
                            on_click=save_canvas_data,
                            bgcolor=BTN_ACCENT_BG,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                )
            ],
            spacing=12,
        )

        canvas_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Business Model Canvas de la Empresa",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                                color=TEXT_SECONDARY,
                            ),
                            ft.Text("Estratégico", size=11, color=TEXT_HINT),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    canvas_grid,
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        header = SectionHeader(
            title="Mi Empresa",
            subtitle="Configuración del perfil comercial, antecedentes fiscales y modelo de negocio",
        )

        self.content = ft.ListView(
            controls=[
                header,
                ft.Container(height=16),
                company_form_card,
                ft.Container(height=16),
                canvas_card,
            ],
            spacing=0,
            expand=True,
        )
