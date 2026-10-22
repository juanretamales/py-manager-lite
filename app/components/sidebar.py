import flet as ft
from typing import Callable, Optional
from app.constant import (
    APP_NAME,
    APP_VER,
    APP_ICON,
    APP_ICON_COLOR,
    SIDEBAR_BGCOLOR,
    SIDEBAR_DIVIDER_COLOR,
    SIDEBAR_TEXT_PRIMARY,
    SIDEBAR_TEXT_MUTED,
    SIDEBAR_STATUS_ACTIVE,
    SIDEBAR_TEXT_SELECTED,
    SIDEBAR_TEXT_UNSELECTED,
    SIDEBAR_ICON_SELECTED_COLOR,
    SIDEBAR_ICON_COLOR,
    SIDEBAR_INDICATOR_COLOR,
)


def create_sidebar(
    selected_index: int,
    on_destination_change: Callable[[int], None],
    user_name: str = "Admin",
    on_lock: Optional[Callable[[], None]] = None,
) -> ft.Container:
    """Creates the modern left sidebar navigation."""

    def handle_change(e: ft.ControlEvent) -> None:
        on_destination_change(e.control.selected_index)

    rail = ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=72,
        min_extended_width=210,
        extended=True,
        bgcolor=SIDEBAR_BGCOLOR,
        indicator_color=SIDEBAR_INDICATOR_COLOR,
        selected_label_text_style=ft.TextStyle(
            color=SIDEBAR_TEXT_SELECTED,
            weight=ft.FontWeight.W_600,
            size=13,
        ),
        unselected_label_text_style=ft.TextStyle(
            color=SIDEBAR_TEXT_UNSELECTED,
            size=13,
        ),
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.DASHBOARD_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(ft.Icons.DASHBOARD_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20),
                label="Inicio",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.BUSINESS_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(ft.Icons.BUSINESS_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20),
                label="Mi Empresa",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.PEOPLE_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(ft.Icons.PEOPLE_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20),
                label="Clientes",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(
                    ft.Icons.DESCRIPTION_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20
                ),
                label="Cotizaciones",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.FOLDER_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(
                    ft.Icons.FOLDER_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20
                ),
                label="Proyectos",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(
                    ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20
                ),
                label="Finanzas",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.FILE_DOWNLOAD_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(
                    ft.Icons.FILE_DOWNLOAD_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20
                ),
                label="Reportes",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icon(ft.Icons.SETTINGS_OUTLINED, color=SIDEBAR_ICON_COLOR, size=20),
                selected_icon=ft.Icon(
                    ft.Icons.SETTINGS_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=20
                ),
                label="Configuración",
            ),
        ],
        on_change=handle_change,
    )

    header = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(APP_ICON, color=APP_ICON_COLOR, size=24),
                        ft.Text(APP_NAME, weight=ft.FontWeight.BOLD, size=15, color=SIDEBAR_TEXT_PRIMARY),
                    ],
                    spacing=8,
                ),
                ft.Container(
                    content=ft.Text(f"v{APP_VER}", size=10, color=SIDEBAR_TEXT_MUTED),
                    padding=ft.Padding.only(left=32),
                )
            ],
            spacing=2,
        ),
        padding=ft.Padding.only(left=16, right=16, top=20, bottom=16),
    )

    user_row = ft.Row(
        controls=[
            ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, color=SIDEBAR_ICON_SELECTED_COLOR, size=18),
            ft.Text(user_name, size=12, weight=ft.FontWeight.W_600, color=SIDEBAR_TEXT_PRIMARY, expand=True),
        ],
        spacing=6,
    )
    if on_lock:
        user_row.controls.append(
            ft.IconButton(
                icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
                icon_color=SIDEBAR_TEXT_MUTED,
                icon_size=16,
                tooltip="Bloquear sesión",
                on_click=lambda _: on_lock(),
            )
        )

    footer = ft.Container(
        content=ft.Column(
            controls=[
                user_row,
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.STORAGE_ROUNDED, color=SIDEBAR_STATUS_ACTIVE, size=12),
                        ft.Text("Turso/LibSQL (profile/)", size=10, color=SIDEBAR_TEXT_MUTED),
                    ],
                    spacing=6,
                ),
            ],
            spacing=4,
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                header,
                ft.Divider(height=1, color=SIDEBAR_DIVIDER_COLOR),
                ft.Container(content=rail, expand=True),
                ft.Divider(height=1, color=SIDEBAR_DIVIDER_COLOR),
                footer,
            ],
            spacing=0,
        ),
        width=210,
        bgcolor=SIDEBAR_BGCOLOR,
    )
