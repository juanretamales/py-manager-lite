"""Vista de Autenticación, Registro Inicial y Desbloqueo del Sistema.

Controla el flujo de acceso seguro a py-manager-lite mediante Contraseña Maestra y PIN rápido,
garantizando la persistencia del perfil y la base de datos en la carpeta profile.
"""

from typing import Callable, Optional
import flet as ft
from app.core.config import DEFAULT_DOCUMENTS_DIR
from app.services.auth_service import AuthService
from app.constant import (
    APP_NAME,
    CARD_BGCOLOR,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    BTN_PRIMARY_BG,
    BTN_SUCCESS_BG,
    METRIC_SUCCESS_COLOR,
)


class AuthView:
    """Gestiona la pantalla de autenticación inicial (registro) o desbloqueo por PIN/contraseña."""

    def __init__(
        self,
        auth_service: AuthService,
        on_authenticated: Callable[[], None],
        page_ref: Optional[ft.Page] = None,
    ) -> None:
        self.auth_service = auth_service
        self.on_authenticated = on_authenticated
        self.page_ref = page_ref
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.active_file_target = None

    def on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Callback al seleccionar carpeta mediante FilePicker."""
        picked = e.path or (e.files[0].path if e.files else None)
        if picked:
            if callable(self.active_file_target):
                self.active_file_target(picked)
            elif isinstance(self.active_file_target, ft.TextField):
                self.active_file_target.value = picked
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
            except Exception:
                pass

        if self.page_ref:
            self.page_ref.run_task(_pick)

    def build(self) -> ft.Control:
        """Construye y retorna el control visual según si el perfil ya existe o debe crearse."""
        is_configured = self.auth_service.is_profile_configured()
        if not is_configured:
            return self._build_register_screen()
        return self._build_login_screen()

    def _build_register_screen(self) -> ft.Control:
        """Pantalla de primer inicio para configurar el perfil de usuario y credenciales."""
        user_name_field = ft.TextField(
            label="Nombre de Usuario / Administrador *",
            prefix_icon=ft.Icons.PERSON_ROUNDED,
            autofocus=True,
            expand=True,
        )
        company_name_field = ft.TextField(
            label="Nombre de tu Empresa / Negocio (opcional)",
            prefix_icon=ft.Icons.BUSINESS_ROUNDED,
            expand=True,
        )
        password_field = ft.TextField(
            label="Contraseña Maestra (mínimo 6 caracteres) *",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_ROUNDED,
            expand=True,
        )
        password_confirm_field = ft.TextField(
            label="Confirmar Contraseña Maestra *",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
            expand=True,
        )
        pin_field = ft.TextField(
            label="PIN de Desbloqueo Rápido (4 a 6 dígitos numéricos) *",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.PIN_ROUNDED,
            max_length=6,
            expand=True,
        )
        default_storage = str(DEFAULT_DOCUMENTS_DIR)
        storage_path_field = ft.TextField(
            label="Carpeta de Almacenamiento de Archivos (Local / Nube) *",
            value=default_storage,
            prefix_icon=ft.Icons.FOLDER_SPECIAL_ROUNDED,
            hint_text="C:\\ruta\\a\\carpeta",
            expand=True,
        )
        storage_row = ft.Row(
            controls=[
                storage_path_field,
                ft.OutlinedButton(
                    "Examinar...",
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    on_click=lambda _: self.trigger_directory_picker(storage_path_field),
                ),
            ],
            spacing=10,
        )
        error_text = ft.Text("", color=ft.Colors.RED_400, size=13, weight=ft.FontWeight.W_500)

        def handle_register(e: ft.ControlEvent) -> None:
            uname = user_name_field.value.strip() if user_name_field.value else ""
            cname = company_name_field.value.strip() if company_name_field.value else ""
            pwd = password_field.value.strip() if password_field.value else ""
            pwd_conf = password_confirm_field.value.strip() if password_confirm_field.value else ""
            pin = pin_field.value.strip() if pin_field.value else ""
            st_path = storage_path_field.value.strip() if storage_path_field.value else default_storage

            if not uname:
                error_text.value = "Ingresa un nombre de usuario o administrador."
                if self.page_ref:
                    self.page_ref.update()
                return

            if len(pwd) < 6:
                error_text.value = "La contraseña maestra debe tener al menos 6 caracteres."
                if self.page_ref:
                    self.page_ref.update()
                return

            if pwd != pwd_conf:
                error_text.value = "Las contraseñas maestras no coinciden."
                if self.page_ref:
                    self.page_ref.update()
                return

            if not (pin.isdigit() and 4 <= len(pin) <= 6):
                error_text.value = "El PIN debe ser numérico y contener entre 4 y 6 dígitos."
                if self.page_ref:
                    self.page_ref.update()
                return

            # DECISIÓN DE NEGOCIO: Al crear el perfil se genera la persistencia en tmp/profile/profile.json
            self.auth_service.create_profile(
                user_name=uname,
                company_name=cname,
                password=pwd,
                pin=pin,
                storage_path=st_path,
            )
            self.on_authenticated()

        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SECURITY_ROUNDED, size=38, color=METRIC_SUCCESS_COLOR),
                        ft.Column(
                            controls=[
                                ft.Text(f"Bienvenido a {APP_NAME}", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    "Configura tu perfil seguro para desbloquear el sistema y Turso DB",
                                    size=13,
                                    color=TEXT_MUTED,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Divider(color=BORDER_COLOR),
                user_name_field,
                company_name_field,
                ft.Row(controls=[password_field, password_confirm_field], spacing=12),
                pin_field,
                storage_row,
                ft.Text(
                    "Tus facturas, cotizaciones, pagos y respaldos se organizarán aquí. "
                    "Puedes seleccionar una carpeta en la nube (Google Drive, OneDrive, etc.).",
                    size=11,
                    color=TEXT_MUTED,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=TEXT_MUTED),
                            ft.Text(
                                "La base de datos y tus credenciales residen en tmp/profile/ (portátil y seguro).",
                                size=12,
                                color=TEXT_MUTED,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=4),
                ),
                error_text,
                ft.FilledButton(
                    "Crear Perfil e Ingresar",
                    icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                    on_click=handle_register,
                    bgcolor=BTN_PRIMARY_BG,
                    height=46,
                ),
            ],
            spacing=14,
            tight=True,
        )

        return ft.Container(
            content=ft.Container(
                content=card_content,
                width=580,
                bgcolor=CARD_BGCOLOR,
                border=ft.Border.all(1, BORDER_COLOR),
                border_radius=12,
                padding=28,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
        )

    def _build_login_screen(self) -> ft.Control:
        """Pantalla de desbloqueo rápido con PIN numérico o Contraseña Maestra."""
        profile = self.auth_service.get_profile_info() or {}
        user_name = profile.get("user_name", "Usuario")
        company_name = profile.get("company_name", "")

        pin_field = ft.TextField(
            label="PIN de Desbloqueo (4-6 dígitos)",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.PIN_ROUNDED,
            text_align=ft.TextAlign.CENTER,
            text_size=18,
            max_length=6,
            autofocus=True,
            expand=True,
        )

        pwd_field = ft.TextField(
            label="Contraseña Maestra",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.KEY_ROUNDED,
            expand=True,
        )

        error_text = ft.Text("", color=ft.Colors.RED_400, size=13, weight=ft.FontWeight.W_500)

        # DECISIÓN DE ARQUITECTURA: Por defecto se ofrece el PIN por rapidez operativa,
        # con opción inmediata de alternar a contraseña maestra si el usuario lo prefiere.
        active_mode = ["PIN"]  # "PIN" o "PASSWORD"
        input_container = ft.Container(content=pin_field)
        switch_btn = ft.TextButton("Ingresar con Contraseña Maestra")

        def handle_unlock(e: ft.ControlEvent) -> None:
            if active_mode[0] == "PIN":
                pin_val = pin_field.value.strip() if pin_field.value else ""
                if not pin_val:
                    error_text.value = "Por favor ingresa tu PIN."
                    if self.page_ref:
                        self.page_ref.update()
                    return

                if self.auth_service.verify_pin(pin_val):
                    self.on_authenticated()
                else:
                    error_text.value = "PIN incorrecto. Intenta nuevamente."
                    if self.page_ref:
                        self.page_ref.update()
            else:
                pwd_val = pwd_field.value.strip() if pwd_field.value else ""
                if not pwd_val:
                    error_text.value = "Por favor ingresa tu Contraseña Maestra."
                    if self.page_ref:
                        self.page_ref.update()
                    return

                if self.auth_service.verify_password(pwd_val):
                    self.on_authenticated()
                else:
                    error_text.value = "Contraseña maestra incorrecta."
                    if self.page_ref:
                        self.page_ref.update()

        pin_field.on_submit = handle_unlock
        pwd_field.on_submit = handle_unlock

        def toggle_mode(e: ft.ControlEvent) -> None:
            error_text.value = ""
            if active_mode[0] == "PIN":
                active_mode[0] = "PASSWORD"
                input_container.content = pwd_field
                switch_btn.text = "Ingresar con PIN Rápido"
            else:
                active_mode[0] = "PIN"
                input_container.content = pin_field
                switch_btn.text = "Ingresar con Contraseña Maestra"
            if self.page_ref:
                self.page_ref.update()

        switch_btn.on_click = toggle_mode

        greeting_subtitle = f"Empresa: {company_name}" if company_name else "Sistema de Gestión y Finanzas"

        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LOCK_PERSON_ROUNDED, size=40, color=TEXT_PRIMARY),
                        ft.Column(
                            controls=[
                                ft.Text(f"Hola, {user_name} 👋", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(greeting_subtitle, size=13, color=TEXT_MUTED),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Divider(color=BORDER_COLOR),
                input_container,
                error_text,
                ft.FilledButton(
                    "Desbloquear Sistema",
                    icon=ft.Icons.LOCK_OPEN_ROUNDED,
                    on_click=handle_unlock,
                    bgcolor=BTN_SUCCESS_BG,
                    height=46,
                ),
                ft.Row(
                    controls=[switch_btn],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=16,
            tight=True,
        )

        return ft.Container(
            content=ft.Container(
                content=card_content,
                width=460,
                bgcolor=CARD_BGCOLOR,
                border=ft.Border.all(1, BORDER_COLOR),
                border_radius=12,
                padding=32,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
        )
