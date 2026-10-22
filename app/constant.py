"""
py-manager-lite: Configuración centralizada de diseño, temas, colores, iconos y assets.
Modifica este archivo para personalizar completamente la apariencia de la aplicación.
"""

import flet as ft
from app.core.config import APP_TITLE, APP_VERSION

# ==============================================================================
# 1. INFORMACIÓN Y BRANDING
# ==============================================================================
APP_NAME = APP_TITLE
APP_VER = APP_VERSION
APP_ICON = ft.Icons.AUTO_GRAPH_ROUNDED
APP_ICON_COLOR = ft.Colors.LIGHT_BLUE_300

# ==============================================================================
# 2. FONDOS GENERALES (BACKGROUNDS)
# ==============================================================================
PAGE_BGCOLOR = ft.Colors.BLUE_GREY_50         # Fondo principal de la ventana
CARD_BGCOLOR = ft.Colors.WHITE                # Fondo de tarjetas y paneles
CARD_ALT_BGCOLOR = ft.Colors.BLUE_GREY_50     # Fondo de cajas secundarias/resúmenes
SIDEBAR_BGCOLOR = ft.Colors.BLUE_GREY_900     # Fondo del menú lateral
TABLE_BGCOLOR = ft.Colors.WHITE               # Fondo de tablas

# ==============================================================================
# 3. BORDES, SOMBRAS Y DIVISORES
# ==============================================================================
BORDER_COLOR = ft.Colors.BLUE_GREY_100        # Borde estándar para tarjetas y tablas
BORDER_LIGHT_COLOR = ft.Colors.BLUE_GREY_50   # Borde suave
DIVIDER_COLOR = ft.Colors.BLUE_GREY_200       # Divisor entre menú y contenido
SIDEBAR_DIVIDER_COLOR = ft.Colors.BLUE_GREY_800  # Divisor interno del sidebar
SHADOW_COLOR = ft.Colors.with_opacity(0.04, ft.Colors.BLACK)

# ==============================================================================
# 4. TIPOGRAFÍA Y COLORES DE TEXTO
# ==============================================================================
TEXT_PRIMARY = ft.Colors.BLUE_GREY_900        # Títulos y valores destacados
TEXT_SECONDARY = ft.Colors.BLUE_GREY_800      # Subtítulos y etiquetas de formulario
TEXT_MUTED = ft.Colors.BLUE_GREY_500          # Textos descriptivos secundarios
TEXT_HINT = ft.Colors.BLUE_GREY_400           # Textos de ayuda / placeholders
TEXT_LIGHT = ft.Colors.WHITE                  # Textos sobre fondos oscuros

SIDEBAR_TEXT_PRIMARY = ft.Colors.WHITE        # Título principal en sidebar
SIDEBAR_TEXT_MUTED = ft.Colors.BLUE_GREY_300  # Versión y subtítulos en sidebar
SIDEBAR_STATUS_ACTIVE = ft.Colors.GREEN_400   # Indicador de estado en sidebar

# Navegación del Menú Sidebar (Items y Destinos)
SIDEBAR_TEXT_SELECTED = ft.Colors.WHITE          # Color de texto del item activo/seleccionado
SIDEBAR_TEXT_UNSELECTED = ft.Colors.BLUE_GREY    # Color de texto de items inactivos
SIDEBAR_ICON_SELECTED_COLOR = ft.Colors.LIGHT_BLUE_300  # Color de icono del item seleccionado
SIDEBAR_ICON_COLOR = ft.Colors.BLUE_GREY_300     # Color de icono de items inactivos
SIDEBAR_INDICATOR_COLOR = ft.Colors.BLUE_GREY_800  # Fondo/pill resaltado del item seleccionado

# ==============================================================================
# 5. BOTONES Y ACCIONES (BUTTONS & ACTIONS)
# ==============================================================================
BTN_PRIMARY_BG = ft.Colors.BLUE_GREY_900      # Botón principal estándar (guardar, crear)
BTN_PRIMARY_TEXT = ft.Colors.WHITE
BTN_ACCENT_BG = ft.Colors.BLUE_600            # Botón de acción destacada (e.g. Canvas, nuevo ítem)
BTN_SUCCESS_BG = ft.Colors.GREEN_700          # Botones de confirmación positiva / pagos
BTN_DANGER_ICON = ft.Colors.RED_400           # Iconos de eliminar/remover
BTN_DEMO_BG = ft.Colors.INDIGO_700            # Botón de carga de datos demo

