import os
import sys
import time
from typing import Optional, Callable, Any, Dict
import flet as ft
from app.core.config import (
    APP_TITLE,
    APP_VERSION,
    DB_PATH,
    PROFILE_DIR,
    BACKUPS_DIR,
    get_documents_dir,
)
from app.components import (
    SectionHeader,
    show_snackbar,
    open_dialog,
    close_dialog,
    run_operation_with_progress,
)
from app.services.client_service import ClientService
from app.services.quote_service import QuoteService
from app.services.project_service import ProjectService
from app.services.finance_service import FinanceService, open_document
from app.services.auth_service import AuthService
from app.services.ai_service import AIService, DEFAULT_MODELS
from app.services.currency_service import get_currency_service, CURRENCY_PRESETS
from app.services.backup_service import BackupService
from app.services.turso_cloud_service import TursoCloudService

from app.models.invoice import InvoiceType
from app.models.quote import QuoteStatus
from app.constant import (
    CARD_BGCOLOR,
    CARD_ALT_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    BTN_DEMO_BG,
    BTN_PRIMARY_BG,
)


class SettingsView(ft.Container):
    def __init__(
        self,
        page: ft.Page,
        on_demo_data_loaded: Optional[Callable[[], None]] = None
    ) -> None:
        super().__init__(expand=True, padding=24)
        self.page_ref = page
        self.on_demo_data_loaded = on_demo_data_loaded
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.active_file_target = None
        self.build_ui()

    def on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Callback ejecutado cuando el usuario selecciona un archivo o carpeta mediante FilePicker."""
        picked_path = e.path or (e.files[0].path if e.files else None)
        if picked_path:
            if callable(self.active_file_target):
                self.active_file_target(picked_path)
            elif isinstance(self.active_file_target, ft.TextField):
                self.active_file_target.value = picked_path
                if self.page_ref:
                    self.page_ref.update()

    def trigger_directory_picker(self, target_callback_or_field) -> None:
        """Abre el diálogo nativo para seleccionar una carpeta del sistema."""
        self.active_file_target = target_callback_or_field
        if self.page_ref and hasattr(self.page_ref, "services") and self.file_picker not in self.page_ref.services:
            self.page_ref.services.append(self.file_picker)
            self.page_ref.update()

        async def _pick() -> None:
            try:
                path = await self.file_picker.get_directory_path(
                    dialog_title="Seleccionar carpeta de almacenamiento de archivos"
                )
                if path:
                    if callable(self.active_file_target):
                        self.active_file_target(path)
                    elif isinstance(self.active_file_target, ft.TextField):
                        self.active_file_target.value = path
                        if self.page_ref:
                            self.page_ref.update()
            except Exception as ex:
                if self.page_ref:
                    show_snackbar(self.page_ref, f"Error al seleccionar carpeta: {ex}", is_error=True)

        if self.page_ref:
            self.page_ref.run_task(_pick)

    def trigger_file_picker(
        self,
        target_callback_or_field,
        allowed_extensions: Optional[list] = None
    ) -> None:
        """Abre el diálogo nativo de selección de archivos registrando el servicio en la página."""
        self.active_file_target = target_callback_or_field
        if self.page_ref and hasattr(self.page_ref, "services") and self.file_picker not in self.page_ref.services:
            self.page_ref.services.append(self.file_picker)
            self.page_ref.update()

        async def _pick() -> None:
            try:
                files = await self.file_picker.pick_files(
                    allow_multiple=False,
                    allowed_extensions=allowed_extensions or ["db", "sqlite", "libsql", "sql", "zip"]
                )
                if files and len(files) > 0:
                    picked_path = files[0].path
                    if callable(self.active_file_target):
                        self.active_file_target(picked_path)
                    elif isinstance(self.active_file_target, ft.TextField):
                        self.active_file_target.value = picked_path
                        if self.page_ref:
                            self.page_ref.update()
            except Exception as ex:
                if self.page_ref:
                    show_snackbar(self.page_ref, f"Error al abrir selector: {ex}", is_error=True)

        if self.page_ref:
            self.page_ref.run_task(_pick)

    def build_ui(self) -> None:
        # Calculate db size
        db_size_kb = round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0

        info_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Diagnóstico Técnico - Fase 0 (PoC Flet)",
                        weight=ft.FontWeight.BOLD,
                        size=15,
                        color=TEXT_SECONDARY
                    ),
                    ft.Divider(height=1),
                    ft.Row([
                        ft.Text("Aplicación:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(f"{APP_TITLE} (v{APP_VERSION})")
                    ]),
                    ft.Row([
                        ft.Text("Python Runtime:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(f"{sys.version.split()[0]} ({sys.executable})")
                    ]),
                    ft.Row([
                        ft.Text("Framework UI:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(f"Flet {ft.__version__}")
                    ]),
                    ft.Row([
                        ft.Text("ORM & Base de datos:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text("SQLAlchemy 2.x + Turso / LibSQL (Local en archivos)")
                    ]),
                    ft.Row([
                        ft.Text("Ubicación BD (profile):", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(str(DB_PATH))
                    ]),
                    ft.Row([
                        ft.Text("Tamaño actual BD:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(f"{db_size_kb} KB")
                    ]),
                    ft.Row([
                        ft.Text("Almacenamiento docs:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(str(get_documents_dir()))
                    ]),
                ],
                spacing=8,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        poc_notes_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Criterios de Evaluación del Roadmap (Fase 0)",
                        weight=ft.FontWeight.BOLD,
                        size=15,
                        color=TEXT_SECONDARY
                    ),
                    ft.Divider(height=1),
                    ft.Text(
                        "• Navegación y Layout: Menú lateral reactivo, renderizado fluido.",
                        size=12
                    ),
                    ft.Text(
                        "• Formularios: Validación en caliente, cálculo reactivo de subtotales, IVA y totales.",
                        size=12
                    ),
                    ft.Text(
                        "• Tablas: Renderizado nativo con DataTables y DataRows, acciones y chips.",
                        size=12
                    ),
                    ft.Text(
                        "• Persistencia SQLite: Separación View → Service → Repository → SQLAlchemy.",
                        size=12
                    ),
                    ft.Text(
                        "• Empaquetado: Listo para compilar con 'flet pack' o PyInstaller.",
                        size=12
                    ),
                ],
                spacing=8,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        def load_sample_data(e: ft.ControlEvent) -> None:
            def _worker(progress_cb: Callable[[float, Optional[str], Optional[str]], None]) -> bool:
                progress_cb(0.10, "Comprobando...", "Comprobando conexión y esquemas de la base de datos...")
                time.sleep(0.2)

                client_svc = ClientService()
                quote_svc = QuoteService()
                proj_svc = ProjectService()
                fin_svc = FinanceService()

                # Client 1
                progress_cb(
                    0.25,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Registrando cliente #1: Inversiones del Sur SpA (RUT 77.890.123-4)..."
                )
                time.sleep(0.15)
                c1 = client_svc.create_client(
                    name="Inversiones del Sur SpA",
                    legal_name="Inversiones del Sur y Compañía SpA",
                    tax_id="77.890.123-4",
                    business_activity="Inversiones y Retail",
                    contact_name="Lorena Valenzuela",
                    email="lvalenzuela@inversionesdelsur.cl",
                    phone="+56 9 8765 4321",
                    address="Av. Providencia 1234, Providencia",
                    notes="Cliente corporativo con ciclo de pago a 30 días."
                )

                # Client 2
                progress_cb(
                    0.45,
                    "Cargando para mejorar la experiencia de usuario...",
                    "Registrando cliente #2: TechStartup Chile (RUT 76.543.210-K)..."
                )
                time.sleep(0.15)
                c2 = client_svc.create_client(
                    name="TechStartup Chile",
                    legal_name="Tecnologías Digitales Emergentes SpA",
                    tax_id="76.543.210-K",
                    business_activity="Desarrollo de Software",
                    contact_name="Carlos Méndez",
                    email="carlos@techstartup.cl",
                    phone="+56 9 1234 5678",
                    address="Alonso de Córdova 5151, Las Condes",
                    notes="Startup en crecimiento, proyectos ágiles."
                )

                # Quote for Client 1
                progress_cb(
                    0.60,
                    "Afinando para el perfil del usuario...",
                    "Creando propuestas comerciales y vinculando a proyectos activos..."
                )
                time.sleep(0.15)
                q1 = quote_svc.create_quote(
                    client_id=c1["id"],
                    items_data=[
                        {
                            "description": "Consultoría y Auditoría de Procesos",
                            "quantity": 1,
                            "unit": "mes",
                            "unit_price": 1200000
                        },
                        {
                            "description": "Implementación de Sistema de Control Interno",
                            "quantity": 1,
                            "unit": "proyecto",
                            "unit_price": 2800000
                        }
                    ],
                    notes="Plazo de ejecución: 6 semanas. Facturación contra hito 1 y 2."
                )
                quote_svc.change_status(q1["id"], QuoteStatus.ACCEPTED)
                proj = quote_svc.convert_to_project(q1["id"], "Auditoría e Implementación de Control Interno")
                if proj:
                    proj_svc.update_progress(
                        proj["id"], 65, "Finalizada auditoría, en proceso de implementación."
                    )

                # Quote for Client 2
                quote_svc.create_quote(
                    client_id=c2["id"],
                    items_data=[
                        {
                            "description": "Desarrollo de Arquitectura en la Nube",
                            "quantity": 1,
                            "unit": "mes",
                            "unit_price": 1800000
                        },
                        {
                            "description": "Soporte e Infraestructura DevOps",
                            "quantity": 2,
                            "unit": "mes",
                            "unit_price": 600000
                        }
                    ],
                    notes="En negociación de condiciones de servicio."
                )

                # Invoices
                progress_cb(
                    0.80,
                    "Afinando para el perfil del usuario...",
                    "Registrando facturas tributarias emitidas y recibidas con pagos..."
                )
                time.sleep(0.15)
                inv1 = fin_svc.create_invoice(
                    type=InvoiceType.ISSUED,
                    number="FAC-101",
                    client_id=c1["id"],
                    net_amount=2000000,
                    tax_amount=380000,
                    total_amount=2380000,
                    category="Consultoría"
                )
                fin_svc.register_payment(
                    inv1["id"],
                    amount=1000000,
                    payment_method="Transferencia",
                    reference="TRF-887123"
                )

                inv2 = fin_svc.create_invoice(
                    type=InvoiceType.RECEIVED,
                    number="FAC-PRV-554",
                    issuer_name="Amazon Web Services Chile",
                    net_amount=250000,
                    tax_amount=47500,
                    total_amount=297500,
                    category="Servicios Cloud"
                )
                fin_svc.register_payment(
                    inv2["id"],
                    amount=297500,
                    payment_method="Tarjeta",
                    reference="CHG-AWS-SEP"
                )

                progress_cb(
                    0.95,
                    "Afinando para el perfil del usuario...",
                    "Sincronizando índices y verificando balances..."
                )
                time.sleep(0.2)
                return True

            def _on_demo_done(res: Any) -> None:
                show_snackbar(self.page_ref, "¡Datos de demostración cargados exitosamente!")
                if self.on_demo_data_loaded:
                    self.on_demo_data_loaded()

            run_operation_with_progress(
                page=self.page_ref,
                title="Cargar Datos de Demostración",
                worker_fn=_worker,
                on_success=_on_demo_done,
                initial_status="Comprobando...",
                initial_log="Iniciando población de base de datos de demostración...",
                icon_color=ft.Colors.INDIGO_600,
                success_message="¡Datos de demostración cargados exitosamente!",
            )

        demo_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Datos de Demostración", weight=ft.FontWeight.BOLD, size=15, color=TEXT_SECONDARY),
                    ft.Text(
                        "Poblar la base de datos con clientes, cotizaciones, proyectos y facturas "
                        "de ejemplo para evaluar inmediatamente la experiencia.",
                        size=12,
                        color=TEXT_MUTED
                    ),
                    ft.Container(height=4),
                    ft.FilledButton(
                        "Cargar Datos de Ejemplo (Demo)",
                        icon=ft.Icons.DATA_OBJECT_ROUNDED,
                        bgcolor=BTN_DEMO_BG,
                        on_click=load_sample_data,
                    )
                ],
                spacing=8,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        auth_service = AuthService()
        profile_info = auth_service.get_profile_info() or {}

        def open_change_pin_dialog(e: ft.ControlEvent) -> None:
            pwd_field = ft.TextField(
                label="Contraseña Maestra Actual *",
                password=True,
                can_reveal_password=True,
                autofocus=True,
            )
            new_pin_field = ft.TextField(
                label="Nuevo PIN (4 a 6 dígitos) *",
                password=True,
                can_reveal_password=True,
                max_length=6,
            )
            dialog = None

            def save_new_pin(ev: ft.ControlEvent) -> None:
                pwd_val = pwd_field.value.strip() if pwd_field.value else ""
                pin_val = new_pin_field.value.strip() if new_pin_field.value else ""

                if not (pin_val.isdigit() and 4 <= len(pin_val) <= 6):
                    show_snackbar(self.page_ref, "El PIN debe ser numérico de 4 a 6 dígitos.", is_error=True)
                    return

                if auth_service.update_pin(pwd_val, pin_val):
                    show_snackbar(self.page_ref, "PIN actualizado exitosamente.")
                    close_dialog(self.page_ref, dialog)
                else:
                    show_snackbar(self.page_ref, "Contraseña maestra incorrecta.", is_error=True)

            dialog = ft.AlertDialog(
                title=ft.Text("Cambiar PIN de Desbloqueo", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Ingresa tu contraseña maestra actual para autorizar el nuevo PIN.", size=12),
                            pwd_field,
                            new_pin_field,
                        ],
                        spacing=12,
                        tight=True,
                    ),
                    width=400,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                    ft.FilledButton("Guardar Nuevo PIN", on_click=save_new_pin, bgcolor=BTN_PRIMARY_BG),
                ],
            )
            open_dialog(self.page_ref, dialog)

        # Gestión y migración de carpeta de almacenamiento (Local / Nube)

        active_storage_path = profile_info.get("storage_path") or str(get_documents_dir())
        active_storage_text = ft.Text(active_storage_path, expand=True, size=12)

        new_storage_path_field = ft.TextField(
            label="Nueva Carpeta de Almacenamiento (Local o Nube)",
            value=active_storage_path,
            hint_text="C:\\...\\Google Drive\\PyManager",
            expand=True,
            dense=True,
        )

        move_files_switch = ft.Switch(
            label="Mover automáticamente los archivos y documentos actuales a la nueva carpeta",
            value=True,
        )

        def execute_storage_migration(e: ft.ControlEvent) -> None:
            target_p = new_storage_path_field.value.strip() if new_storage_path_field.value else ""
            if not target_p:
                show_snackbar(self.page_ref, "Ingresa o selecciona una ruta válida.", is_error=True)
                return

            dialog = None

            def do_migrate(ev: ft.ControlEvent) -> None:
                close_dialog(self.page_ref, dialog)

                def _worker(progress_cb: Callable[[float, Optional[str], Optional[str]], None]) -> Dict[str, Any]:
                    return auth_service.migrate_storage_path(
                        new_path_str=target_p,
                        move_existing=move_files_switch.value,
                        progress_callback=progress_cb,
                    )

                def _on_done(res: Dict[str, Any]) -> None:
                    active_storage_text.value = res["new_path"]
                    show_snackbar(
                        self.page_ref,
                        f"Ubicación actualizada en profile.json. Archivos migrados: {res['files_moved']}."
                    )
                    if self.page_ref:
                        self.page_ref.update()

                run_operation_with_progress(
                    page=self.page_ref,
                    title="Mover Archivos de Almacenamiento",
                    worker_fn=_worker,
                    on_success=_on_done,
                    initial_status="Comprobando...",
                    initial_log=f"Iniciando cambio de ubicación hacia: {target_p}",
                    icon_color=ft.Colors.BLUE_700,
                    success_message="¡Archivos transferidos y base de datos actualizada!",
                )

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.DRIVE_FILE_MOVE_ROUNDED, color=ft.Colors.BLUE_700),
                    ft.Text("Confirmar Cambio de Ubicación", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("¿Deseas cambiar la carpeta de almacenamiento de archivos comercial a:", size=13),
                            ft.Text(f"• {target_p}", weight=ft.FontWeight.BOLD, size=12),
                            ft.Container(height=4),
                            ft.Text(
                                "Si la carpeta está en una unidad en la nube (Google Drive, Dropbox, OneDrive), "
                                "la sincronización será administrada por tu cliente de escritorio.",
                                size=11,
                                color=TEXT_MUTED,
                            ),
                        ],
                        spacing=8,
                        tight=True,
                    ),
                    width=450,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                    ft.FilledButton("Sí, Cambiar Ubicación", on_click=do_migrate, bgcolor=BTN_PRIMARY_BG),
                ],
            )
            open_dialog(self.page_ref, dialog)

        profile_security_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SECURITY_ROUNDED, size=20, color=TEXT_PRIMARY),
                            ft.Text(
                                "Seguridad, Perfil y Almacenamiento (Carpeta Profile / Nube)",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                                color=TEXT_SECONDARY,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1),
                    ft.Row([
                        ft.Text("Usuario Activo:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(profile_info.get("user_name", "No configurado")),
                    ]),
                    ft.Row([
                        ft.Text("Empresa:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(profile_info.get("company_name", "Sin especificar")),
                    ]),
                    ft.Row([
                        ft.Text("Ubicación Perfil:", weight=ft.FontWeight.BOLD, width=160),
                        ft.Text(str(PROFILE_DIR)),
                    ]),
                    ft.Row([
                        ft.Text("Carpeta Archivos:", weight=ft.FontWeight.BOLD, width=160),
                        active_storage_text,
                        ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                            tooltip="Abrir carpeta de archivos en el explorador",
                            icon_size=18,
                            icon_color=ft.Colors.BLUE_700,
                            on_click=lambda _: open_document(active_storage_text.value),
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                "Cambiar PIN de Desbloqueo",
                                icon=ft.Icons.PIN_ROUNDED,
                                on_click=open_change_pin_dialog,
                            ),
                        ]
                    ),
                    ft.Divider(height=1),
                    ft.Text(
                        "Ubicación de Archivos y Carpeta en Nube (Google Drive, Dropbox, OneDrive)",
                        size=13,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        "Puedes definir una carpeta en tu nube favorita para que la app de escritorio la sincronice. "
                        "El sistema moverá tus archivos organizados y actualizará las referencias.",
                        size=12,
                        color=TEXT_MUTED,
                    ),
                    ft.Row(
                        controls=[
                            new_storage_path_field,
                            ft.FilledButton(
                                "Examinar...",
                                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                on_click=lambda _: self.trigger_directory_picker(new_storage_path_field),
                                bgcolor=BTN_PRIMARY_BG,
                            ),
                        ],
                        spacing=10,
                    ),
                    move_files_switch,
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Cambiar y Mover Archivos Ahora",
                                icon=ft.Icons.DRIVE_FILE_MOVE_ROUNDED,
                                on_click=execute_storage_migration,
                                bgcolor=ft.Colors.BLUE_GREY_800,
                            ),
                        ]
                    ),
                ],
                spacing=10,
            ),

            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # ==============================================================================
        # 5. Turso Cloud & Sincronización Remota (Fase 5 del Roadmap)
        # ==============================================================================
        turso_service = TursoCloudService(auth_service=auth_service)
        init_turso_url, init_turso_token = auth_service.get_turso_credentials()

        turso_url_field = ft.TextField(
            label="URL Base de Datos Turso Cloud",
            value=init_turso_url,
            hint_text="libsql://tu-bd.turso.io o https://...",
            prefix_icon=ft.Icons.CLOUD_QUEUE_ROUNDED,
            expand=True,
        )

        turso_token_field = ft.TextField(
            label="Token de Autenticación Turso Cloud (Cifrado con AES-256-GCM)",
            value=init_turso_token,
            password=True,
            can_reveal_password=True,
            hint_text="eyJhbGciOi...",
            prefix_icon=ft.Icons.KEY_ROUNDED,
            expand=True,
        )

        has_init_turso = bool(init_turso_url and init_turso_token)
        turso_status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED if has_init_turso else ft.Icons.INFO_OUTLINE_ROUNDED,
            size=18,
            color=ft.Colors.GREEN_400 if has_init_turso else ft.Colors.BLUE_GREY_400,
        )

        turso_status_text = ft.Text(
            "Credenciales guardadas y cifradas en profile.json."
            if has_init_turso
            else "Ingresa tu URL y Token de Turso para activar la nube.",
            size=12,
            color=TEXT_MUTED,
        )

        turso_status_container = ft.Container(
            content=ft.Row(
                controls=[turso_status_icon, turso_status_text],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=CARD_ALT_BGCOLOR,
            border_radius=6,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        def test_turso_cloud_connection(e: ft.ControlEvent) -> None:
            url_val = turso_url_field.value.strip() if turso_url_field.value else ""
            tok_val = turso_token_field.value.strip() if turso_token_field.value else ""
            turso_status_icon.name = ft.Icons.HOURGLASS_EMPTY_ROUNDED
            turso_status_icon.color = ft.Colors.AMBER_400
            turso_status_text.value = "Probando conexión con Turso Cloud..."
            turso_status_text.color = ft.Colors.AMBER_400
            if self.page_ref:
                self.page_ref.update()

            res = turso_service.test_connection(url=url_val, token=tok_val)
            if res["connected"]:
                turso_status_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                turso_status_icon.color = ft.Colors.GREEN_400
                turso_status_text.value = (
                    f"Conectado a Turso Cloud ({res['latency_ms']} ms) | Tablas remotas: {res['table_count']}"
                )
                turso_status_text.color = ft.Colors.GREEN_400
                show_snackbar(self.page_ref, res["message"])
            else:
                turso_status_icon.name = ft.Icons.ERROR_OUTLINE_ROUNDED
                turso_status_icon.color = ft.Colors.RED_400
                turso_status_text.value = res["message"]
                turso_status_text.color = ft.Colors.RED_400
                show_snackbar(self.page_ref, res["message"], is_error=True)
            if self.page_ref:
                self.page_ref.update()

        def save_turso_cloud_credentials(e: ft.ControlEvent) -> None:
            url_val = turso_url_field.value.strip() if turso_url_field.value else ""
            tok_val = turso_token_field.value.strip() if turso_token_field.value else ""
            auth_service.update_turso_config(cloud_url=url_val, auth_token=tok_val)
            turso_status_icon.name = ft.Icons.LOCK_ROUNDED
            turso_status_icon.color = ft.Colors.GREEN_400
            turso_status_text.value = "Credenciales cifradas con AES-256-GCM y guardadas en profile.json."
            turso_status_text.color = ft.Colors.GREEN_400
            show_snackbar(
                self.page_ref,
                "Configuración de Turso Cloud cifrada con salt y guardada en profile."
            )
            if self.page_ref:
                self.page_ref.update()

        def confirm_push_to_cloud(e: ft.ControlEvent) -> None:
            if not turso_url_field.value or not turso_token_field.value:
                show_snackbar(self.page_ref, "Configura primero la URL y el Token de Turso.", is_error=True)
                return

            dialog = None

            def do_push(ev: ft.ControlEvent) -> None:
                close_dialog(self.page_ref, dialog)

                def _push_worker(progress_cb: Callable[[float, Optional[str], Optional[str]], None]) -> Dict[str, Any]:
                    progress_cb(0.15, "Comprobando...", "Comprobando credenciales y conexión con Turso Cloud...")
                    time.sleep(0.2)
                    progress_cb(
                        0.40,
                        "Cargando para mejorar la experiencia de usuario...",
                        "Extrayendo esquemas y tablas locales..."
                    )
                    res = turso_service.push_local_to_cloud()
                    progress_cb(
                        0.85,
                        "Afinando para el perfil del usuario...",
                        f"Transferidas {res['tables_synced']} tablas..."
                    )
                    time.sleep(0.2)
                    return res

                def _on_push_done(res: Dict[str, Any]) -> None:
                    msg = (
                        f"¡Sincronización a Turso Cloud exitosa! "
                        f"{res['tables_synced']} tablas y {res['records_synced']} registros."
                    )
                    show_snackbar(self.page_ref, msg)
                    test_turso_cloud_connection(None)

                run_operation_with_progress(
                    page=self.page_ref,
                    title="Sincronizar a Turso Cloud (Push)",
                    worker_fn=_push_worker,
                    on_success=_on_push_done,
                    initial_status="Comprobando...",
                    initial_log="Iniciando subida de base de datos a Turso Cloud...",
                    icon_color=ft.Colors.BLUE_600,
                    success_message="¡Base de datos replicada en la nube con éxito!",
                )

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, color=ft.Colors.BLUE_400),
                    ft.Text("Sincronizar a Turso Cloud (Push)", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "¿Deseas subir y replicar la base de datos local SQLite completa hacia Turso Cloud?",
                                size=13,
                            ),
                            ft.Container(height=4),
                            ft.Text(
                                "• Se crearán las tablas si no existen y se insertarán todos los registros actuales.\n"
                                "• Esto actualizará tu base de datos en la nube sin borrar archivos.",
                                size=11,
                                color=TEXT_MUTED,
                            ),
                        ],
                        spacing=8,
                        tight=True,
                    ),
                    width=460,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                    ft.FilledButton("Sí, Sincronizar a la Nube", on_click=do_push, bgcolor=BTN_PRIMARY_BG),
                ],
            )
            open_dialog(self.page_ref, dialog)

        def confirm_pull_from_cloud(e: ft.ControlEvent) -> None:
            if not turso_url_field.value or not turso_token_field.value:
                show_snackbar(self.page_ref, "Configura primero la URL y el Token de Turso.", is_error=True)
                return

            dialog = None

            def do_pull(ev: ft.ControlEvent) -> None:
                close_dialog(self.page_ref, dialog)

                def _pull_worker(progress_cb: Callable[[float, Optional[str], Optional[str]], None]) -> Dict[str, Any]:
                    progress_cb(0.15, "Comprobando...", "Verificando credenciales y enlace seguro a Turso Cloud...")
                    time.sleep(0.2)
                    progress_cb(
                        0.35,
                        "Cargando para mejorar la experiencia de usuario...",
                        "Creando respaldo de seguridad preventivo local..."
                    )
                    res = turso_service.pull_cloud_to_local(safety_backup=True)
                    progress_cb(
                        0.85,
                        "Afinando para el perfil del usuario...",
                        f"Tablas sincronizadas: {res['tables_synced']}..."
                    )
                    time.sleep(0.2)
                    return res

                def _on_pull_done(res: Dict[str, Any]) -> None:
                    msg = (
                        f"¡Descarga exitosa! {res['tables_synced']} tablas y "
                        f"{res['records_synced']} registros locales actualizados."
                    )
                    show_snackbar(self.page_ref, msg)
                    if self.on_demo_data_loaded:
                        self.on_demo_data_loaded()

                run_operation_with_progress(
                    page=self.page_ref,
                    title="Descargar de Turso Cloud (Pull)",
                    worker_fn=_pull_worker,
                    on_success=_on_pull_done,
                    initial_status="Comprobando...",
                    initial_log="Iniciando descarga de datos desde Turso Cloud...",
                    icon_color=ft.Colors.AMBER_700,
                    success_message="¡Base de datos local actualizada desde la nube!",
                )

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.CLOUD_DOWNLOAD_ROUNDED, color=ft.Colors.AMBER_400),
                    ft.Text("Descargar de Turso Cloud (Pull)", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "¿Deseas descargar la base de datos desde Turso Cloud y actualizar la copia local?",
                                size=13,
                            ),
                            ft.Container(height=4),
                            ft.Text(
                                "• SEGURIDAD: Se creará automáticamente un respaldo local en 'safety_backups/' "
                                "antes de reemplazar la información.\n"
                                "• Los datos locales serán sincronizados con la versión en la nube.",
                                size=11,
                                color=TEXT_MUTED,
                            ),
                        ],
                        spacing=8,
                        tight=True,
                    ),
                    width=460,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                    ft.FilledButton("Sí, Descargar y Respaldar", on_click=do_pull, bgcolor=ft.Colors.DEEP_ORANGE_700),
                ],
            )
            open_dialog(self.page_ref, dialog)

        def show_remote_tables_dialog(e: ft.ControlEvent) -> None:
            dialog = None
            summary = turso_service.get_remote_tables_summary()
            if not summary["success"]:
                show_snackbar(self.page_ref, f"No se pudo consultar Turso Cloud: {summary['error']}", is_error=True)
                return

            rows_controls = []
            for t, cnt in summary["counts"].items():
                rows_controls.append(
                    ft.Row([
                        ft.Text(f"• {t}", weight=ft.FontWeight.W_600, expand=True, size=12),
                        ft.Text(f"{cnt} filas", size=12, color=TEXT_MUTED),
                    ])
                )

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.TABLE_VIEW_ROUNDED, color=ft.Colors.BLUE_400),
                    ft.Text("Tablas Remotas en Turso Cloud", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"Total de Tablas: {summary['total_tables']} | Filas Totales: {summary['total_rows']}",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Divider(height=1),
                            *(rows_controls if rows_controls else [
                                ft.Text(
                                    "Aún no hay tablas en Turso Cloud. Usa 'Subir / Sincronizar' para crearlas.",
                                    size=12,
                                    color=TEXT_MUTED,
                                )
                            ]),
                        ],
                        spacing=8,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=420,
                    height=300,
                ),
                actions=[
                    ft.TextButton("Cerrar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                ],
            )
            open_dialog(self.page_ref, dialog)

        turso_cloud_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CLOUD_SYNC_ROUNDED, size=22, color=ft.Colors.CYAN_400),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Turso Cloud & Sincronización Remota (Fase 5)",
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color=TEXT_SECONDARY,
                                    ),
                                    ft.Text(
                                        "Base de datos libSQL en la nube. "
                                        "Credenciales cifradas con AES-256-GCM y salt en profile.json.",
                                        size=12,
                                        color=TEXT_MUTED,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            turso_url_field,
                            turso_token_field,
                        ],
                        spacing=12,
                    ),
                    turso_status_container,
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Probar Conexión",
                                icon=ft.Icons.NETWORK_CHECK_ROUNDED,
                                on_click=test_turso_cloud_connection,
                                bgcolor=ft.Colors.BLUE_GREY_700,
                            ),
                            ft.FilledButton(
                                "Guardar Credenciales Cifradas",
                                icon=ft.Icons.LOCK_ROUNDED,
                                on_click=save_turso_cloud_credentials,
                                bgcolor=BTN_PRIMARY_BG,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(height=1),
                    ft.Text("Replicación y Sincronización de Datos:", size=13, weight=ft.FontWeight.W_600),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Subir / Sincronizar Base Local a Turso Cloud",
                                icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                                on_click=confirm_push_to_cloud,
                                bgcolor=ft.Colors.CYAN_800,
                            ),
                            ft.OutlinedButton(
                                "Descargar de Turso Cloud a Local",
                                icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                                on_click=confirm_pull_from_cloud,
                            ),
                            ft.TextButton(
                                "Inspeccionar Tablas Remotas",
                                icon=ft.Icons.TABLE_VIEW_ROUNDED,
                                on_click=show_remote_tables_dialog,
                            ),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # Configuración y Uso de Inteligencia Artificial (Agnóstico a modelos)
        ai_service = AIService()
        ai_cfg = ai_service.get_config()

        def make_ai_status_badge() -> ft.Container:

            is_active = ai_service.is_configured()
            prov_name = ai_cfg.get("provider", "gemini").capitalize()
            feats = ai_cfg.get("features", {})
            active_feats = [k for k, v in feats.items() if v]
            if is_active:
                status_text = (
                    f"IA Conectada ({prov_name} - {ai_cfg.get('model', '')}) | Usos activos: {len(active_feats)}/6"
                )
                badge_bg = ft.Colors.GREEN_50
                badge_fg = ft.Colors.GREEN_700
                badge_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            else:
                status_text = "IA Desactivada (Ingresa una API Key para habilitar)"
                badge_bg = ft.Colors.BLUE_GREY_50
                badge_fg = ft.Colors.BLUE_GREY_600
                badge_icon = ft.Icons.INFO_OUTLINE_ROUNDED

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(badge_icon, size=16, color=badge_fg),
                        ft.Text(status_text, size=12, weight=ft.FontWeight.W_600, color=badge_fg),
                    ],
                    spacing=6,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                bgcolor=badge_bg,
                border_radius=6,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, badge_fg)),
            )

        ai_status_holder = ft.Container(content=make_ai_status_badge())

        ai_provider_dropdown = ft.Dropdown(
            label="Proveedor de IA *",
            options=[
                ft.dropdown.Option(key="gemini", text="Google Gemini (Recomendado)"),
                ft.dropdown.Option(key="openrouter", text="OpenRouter (Multi-proveedor / OpenAI / Llama)"),
            ],
            value=ai_cfg.get("provider", "gemini"),
            width=280,
        )

        ai_model_field = ft.TextField(
            label="Modelo (LLM) *",
            value=ai_cfg.get("model") or DEFAULT_MODELS.get(ai_provider_dropdown.value, ""),
            hint_text="ej. gemini-2.0-flash o google/gemini-2.0-flash-001",
            expand=True,
        )

        def on_ai_provider_change(e: ft.ControlEvent) -> None:
            chosen = ai_provider_dropdown.value or "gemini"
            ai_model_field.value = DEFAULT_MODELS.get(chosen, "")
            if self.page_ref:
                self.page_ref.update()

        ai_provider_dropdown.on_select = on_ai_provider_change

        ai_api_key_field = ft.TextField(
            label="Clave de API (API Key) *",
            value=ai_cfg.get("api_key", ""),
            password=True,
            can_reveal_password=True,
            hint_text="Pega aquí tu clave (AIzaSy... o sk-or-v1-...)",
            expand=True,
        )

        ai_test_feedback = ft.Text("", size=12, weight=ft.FontWeight.W_500)

        # Switches de Usos Específicos de IA (Fase 6 Granular)
        features_dict = dict(ai_cfg.get("features", {}))

        switch_invoices = ft.Switch(
            label="Extracción de Facturas & DTE SII",
            value=features_dict.get("invoices", True),
        )
        switch_classify_expenses = ft.Switch(
            label="Clasificación Contable de Gastos & Compras",
            value=features_dict.get("classify_expenses", False),
        )
        switch_improve_quotes = ft.Switch(
            label="Redacción Comercial de Cotizaciones & Propuestas",
            value=features_dict.get("improve_quotes", False),
        )
        switch_suggest_descriptions = ft.Switch(
            label="Sugerencia Técnica de Partidas & Alcances (SOW)",
            value=features_dict.get("suggest_descriptions", False),
        )
        switch_summarize_client = ft.Switch(
            label="Resumen Ejecutivo del Historial de Clientes",
            value=features_dict.get("summarize_client", False),
        )
        switch_assist_reports = ft.Switch(
            label="Diagnóstico Ejecutivo en Reportes Financieros",
            value=features_dict.get("assist_reports", False),
        )

        def test_ai_connection(e: ft.ControlEvent) -> None:
            prov = ai_provider_dropdown.value or "gemini"
            key = ai_api_key_field.value.strip() if ai_api_key_field.value else ""
            mdl = ai_model_field.value.strip() if ai_model_field.value else ""

            if not key:
                ai_test_feedback.value = "⚠️ Ingresa una clave de API antes de probar la conexión."
                ai_test_feedback.color = ft.Colors.ORANGE_800
                if self.page_ref:
                    self.page_ref.update()
                return

            ai_test_feedback.value = "⏳ Verificando credenciales..."
            ai_test_feedback.color = ft.Colors.BLUE_GREY_600
            if self.page_ref:
                self.page_ref.update()

            ok, msg = ai_service.test_connection(provider=prov, api_key=key, model=mdl)
            if ok:
                ai_test_feedback.value = f"✅ {msg}"
                ai_test_feedback.color = ft.Colors.GREEN_700
                show_snackbar(self.page_ref, f"¡Conexión con {prov.capitalize()} validada con éxito!")
            else:
                ai_test_feedback.value = f"❌ {msg}"
                ai_test_feedback.color = ft.Colors.RED_700
                show_snackbar(self.page_ref, msg, is_error=True)

            if self.page_ref:
                self.page_ref.update()

        def save_ai_config(e: ft.ControlEvent) -> None:
            prov = ai_provider_dropdown.value or "gemini"
            key = ai_api_key_field.value.strip() if ai_api_key_field.value else ""
            mdl = ai_model_field.value.strip() if ai_model_field.value else ""
            feats = {
                "invoices": switch_invoices.value,
                "classify_expenses": switch_classify_expenses.value,
                "improve_quotes": switch_improve_quotes.value,
                "suggest_descriptions": switch_suggest_descriptions.value,
                "summarize_client": switch_summarize_client.value,
                "assist_reports": switch_assist_reports.value,
            }

            ai_service.save_config(
                provider=prov,
                api_key=key,
                model=mdl,
                features=feats,
            )
            ai_cfg.clear()
            ai_cfg.update(ai_service.get_config())
            ai_status_holder.content = make_ai_status_badge()
            show_snackbar(self.page_ref, "Configuración y permisos granulares de IA guardados.")
            if self.page_ref:
                self.page_ref.update()

        ai_usage_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=24, color=ft.Colors.PURPLE_700),
                                    ft.Text(
                                        "Uso de Inteligencia Artificial (Módulo Agnóstico)",
                                        weight=ft.FontWeight.BOLD,
                                        size=16,
                                        color=TEXT_PRIMARY,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ai_status_holder,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        "py-manager-lite integra Inteligencia Artificial desacoplada del proveedor. "
                        "Puedes utilizar Google Gemini u OpenRouter para potenciar la precisión documental.",
                        size=13,
                        color=TEXT_MUTED,
                    ),
                    ft.Divider(height=1),
                    ft.Text(
                        "Credenciales y Proveedor de LLM",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_SECONDARY,
                    ),
                    ft.Row(
                        controls=[
                            ai_provider_dropdown,
                            ai_model_field,
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        controls=[
                            ai_api_key_field,
                        ],
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                "Probar Conexión",
                                icon=ft.Icons.NETWORK_CHECK_ROUNDED,
                                on_click=test_ai_connection,
                            ),
                            ft.FilledButton(
                                "Guardar Configuración IA",
                                icon=ft.Icons.SAVE_ROUNDED,
                                on_click=save_ai_config,
                                bgcolor=BTN_PRIMARY_BG,
                            ),
                            ai_test_feedback,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1),
                    # Sección destacada: Uso IA (En qué se usará)
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=20, color=ft.Colors.PURPLE_700),
                                        ft.Text(
                                            "Uso IA: ¿En qué se usará la Inteligencia Artificial?",
                                            weight=ft.FontWeight.BOLD,
                                            size=15,
                                            color=TEXT_PRIMARY,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    "Selecciona de manera exclusiva en qué funcionalidades operará el modelo. "
                                    "Si solo deseas usarlo para facturas y ninguna otra función, mantén activa "
                                    "únicamente esa opción.",
                                    size=12,
                                    color=TEXT_MUTED,
                                ),
                                ft.Container(height=4),
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.Row(
                                                controls=[
                                                    switch_invoices,
                                                    ft.Text(
                                                        "(Extrae folios, montos neto/IVA, RUTs y fechas desde PDFs y "
                                                        "XMLs DTE)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                            ft.Row(
                                                controls=[
                                                    switch_classify_expenses,
                                                    ft.Text(
                                                        "(Asigna categorías contables y centros de costo según el "
                                                        "emisor y glosa)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                            ft.Row(
                                                controls=[
                                                    switch_improve_quotes,
                                                    ft.Text(
                                                        "(Perfecciona redacción de observaciones, condiciones "
                                                        "comerciales y propuesta)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                            ft.Row(
                                                controls=[
                                                    switch_suggest_descriptions,
                                                    ft.Text(
                                                        "(Genera especificaciones técnicas y alcances para partidas "
                                                        "de cotización)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                            ft.Row(
                                                controls=[
                                                    switch_summarize_client,
                                                    ft.Text(
                                                        "(Genera briefing ejecutivo con proyectos, volumen histórico "
                                                        "y comportamiento de pago)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                            ft.Row(
                                                controls=[
                                                    switch_assist_reports,
                                                    ft.Text(
                                                        "(Elabora diagnósticos de rentabilidad, proyección tributaria "
                                                        "F29 y alertas)",
                                                        size=11,
                                                        color=TEXT_MUTED,
                                                    ),
                                                ],
                                                spacing=12,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    padding=12,
                                    bgcolor=CARD_ALT_BGCOLOR,
                                    border_radius=6,
                                    border=ft.Border.all(1, BORDER_COLOR),
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding.symmetric(vertical=6),
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # Configuración de Moneda y Formato
        curr_svc = get_currency_service()
        curr_config = curr_svc.get_config()

        preview_pos_text = ft.Text(
            curr_svc.format_amount(1250000.5, curr_config),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_700,
        )
        preview_neg_text = ft.Text(
            curr_svc.format_amount(-45000, curr_config),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.RED_700,
        )

        preset_options = [
            ft.dropdown.Option(key=k, text=v["label"])
            for k, v in CURRENCY_PRESETS.items()
        ]

        preset_dropdown = ft.Dropdown(
            label="Perfil Predefinido de Divisa",
            options=preset_options,
            value=curr_config.get("preset", "CLP"),
            width=320,
            dense=True,
        )

        symbol_field = ft.TextField(
            label="Símbolo",
            value=curr_config.get("symbol", "$"),
            width=100,
            dense=True,
        )

        position_dropdown = ft.Dropdown(
            label="Posición",
            options=[
                ft.dropdown.Option(key="prefix", text="Prefijo (ej: $ 1.000)"),
                ft.dropdown.Option(key="suffix", text="Sufijo (ej: 1.000 UF)"),
            ],
            value=curr_config.get("symbol_position", "prefix"),
            width=180,
            dense=True,
        )

        thousand_sep_dropdown = ft.Dropdown(
            label="Separador Miles",
            options=[
                ft.dropdown.Option(key=".", text=". (Punto - Chile/ES)"),
                ft.dropdown.Option(key=",", text=", (Coma - US/Intl)"),
                ft.dropdown.Option(key=" ", text="  (Espacio)"),
                ft.dropdown.Option(key="'", text="' (Apóstrofe)"),
            ],
            value=curr_config.get("thousand_separator", "."),
            width=170,
            dense=True,
        )

        decimal_sep_dropdown = ft.Dropdown(
            label="Separador Decimal",
            options=[
                ft.dropdown.Option(key=",", text=", (Coma - Chile/ES)"),
                ft.dropdown.Option(key=".", text=". (Punto - US/Intl)"),
            ],
            value=curr_config.get("decimal_separator", ","),
            width=170,
            dense=True,
        )

        decimals_dropdown = ft.Dropdown(
            label="Cant. Decimales",
            options=[
                ft.dropdown.Option(key="0", text="0 (Entero - CLP)"),
                ft.dropdown.Option(key="1", text="1 decimal"),
                ft.dropdown.Option(key="2", text="2 decimales (USD/UF)"),
                ft.dropdown.Option(key="4", text="4 decimales (UF precisión)"),
            ],
            value=str(curr_config.get("decimals", 0)),
            width=170,
            dense=True,
        )

        code_field = ft.TextField(
            label="Divisa (Código ISO)",
            value=curr_config.get("code", "CLP"),
            width=140,
            dense=True,
        )

        show_code_switch = ft.Switch(
            label="Mostrar divisa al final (ej: $ 1.250.000 CLP)",
            value=bool(curr_config.get("show_code", False)),
        )

        def get_current_form_config() -> dict:
            return {
                "preset": preset_dropdown.value or "CUSTOM",
                "code": (code_field.value or "CLP").strip().upper(),
                "symbol": (symbol_field.value or "$").strip(),
                "symbol_position": position_dropdown.value or "prefix",
                "thousand_separator": thousand_sep_dropdown.value or ".",
                "decimal_separator": decimal_sep_dropdown.value or ",",
                "decimals": int(decimals_dropdown.value or "0"),
                "show_code": bool(show_code_switch.value),
            }

        def update_preview() -> None:
            c = get_current_form_config()
            preview_pos_text.value = curr_svc.format_amount(1250000.5, c)
            preview_neg_text.value = curr_svc.format_amount(-45000, c)
            if self.page_ref:
                self.page_ref.update()

        def on_preset_select(e: ft.ControlEvent) -> None:
            pkey = preset_dropdown.value or "CLP"
            if pkey in CURRENCY_PRESETS and pkey != "CUSTOM":
                p = CURRENCY_PRESETS[pkey]
                code_field.value = p["code"]
                symbol_field.value = p["symbol"]
                position_dropdown.value = p["symbol_position"]
                thousand_sep_dropdown.value = p["thousand_separator"]
                decimal_sep_dropdown.value = p["decimal_separator"]
                decimals_dropdown.value = str(p["decimals"])
                show_code_switch.value = p["show_code"]
            update_preview()

        def on_field_change(e: ft.ControlEvent) -> None:
            preset_dropdown.value = "CUSTOM"
            update_preview()

        preset_dropdown.on_select = on_preset_select
        symbol_field.on_change = on_field_change
        position_dropdown.on_select = on_field_change
        thousand_sep_dropdown.on_select = on_field_change
        decimal_sep_dropdown.on_select = on_field_change
        decimals_dropdown.on_select = on_field_change
        code_field.on_change = on_field_change
        show_code_switch.on_change = on_field_change

        def save_currency_settings(e: ft.ControlEvent) -> None:
            cfg = get_current_form_config()
            curr_svc.update_config(cfg)
            update_preview()
            show_snackbar(
                self.page_ref,
                f"Formato de moneda guardado: {cfg['code']} ({cfg['symbol']}). Se aplicará en todo el sistema."
            )

        currency_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=22, color=ft.Colors.GREEN_700),
                            ft.Text(
                                "Formato de Moneda y Divisa del Sistema",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                                color=TEXT_PRIMARY,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Configura el formato monetario estándar (CLP, UF, USD, EUR o personalizado) aplicado a "
                        "todas las vistas, cotizaciones, finanzas y reportes contables.",
                        size=12,
                        color=TEXT_MUTED,
                    ),
                    ft.Divider(height=1),
                    # Selector de preset
                    ft.Row(
                        controls=[
                            preset_dropdown,
                            show_code_switch,
                        ],
                        spacing=20,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # Campos de personalización
                    ft.Row(
                        controls=[
                            code_field,
                            symbol_field,
                            position_dropdown,
                            thousand_sep_dropdown,
                            decimal_sep_dropdown,
                            decimals_dropdown,
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                    # Vista Previa Interactiva en Vivo
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.PREVIEW_ROUNDED, size=18, color=TEXT_SECONDARY),
                                ft.Text("Vista Previa en Vivo:", size=13, weight=ft.FontWeight.BOLD),
                                ft.Container(width=10),
                                ft.Text("Positivo:", size=12, color=TEXT_MUTED),
                                preview_pos_text,
                                ft.Container(width=16),
                                ft.Text("Negativo:", size=12, color=TEXT_MUTED),
                                preview_neg_text,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=12,
                        bgcolor=CARD_ALT_BGCOLOR,
                        border_radius=6,
                        border=ft.Border.all(1, BORDER_COLOR),
                    ),
                    ft.Container(height=4),
                    ft.FilledButton(
                        "Guardar Formato de Moneda",
                        icon=ft.Icons.SAVE_ROUNDED,
                        on_click=save_currency_settings,
                        bgcolor=BTN_PRIMARY_BG,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        # =====================================================================
        # Respaldo, Exportación e Importación de Base de Datos Turso / LibSQL
        # =====================================================================
        backup_service = BackupService()
        db_summary = backup_service.get_database_summary()

        counts_badge_str = " | ".join(
            [f"{k}: {v}" for k, v in db_summary.get("counts", {}).items() if v > 0]
        ) or "Base de datos inicializada"

        import_path_field = ft.TextField(
            label="Ruta del archivo a restaurar (.db, .sql, .zip)",
            hint_text="C:\\...\\turso_backup.db",
            expand=True,
            dense=True,
        )

        restore_configs_switch = ft.Switch(
            label="Restaurar configuraciones de perfil, IA y moneda (si están en el archivo ZIP)",
            value=True,
        )

        preview_card_content = ft.Column(spacing=6)
        preview_container = ft.Container(
            content=preview_card_content,
            padding=12,
            bgcolor=CARD_ALT_BGCOLOR,
            border_radius=6,
            border=ft.Border.all(1, BORDER_COLOR),
            visible=False,
        )

        recent_backups_column = ft.Column(spacing=8)

        def inspect_and_preview(path_str: str) -> None:
            clean_path = path_str.strip()
            if not clean_path:
                preview_container.visible = False
                if self.page_ref:
                    self.page_ref.update()
                return

            insp = backup_service.inspect_backup_file(clean_path)
            preview_card_content.controls.clear()

            if insp.get("valid"):
                b_type = str(insp.get("type", "")).upper()
                c_dict = insp.get("counts", {})
                c_str = " | ".join([f"{k}: {v}" for k, v in c_dict.items()]) if c_dict else "Estructura válida"

                preview_card_content.controls.extend([
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=ft.Colors.GREEN_700),
                            ft.Text(
                                f"Respaldo Válido ({b_type})",
                                weight=ft.FontWeight.BOLD,
                                size=13,
                                color=ft.Colors.GREEN_800,
                            ),
                            ft.Container(width=10),
                            ft.Text(
                                f"Archivo: {insp.get('file_name')} ({insp.get('size_kb')} KB)",
                                size=12,
                                color=TEXT_MUTED,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(f"Contenido detectado: {c_str}", size=11, color=TEXT_SECONDARY),
                ])
                preview_container.border = ft.Border.all(1, ft.Colors.GREEN_300)
                preview_container.bgcolor = ft.Colors.GREEN_50
            else:
                preview_card_content.controls.extend([
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=18, color=ft.Colors.RED_700),
                            ft.Text(
                                "Archivo Incompatible o No Válido",
                                weight=ft.FontWeight.BOLD,
                                size=13,
                                color=ft.Colors.RED_800,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(insp.get("error", "Error desconocido"), size=11, color=ft.Colors.RED_600),
                ])
                preview_container.border = ft.Border.all(1, ft.Colors.RED_300)
                preview_container.bgcolor = ft.Colors.RED_50

            preview_container.visible = True
            if self.page_ref:
                self.page_ref.update()

        import_path_field.on_change = lambda e: inspect_and_preview(import_path_field.value or "")

        def refresh_recent_backups() -> None:
            recent_backups_column.controls.clear()
            backups = backup_service.list_backups()[:5]
            if not backups:
                recent_backups_column.controls.append(
                    ft.Text("No hay respaldos generados aún en documents/backups/.", size=12, color=TEXT_MUTED)
                )
                if self.page_ref:
                    self.page_ref.update()
                return

            rows = []
            for b in backups:
                b_path = b["path"]

                def make_select_handler(path_val: str):
                    def _h(_):
                        import_path_field.value = path_val
                        inspect_and_preview(path_val)
                    return _h

                def make_open_handler(path_val: str):
                    def _h(_):
                        open_document(path_val)
                    return _h

                icon = (
                    ft.Icons.STORAGE_ROUNDED if b["ext"] == ".db"
                    else (ft.Icons.CODE_ROUNDED if b["ext"] == ".sql" else ft.Icons.FOLDER_ZIP_ROUNDED)
                )
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(
                                ft.Row([
                                    ft.Icon(icon, size=16, color=ft.Colors.CYAN_700),
                                    ft.Text(b["name"], size=12, weight=ft.FontWeight.W_500),
                                ], spacing=6)
                            ),
                            ft.DataCell(ft.Text(b["type_label"], size=11)),
                            ft.DataCell(ft.Text(f"{b['size_kb']} KB", size=11)),
                            ft.DataCell(ft.Text(b["created_at"], size=11)),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.RESTORE_PAGE_ROUNDED,
                                        tooltip="Cargar en el selector para restaurar",
                                        icon_size=18,
                                        icon_color=ft.Colors.BLUE_700,
                                        on_click=make_select_handler(b_path),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                        tooltip="Abrir archivo",
                                        icon_size=18,
                                        icon_color=TEXT_MUTED,
                                        on_click=make_open_handler(b_path),
                                    ),
                                ], spacing=2)
                            ),
                        ]
                    )
                )

            recent_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Archivo", weight=ft.FontWeight.BOLD, size=12)),
                    ft.DataColumn(ft.Text("Formato", weight=ft.FontWeight.BOLD, size=12)),
                    ft.DataColumn(ft.Text("Tamaño", weight=ft.FontWeight.BOLD, size=12)),
                    ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=12)),
                    ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12)),
                ],
                rows=rows,
                heading_row_height=36,
                data_row_min_height=36,
                data_row_max_height=42,
                column_spacing=16,
            )
            recent_backups_column.controls.append(recent_table)
            if self.page_ref:
                self.page_ref.update()

        # Handlers de exportación
        def export_turso_db_click(e: ft.ControlEvent) -> None:
            def _worker(cb: Callable[[float, Optional[str], Optional[str]], None]) -> str:
                return backup_service.export_turso_db(progress_callback=cb)

            def _done(out_path: str) -> None:
                fname = os.path.basename(out_path)
                show_snackbar(self.page_ref, f"Base de datos Turso (.db) exportada: {fname}")
                refresh_recent_backups()

            run_operation_with_progress(
                page=self.page_ref,
                title="Exportar Base de Datos (.db)",
                worker_fn=_worker,
                on_success=_done,
                initial_status="Comprobando...",
                initial_log="Iniciando exportación atómica de base de datos Turso (.db)...",
                icon_color=ft.Colors.INDIGO_600,
                success_message="¡Base de datos exportada con éxito!",
            )

        def export_sql_dump_click(e: ft.ControlEvent) -> None:
            def _worker(cb: Callable[[float, Optional[str], Optional[str]], None]) -> str:
                return backup_service.export_turso_sql_dump(progress_callback=cb)

            def _done(out_path: str) -> None:
                fname = os.path.basename(out_path)
                show_snackbar(self.page_ref, f"Volcado SQL para Turso Cloud (.sql) generado: {fname}")
                refresh_recent_backups()

            run_operation_with_progress(
                page=self.page_ref,
                title="Generar Volcado SQL (.sql)",
                worker_fn=_worker,
                on_success=_done,
                initial_status="Comprobando...",
                initial_log="Iniciando generación de volcado SQL para Turso Cloud...",
                icon_color=ft.Colors.TEAL_600,
                success_message="¡Volcado SQL generado con éxito!",
            )

        def export_zip_pkg_click(e: ft.ControlEvent) -> None:
            def _worker(cb: Callable[[float, Optional[str], Optional[str]], None]) -> str:
                return backup_service.export_full_backup_package(progress_callback=cb)

            def _done(out_path: str) -> None:
                fname = os.path.basename(out_path)
                show_snackbar(self.page_ref, f"Paquete completo (.zip) exportado: {fname}")
                refresh_recent_backups()

            run_operation_with_progress(
                page=self.page_ref,
                title="Exportar Paquete Completo (.zip)",
                worker_fn=_worker,
                on_success=_done,
                initial_status="Comprobando...",
                initial_log="Iniciando empaquetado integral del sistema...",
                icon_color=ft.Colors.BLUE_600,
                success_message="¡Paquete completo exportado con éxito!",
            )

        def open_backups_folder_click(e: ft.ControlEvent) -> None:
            opened = open_document(str(BACKUPS_DIR))
            if not opened:
                show_snackbar(self.page_ref, f"Carpeta de respaldos: {BACKUPS_DIR}")

        def on_import_file_picked(picked_path: str) -> None:
            import_path_field.value = picked_path
            inspect_and_preview(picked_path)

        def browse_backup_file(e: ft.ControlEvent) -> None:
            self.trigger_file_picker(
                on_import_file_picked,
                allowed_extensions=["db", "sqlite", "libsql", "sql", "zip"]
            )

        def confirm_restore(e: ft.ControlEvent) -> None:
            path_val = import_path_field.value.strip() if import_path_field.value else ""
            if not path_val:
                show_snackbar(self.page_ref, "Selecciona o ingresa la ruta del archivo a restaurar.", is_error=True)
                return

            insp = backup_service.inspect_backup_file(path_val)
            if not insp.get("valid"):
                show_snackbar(self.page_ref, f"El archivo no es válido: {insp.get('error')}", is_error=True)
                return

            dialog = None

            def execute_restore(ev: ft.ControlEvent) -> None:
                close_dialog(self.page_ref, dialog)

                def _restore_worker(cb: Callable[[float, Optional[str], Optional[str]], None]) -> Dict[str, Any]:
                    return backup_service.import_backup(
                        path_val,
                        restore_configs=restore_configs_switch.value,
                        progress_callback=cb,
                    )

                def _on_restore_done(res: Dict[str, Any]) -> None:
                    counts = res.get("counts", {})
                    c_summary = ", ".join([f"{k}: {v}" for k, v in counts.items()]) if counts else "Tablas cargadas"
                    show_snackbar(
                        self.page_ref,
                        f"¡Base de datos restaurada con éxito! ({c_summary}). "
                        f"Respaldo preventivo guardado en safety/."
                    )
                    if self.on_demo_data_loaded:
                        self.on_demo_data_loaded()
                    else:
                        self.build_ui()

                run_operation_with_progress(
                    page=self.page_ref,
                    title="Restaurar Base de Datos",
                    worker_fn=_restore_worker,
                    on_success=_on_restore_done,
                    initial_status="Comprobando...",
                    initial_log=f"Iniciando restauración desde {os.path.basename(path_val)}...",
                    icon_color=ft.Colors.DEEP_ORANGE_600,
                    success_message="¡Base de datos restaurada con éxito!",
                )

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.DEEP_ORANGE_700),
                    ft.Text("Confirmar Restauración de Base de Datos", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Se sobreescribirá la base de datos actual con la información del archivo:",
                                size=13,
                            ),
                            ft.Text(f"• Archivo: {os.path.basename(path_val)}", weight=ft.FontWeight.BOLD, size=13),
                            ft.Text(f"• Tipo: {insp.get('type', '').upper()} ({insp.get('size_kb')} KB)", size=12),
                            ft.Container(height=4),
                            ft.Text(
                                "SEGURIDAD: Se creará automáticamente un respaldo previo de seguridad en "
                                "'tmp/profile/backups_safety/' antes de aplicar los cambios.",
                                size=11,
                                color=ft.Colors.GREEN_800,
                            ),
                        ],
                        spacing=8,
                        tight=True,
                    ),
                    width=460,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: close_dialog(self.page_ref, dialog)),
                    ft.FilledButton(
                        "Sí, Restaurar Base de Datos",
                        on_click=execute_restore,
                        bgcolor=ft.Colors.DEEP_ORANGE_700,
                    ),
                ],
            )
            open_dialog(self.page_ref, dialog)

        # Inicializar lista de respaldos recientes
        refresh_recent_backups()

        backup_migration_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CLOUD_SYNC_ROUNDED, size=22, color=ft.Colors.CYAN_700),
                            ft.Text(
                                "Copia de Seguridad y Migración Turso / Base de Datos",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                                color=TEXT_PRIMARY,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Exporta e importa toda la base de datos en formato Turso / LibSQL (.db y .sql) para "
                        "respaldos locales o migración a Turso Cloud, evitando la pérdida de información comercial.",
                        size=12,
                        color=TEXT_MUTED,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=ft.Colors.GREEN_700),
                                ft.Text(
                                    f"BD Activa: turso_manager.db ({db_summary.get('size_kb', 0)} KB) | "
                                    f"Integridad: {db_summary.get('integrity', 'OK')}",
                                    size=12,
                                    weight=ft.FontWeight.W_500,
                                    color=TEXT_PRIMARY,
                                ),
                                ft.Container(width=10),
                                ft.Text(
                                    f"Datos: {counts_badge_str}",
                                    size=11,
                                    color=TEXT_MUTED,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=10,
                        bgcolor=CARD_ALT_BGCOLOR,
                        border_radius=6,
                        border=ft.Border.all(1, BORDER_COLOR),
                    ),
                    ft.Divider(height=1),
                    ft.Text("1. Exportar Todo (Generar Respaldo)", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Exporta la base de datos completa. El formato .db es directamente compatible con Turso CLI "
                        "(turso db create --from-file) y el volcado .sql es compatible con 'turso db shell'.",
                        size=12,
                        color=TEXT_MUTED,
                    ),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Exportar Base de Datos Turso (.db)",
                                icon=ft.Icons.STORAGE_ROUNDED,
                                on_click=export_turso_db_click,
                                bgcolor=ft.Colors.CYAN_800,
                            ),
                            ft.FilledButton(
                                "Exportar Volcado SQL Cloud (.sql)",
                                icon=ft.Icons.CODE_ROUNDED,
                                on_click=export_sql_dump_click,
                                bgcolor=ft.Colors.TEAL_800,
                            ),
                            ft.OutlinedButton(
                                "Exportar Paquete Completo (.zip)",
                                icon=ft.Icons.FOLDER_ZIP_ROUNDED,
                                on_click=export_zip_pkg_click,
                            ),
                            ft.TextButton(
                                "Abrir Carpeta de Respaldos",
                                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                on_click=open_backups_folder_click,
                            ),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                    ft.Divider(height=1),
                    ft.Text("2. Importar y Restaurar Todo", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Selecciona un archivo de respaldo (.db, .sql o .zip) para restaurar la información. "
                        "El sistema creará automáticamente una copia de seguridad preventiva antes de proceder.",
                        size=12,
                        color=TEXT_MUTED,
                    ),
                    ft.Row(
                        controls=[
                            import_path_field,
                            ft.FilledButton(
                                "Examinar...",
                                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                on_click=browse_backup_file,
                                bgcolor=BTN_PRIMARY_BG,
                            ),
                        ],
                        spacing=10,
                    ),
                    preview_container,
                    restore_configs_switch,
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Restaurar Base de Datos Ahora",
                                icon=ft.Icons.RESTORE_ROUNDED,
                                on_click=confirm_restore,
                                bgcolor=ft.Colors.DEEP_ORANGE_700,
                            ),
                        ],
                    ),
                    ft.Divider(height=1),
                    ft.Text("3. Respaldos Recientes Generados", weight=ft.FontWeight.BOLD, size=13),
                    recent_backups_column,
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=CARD_BGCOLOR,
            border_radius=8,
            border=ft.Border.all(1, BORDER_COLOR),
        )

        header = SectionHeader(
            title="Configuración",
            subtitle="Parámetros técnicos, moneda del sistema, perfil seguro y estado general",
        )

        self.content = ft.ListView(
            controls=[
                header,
                ft.Container(height=16),
                currency_card,
                ft.Container(height=16),
                backup_migration_card,
                ft.Container(height=16),
                turso_cloud_card,
                ft.Container(height=16),
                ai_usage_card,
                ft.Container(height=16),
                profile_security_card,

                ft.Container(height=16),
                info_card,
                ft.Container(height=16),
                poc_notes_card,
                ft.Container(height=16),
                demo_card,
            ],
            spacing=0,
            expand=True,
        )
