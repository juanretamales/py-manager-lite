import flet as ft
from typing import Optional
from app.constant import (
    CARD_BGCOLOR,
    BORDER_COLOR,
    SHADOW_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_HINT,
    STATUS_THEMES,
    STATUS_LABELS,
    SNACKBAR_SUCCESS_BG,
    SNACKBAR_ERROR_BG,
    SNACKBAR_TEXT_COLOR,
    METRIC_QUOTE_COLOR,
)


def show_snackbar(page: ft.Page, message: str, is_error: bool = False) -> None:
    """Display a feedback SnackBar on the page."""
    sb = ft.SnackBar(
        content=ft.Text(message, color=SNACKBAR_TEXT_COLOR, weight=ft.FontWeight.W_500),
        bgcolor=SNACKBAR_ERROR_BG if is_error else SNACKBAR_SUCCESS_BG,
        open=True
    )
    page.overlay.append(sb)
    page.update()


def open_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    """Add and open a modal dialog on the page."""
    if dialog not in page.overlay:
        page.overlay.append(dialog)
    dialog.open = True
    page.update()


def close_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    """Close an open modal dialog."""
    dialog.open = False
    page.update()


def StatCard(
    title: str,
    value: str,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    icon_color: str = METRIC_QUOTE_COLOR,
    accent_border: Optional[str] = None,
) -> ft.Container:
    """Reusable metric card component for dashboards and financial overviews."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(title, size=13, weight=ft.FontWeight.W_500, color=TEXT_MUTED),
                        ft.Icon(icon, color=icon_color, size=20) if icon else ft.Container(),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Text(subtitle, size=11, color=TEXT_HINT) if subtitle else ft.Container(),
            ],
            spacing=4,
            tight=True,
        ),
        padding=16,
        border_radius=8,
        bgcolor=CARD_BGCOLOR,
        border=ft.Border.all(1, BORDER_COLOR),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=3,
            color=SHADOW_COLOR,
            offset=ft.Offset(0, 1)
        ),
        expand=True,
    )


def StatusChip(status: str) -> ft.Container:
    """Render a clean status pill/badge with semantic colors."""
    status_upper = (status or "").upper()

    text_color, bg_color = STATUS_THEMES.get(status_upper, (TEXT_MUTED, CARD_BGCOLOR))
    label = STATUS_LABELS.get(status_upper, status_upper)

    return ft.Container(
        content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=text_color),
        bgcolor=bg_color,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, text_color)),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def SectionHeader(
    title: str,
    subtitle: Optional[str] = None,
    action_button: Optional[ft.Control] = None
) -> ft.Row:
    """Header row with title, description and optional primary action button."""
    return ft.Row(
        controls=[
            ft.Column(
                controls=[
                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text(subtitle, size=12, color=TEXT_MUTED) if subtitle else ft.Container(),
                ],
                spacing=2,
            ),
            action_button if action_button else ft.Container(),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
