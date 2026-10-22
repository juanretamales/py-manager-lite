import sys
from pathlib import Path

# Ensure project root and _MEIPASS are in sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    if sys._MEIPASS not in sys.path:
        sys.path.insert(0, sys._MEIPASS)

import flet as ft  # noqa: E402
from app.core.config import APP_TITLE, APP_VERSION  # noqa: E402
from app.constant import PAGE_BGCOLOR, DIVIDER_COLOR  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.components.sidebar import create_sidebar  # noqa: E402
from app.views.dashboard_view import DashboardView  # noqa: E402
from app.views.company_view import CompanyView  # noqa: E402
from app.views.clients_view import ClientsView  # noqa: E402
from app.views.quotes_view import QuotesView  # noqa: E402
from app.views.projects_view import ProjectsView  # noqa: E402
from app.views.finances_view import FinancesView  # noqa: E402
from app.views.exports_view import ExportsView  # noqa: E402
from app.views.settings_view import SettingsView  # noqa: E402
from app.views.auth_view import AuthView  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


def main(page: ft.Page) -> None:
    # Page setup
    page.title = f"{APP_TITLE} v{APP_VERSION} - Gestión Comercial y Financiera"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAGE_BGCOLOR
    page.padding = 0
    page.spacing = 0

    auth_service = AuthService()

    # Content container for main shell
    content_area = ft.Container(expand=True)
    current_tab = 0

    def get_current_user_name() -> str:
        info = auth_service.get_profile_info()
        return info.get("user_name", "Admin") if info else "Admin"

    def lock_app() -> None:
        """Bloquea la aplicación y retorna a la pantalla de PIN/Contraseña."""
        page.clean()
        auth_view = AuthView(
            auth_service=auth_service,
            on_authenticated=unlock_app,
            page_ref=page
        )
        page.add(auth_view.build())
        page.update()

    def navigate_to(index: int) -> None:
        nonlocal current_tab
        current_tab = index

        if index == 0:
            content_area.content = DashboardView(page, on_navigate_tab=navigate_to)
        elif index == 1:
            content_area.content = CompanyView(page)
        elif index == 2:
            content_area.content = ClientsView(page)
        elif index == 3:
            content_area.content = QuotesView(page, on_project_created=lambda: navigate_to(4))
        elif index == 4:
            content_area.content = ProjectsView(page)
        elif index == 5:
            content_area.content = FinancesView(page, on_navigate_tab=navigate_to)
        elif index == 6:
            content_area.content = ExportsView(page)
        elif index == 7:
            content_area.content = SettingsView(page, on_demo_data_loaded=lambda: navigate_to(0))

        # Re-render sidebar with updated active index and user profile
        sidebar_slot.content = create_sidebar(
            current_tab,
            navigate_to,
            user_name=get_current_user_name(),
            on_lock=lock_app,
        )
        page.update()

    sidebar_slot = ft.Container()

    def unlock_app() -> None:
        """Carga la interfaz principal tras autenticación exitosa."""
        page.clean()
        sidebar_slot.content = create_sidebar(
            0,
            navigate_to,
            user_name=get_current_user_name(),
            on_lock=lock_app,
        )
        content_area.content = DashboardView(page, on_navigate_tab=navigate_to)

        layout = ft.Row(
            controls=[
                sidebar_slot,
                ft.VerticalDivider(width=1, color=DIVIDER_COLOR),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        page.add(layout)
        page.update()

    # DECISIÓN DE ARQUITECTURA: Verificación de sesión al arranque; si no existe perfil o está bloqueado,
    # se muestra la vista de autenticación (registro de perfil inicial o desbloqueo por PIN).
    lock_app()


if __name__ == "__main__":
    init_db()
    ft.run(main)