# ==============================================================================
# 6. MÉTRICAS E INDICADORES (DASHBOARD)
# ==============================================================================
METRIC_QUOTE_COLOR = ft.Colors.BLUE_600       # Icono cotizaciones
METRIC_PROJECT_COLOR = ft.Colors.INDIGO_600   # Icono proyectos
METRIC_CLIENT_COLOR = ft.Colors.TEAL_600      # Icono clientes
METRIC_INVOICE_UP_COLOR = ft.Colors.GREEN_600    # Icono facturación emitida (ventas)
METRIC_INVOICE_DOWN_COLOR = ft.Colors.BLUE_GREY_600  # Facturación recibida (gastos)
METRIC_PENDING_PAY_COLOR = ft.Colors.RED_600  # Pendiente de pago
METRIC_PENDING_COLLECT_COLOR = ft.Colors.ORANGE_600  # Pendiente de cobro
METRIC_ALERT_COLOR = ft.Colors.AMBER_700      # Alertas / documentos faltantes
METRIC_SUCCESS_COLOR = ft.Colors.GREEN_600    # OK / sin alertas

# Balance operacional
BALANCE_POSITIVE_COLOR = ft.Colors.GREEN_700  # Saldo positivo
BALANCE_NEGATIVE_COLOR = ft.Colors.RED_700    # Saldo negativo

# ==============================================================================
# 7. ESTADOS SEMÁFORO (STATUS CHIPS & BADGES)
# Cada estado define tupla: (Color de texto, Color de fondo)
# ==============================================================================
STATUS_THEMES = {
    # Éxito / Completado / Pagado
    "ACCEPTED": (ft.Colors.GREEN_700, ft.Colors.GREEN_50),
    "PAID": (ft.Colors.GREEN_700, ft.Colors.GREEN_50),
    "COMPLETED": (ft.Colors.GREEN_700, ft.Colors.GREEN_50),

    # En proceso / Activo / Enviada
    "ACTIVE": (ft.Colors.BLUE_700, ft.Colors.BLUE_50),
    "SENT": (ft.Colors.BLUE_700, ft.Colors.BLUE_50),

    # Atención / Parcial / Negociación
    "PARTIAL": (ft.Colors.AMBER_800, ft.Colors.AMBER_50),
    "NEGOTIATION": (ft.Colors.AMBER_800, ft.Colors.AMBER_50),
    "PAUSED": (ft.Colors.AMBER_800, ft.Colors.AMBER_50),
    "PENDING": (ft.Colors.ORANGE_800, ft.Colors.ORANGE_50),

    # Planificado / Inicial
    "PLANNED": (ft.Colors.PURPLE_700, ft.Colors.PURPLE_50),
    "DRAFT": (ft.Colors.BLUE_GREY_700, ft.Colors.BLUE_GREY_50),

    # Alerta / Vencido / Cancelado / Rechazado / Eliminado
    "REJECTED": (ft.Colors.RED_700, ft.Colors.RED_50),
    "EXPIRED": (ft.Colors.RED_700, ft.Colors.RED_50),
    "OVERDUE": (ft.Colors.RED_800, ft.Colors.RED_50),
    "CANCELLED": (ft.Colors.RED_700, ft.Colors.RED_50),
    "DELETED": (ft.Colors.GREY_700, ft.Colors.GREY_100),
    "ANNULLED": (ft.Colors.PURPLE_800, ft.Colors.PURPLE_50),
    "CREDIT_NOTE": (ft.Colors.DEEP_PURPLE_700, ft.Colors.DEEP_PURPLE_50),
}

# Etiquetas en español para los estados
STATUS_LABELS = {
    "DRAFT": "Borrador",
    "SENT": "Enviada",
    "NEGOTIATION": "Negociación",
    "ACCEPTED": "Aceptada",
    "REJECTED": "Rechazada",
    "EXPIRED": "Expirada",
    "PLANNED": "Planificado",
    "ACTIVE": "Activo",
    "PAUSED": "En Pausa",
    "COMPLETED": "Completado",
    "CANCELLED": "Cancelado",
    "PENDING": "Pendiente",
    "PARTIAL": "Parcial",
    "PAID": "Pagado",
    "OVERDUE": "Vencido",
    "DELETED": "Eliminada",
    "ANNULLED": "Anulada con NC",
    "CREDIT_NOTE": "Nota de Crédito",
}

# Badges de Facturas y Documentos Tributarios
INVOICE_ISSUED_BG = ft.Colors.GREEN_700
INVOICE_RECEIVED_BG = ft.Colors.BLUE_GREY_600
INVOICE_CREDIT_NOTE_BG = ft.Colors.PURPLE_700

# ==============================================================================
# 8. MENSAJES Y NOTIFICACIONES (SNACKBARS)
# ==============================================================================
SNACKBAR_SUCCESS_BG = ft.Colors.GREEN_700
SNACKBAR_ERROR_BG = ft.Colors.RED_700
SNACKBAR_TEXT_COLOR = ft.Colors.WHITE

# ==============================================================================
# 9. ASSETS E IMÁGENES
# ==============================================================================
LOGO_IMAGE_PATH = None                        # Ruta a logo opcional (ej: "assets/logo.png")
DEFAULT_AVATAR_ICON = ft.Icons.ACCOUNT_CIRCLE_ROUNDED
