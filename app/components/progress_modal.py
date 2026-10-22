"""Modal de Progreso y Registro en Tiempo Real para Operaciones de Datos y Archivos.

# DECISIÓN DE ARQUITECTURA Y UX:
Al ejecutar operaciones prolongadas de base de datos (carga de datos demo, volcados SQL,
restauración atómica de respaldos, migración masiva de almacenamiento a carpetas locales/nube
o sincronización con Turso Cloud), la interfaz Flet se congela si se ejecutan en el hilo principal.
Este componente proporciona un diálogo modal flotante ejecutado en hilo secundario (daemon thread),
impidiendo clics conflictivos accidentales, mostrando un anillo giratorio (ProgressRing),
una barra porcentual dinámica, frases de empatía de usuario ("Cargando para mejorar la experiencia",
"Afinando para el perfil del usuario", "Comprobando") y una consola de registro (live log)
con timestamps en tiempo real.
"""

from typing import Optional, Callable, Any
import threading
import time
from datetime import datetime
import flet as ft

from app.constant import (
    CARD_BGCOLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    BTN_PRIMARY_BG,
    BTN_PRIMARY_TEXT,
)


class OperationProgressModal:
    """Ventana modal de diálogo con barra de progreso, porcentaje y consola de registro en vivo."""

    def __init__(
        self,
        page: ft.Page,
        title: str,
        initial_status: str = "Comprobando...",
        initial_log: Optional[str] = None,
        icon: Optional[str] = None,
        icon_color: Optional[str] = None,
    ) -> None:
        self.page = page
        self.title_text = title
        self.icon = icon
        self.is_completed = False
        self.has_error = False

        # 1. Cabecera con Icono animado y porcentaje
        self.spinner = ft.ProgressRing(
            width=26,
            height=26,
            stroke_width=3,
            color=icon_color or ft.Colors.INDIGO_600,
        )
        self.status_icon_container = ft.Container(content=self.spinner)

        self.title_label = ft.Text(
            self.title_text,
            size=16,
            weight=ft.FontWeight.BOLD,
            color=TEXT_PRIMARY,
        )

        self.percent_badge = ft.Container(
            content=ft.Text(
                "0%",
                size=12,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.INDIGO_700,
            ),
            bgcolor=ft.Colors.INDIGO_50,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.INDIGO_200),
        )

        # 2. Frase de empatía y estado hero
        self.hero_status = ft.Text(
            initial_status,
            size=13,
            weight=ft.FontWeight.W_500,
            color=TEXT_SECONDARY,
        )

        # 3. Barra de progreso visual
        self.progress_bar = ft.ProgressBar(
            value=0.0,
            height=8,
            border_radius=4,
            color=ft.Colors.INDIGO_600,
            bgcolor=ft.Colors.INDIGO_50,
        )

        # 4. Consola de registros en vivo (Live Terminal)
        self.log_lines_column = ft.Column(
            spacing=3,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.terminal_container = ft.Container(
            content=self.log_lines_column,
            bgcolor=ft.Colors.BLUE_GREY_900,
            border_radius=6,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_700),
            padding=10,
            height=130,
        )

        # 5. Botones de acción inferior y botón cerrar en cabecera
        self.close_icon_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=20,
            tooltip="Operación en curso...",
            disabled=True,
            on_click=self._on_action_click,
        )

        self.action_button = ft.FilledButton(
            "Procesando...",
            disabled=True,
            bgcolor=BTN_PRIMARY_BG,
            color=BTN_PRIMARY_TEXT,
            on_click=self._on_action_click,
        )
        self.footer_hint = ft.Text(
            "Operación en ejecución. No cierres la ventana.",
            size=11,
            color=TEXT_MUTED,
            italic=True,
        )

        self.on_close_callback: Optional[Callable[[], None]] = None

        # Ensamblar diálogo
        self.dialog = ft.AlertDialog(
            modal=True,
            on_dismiss=self._on_dismiss,
            title=ft.Row(
                controls=[
                    self.status_icon_container,
                    self.title_label,
                    ft.Container(expand=True),
                    self.percent_badge,
                    self.close_icon_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.hero_status,
                        self.progress_bar,
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=14, color=TEXT_MUTED),
                                ft.Text(
                                    "Registro de Operaciones en Vivo:",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXT_MUTED,
                                ),
                            ],
                            spacing=4,
                        ),
                        self.terminal_container,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=520,
            ),
            actions=[
                self.footer_hint,
                self.action_button,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            shape=ft.RoundedRectangleBorder(radius=10),
            bgcolor=CARD_BGCOLOR,
        )

        if initial_log:
            self.add_log(initial_log)

    def open(self) -> None:
        """Añade y muestra el modal de progreso en la página."""
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def close(self) -> None:
        """Cierra el diálogo modal."""
        self.dialog.open = False
        try:
            self.page.update()
        except Exception:
            pass

    def add_log(self, text: str, is_highlight: bool = False, is_error: bool = False) -> None:
        """Añade una línea de texto timestamped a la consola de log."""
        ts = datetime.now().strftime("%H:%M:%S")
        if is_error:
            color = ft.Colors.RED_300
        elif is_highlight:
            color = ft.Colors.LIGHT_BLUE_300
        else:
            color = ft.Colors.BLUE_GREY_200

        line = ft.Text(
            f"[{ts}] {text}",
            size=11,
            color=color,
            font_family="monospace",
            no_wrap=False,
        )
        self.log_lines_column.controls.append(line)
        # Mantener las últimas 60 líneas
        if len(self.log_lines_column.controls) > 60:
            self.log_lines_column.controls.pop(0)

    def update_progress(
        self,
        progress: float,
        status: Optional[str] = None,
        log_message: Optional[str] = None,
    ) -> None:
        """Actualiza el porcentaje (0.0 a 1.0), frase de estado y opcionalmente añade un log."""
        clamped = max(0.0, min(1.0, progress))
        self.progress_bar.value = clamped

        pct_val = int(clamped * 100)
        self.percent_badge.content = ft.Text(
            f"{pct_val}%",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_700 if pct_val == 100 else ft.Colors.INDIGO_700,
        )
        self.percent_badge.bgcolor = ft.Colors.GREEN_50 if pct_val == 100 else ft.Colors.INDIGO_50
        self.percent_badge.border = ft.Border.all(
            1, ft.Colors.GREEN_300 if pct_val == 100 else ft.Colors.INDIGO_200
        )

        if status:
            self.hero_status.value = status

        if log_message:
            self.add_log(log_message)

        try:
            self.page.update()
        except Exception:
            pass

    def complete(
        self,
        final_message: str = "¡Operación completada exitosamente!",
        final_log: Optional[str] = None,
        button_text: str = "Continuar",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Marca la tarea como completada, cambia el icono a verde y habilita el botón de continuar."""
        self.is_completed = True
        self.on_close_callback = on_close
        self.update_progress(1.0, status=final_message, log_message=final_log)

        # Reemplazar spinner por icono de check verde
        self.status_icon_container.content = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED,
            color=ft.Colors.GREEN_600,
            size=28,
        )
        self.progress_bar.color = ft.Colors.GREEN_600
        self.footer_hint.value = "Completado sin errores."
        self.footer_hint.color = ft.Colors.GREEN_700
        self.action_button.text = button_text
        self.action_button.disabled = False
        self.close_icon_button.disabled = False
        self.close_icon_button.tooltip = "Cerrar ventana"
        self.dialog.modal = False

        try:
            self.page.update()
        except Exception:
            pass

    def set_error(
        self,
        error_message: str,
        error_details: Optional[str] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Presenta visualmente una alerta de error y habilita el botón para cerrar."""
        self.has_error = True
        self.on_close_callback = on_close

        self.status_icon_container.content = ft.Icon(
            ft.Icons.ERROR_ROUNDED,
            color=ft.Colors.RED_600,
            size=28,
        )
        self.hero_status.value = f"Error: {error_message}"
        self.hero_status.color = ft.Colors.RED_700
        self.progress_bar.color = ft.Colors.RED_600
        self.percent_badge.content = ft.Text("ERROR", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700)
        self.percent_badge.bgcolor = ft.Colors.RED_50
        self.percent_badge.border = ft.Border.all(1, ft.Colors.RED_300)

        self.add_log(f"FALLO: {error_message}", is_error=True)
        if error_details:
            self.add_log(str(error_details), is_error=True)

        self.footer_hint.value = "La operación fue interrumpida."
        self.footer_hint.color = ft.Colors.RED_700
        self.action_button.text = "Cerrar"
        self.action_button.disabled = False
        self.close_icon_button.disabled = False
        self.close_icon_button.tooltip = "Cerrar ventana"
        self.dialog.modal = False

        try:
            self.page.update()
        except Exception:
            pass

    def _on_action_click(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Handler al pulsar el botón de continuar, cerrar o el icono X."""
        self.close()
        self._trigger_close_callback()

    def _on_dismiss(self, e: ft.ControlEvent) -> None:
        """Handler cuando el diálogo es descartado por ESC o clic externo."""
        self._trigger_close_callback()

    def _trigger_close_callback(self) -> None:
        """Ejecuta el callback de cierre exactamente una vez."""
        if self.on_close_callback:
            cb = self.on_close_callback
            self.on_close_callback = None
            cb()


def run_operation_with_progress(
    page: ft.Page,
    title: str,
    worker_fn: Callable[[Callable[[float, Optional[str], Optional[str]], None]], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    initial_status: str = "Comprobando...",
    initial_log: Optional[str] = None,
    icon: Optional[str] = None,
    icon_color: Optional[str] = None,
    success_message: str = "¡Operación completada exitosamente!",
    auto_close_delay: Optional[float] = None,
) -> None:
    """Ejecuta una función trabajadora en un hilo en segundo plano con modal de progreso en tiempo real.

    Args:
        page: Referencia a la página activa de Flet.
        title: Título descriptivo en el modal.
        worker_fn: Función que recibe `progress_callback(percent, status, log)` y ejecuta la tarea.
        on_success: Callback ejecutado cuando el usuario hace clic en continuar tras el éxito.
        on_error: Callback en caso de excepción no controlada.
        initial_status: Frase inicial amigable de progreso.
        initial_log: Primer mensaje para la consola en vivo.
        icon: Opcional, identificador de icono para la operación.
        icon_color: Color del ProgressRing.
        success_message: Frase de estado mostrada al llegar al 100%.
        auto_close_delay: Opcional, segundos para autocerrar tras éxito sin forzar clic.
    """
    modal = OperationProgressModal(
        page=page,
        title=title,
        initial_status=initial_status,
        initial_log=initial_log,
        icon=icon,
        icon_color=icon_color,
    )
    modal.open()

    def _thread_target() -> None:
        try:
            def reporter(progress: float, status: Optional[str] = None, log: Optional[str] = None) -> None:
                modal.update_progress(progress=progress, status=status, log_message=log)

            result = worker_fn(reporter)

            def handle_success_close() -> None:
                if on_success:
                    on_success(result)

            modal.complete(
                final_message=success_message,
                on_close=handle_success_close,
            )

            # Cierre automático opcional si se configuró delay
            if auto_close_delay and auto_close_delay > 0:
                time.sleep(auto_close_delay)
                if modal.dialog.open:
                    modal.close()
                    handle_success_close()

        except Exception as ex:
            import traceback
            tb = traceback.format_exc()
            err_obj = ex
            err_msg = str(ex)

            def handle_error_close() -> None:
                if on_error:
                    on_error(err_obj)

            modal.set_error(
                error_message=err_msg,
                error_details=tb,
                on_close=handle_error_close,
            )

    worker_thread = threading.Thread(target=_thread_target, daemon=True)
    worker_thread.start()
