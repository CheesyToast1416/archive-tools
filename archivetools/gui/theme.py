from __future__ import annotations

from typing import TypedDict

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeColors(TypedDict):
    """All color tokens used across the application theme."""

    is_dark: bool
    # Surfaces
    window: str
    surface: str
    surface2: str
    border: str
    # Text
    text: str
    text_secondary: str
    text_dim: str
    # Accent
    accent: str
    accent_hover: str
    accent_disabled_bg: str
    # Sidebar
    sidebar_bg: str
    sidebar_selected: str
    sidebar_hover: str
    sidebar_title: str
    sidebar_text: str
    # Warnings
    warn_bg: str
    warn_text: str
    # Drop zone
    drop_zone_hover_bg: str
    # Cards
    card_bg: str
    card_border: str
    card_hover_bg: str


# ── Color dictionaries ────────────────────────────────────────────────────────

LIGHT: ThemeColors = {
    "is_dark": False,
    # Surfaces
    "window": "#F5F5F5",
    "surface": "#F2F2F7",
    "surface2": "#E5E5EA",
    "border": "#D1D1D6",
    # Text
    "text": "#1C1C1E",
    "text_secondary": "#6E6E73",
    "text_dim": "#AEAEB2",
    # Accent (Apple blue)
    "accent": "#007AFF",
    "accent_hover": "#0056CC",
    "accent_disabled_bg": "#AEAEB2",
    # Sidebar
    "sidebar_bg": "#E8E8EA",
    "sidebar_selected": "#C8C8CA",
    "sidebar_hover": "#DEDEDF",
    "sidebar_title": "#888888",
    "sidebar_text": "#1C1C1E",
    # Warnings
    "warn_bg": "#FFF3CD",
    "warn_text": "#664D03",
    # Drop zone (hover only; idle uses surface)
    "drop_zone_hover_bg": "#EFF5FF",
    # Cards (Recent panel)
    "card_bg": "#FFFFFF",
    "card_border": "#E5E5EA",
    "card_hover_bg": "#F2F2F7",
}

DARK: dict = {
    "is_dark": True,
    # Surfaces
    "window": "#1C1C1E",
    "surface": "#2C2C2E",
    "surface2": "#3A3A3C",
    "border": "#48484A",
    # Text
    "text": "#EBEBF5",
    "text_secondary": "#AEAEB2",
    "text_dim": "#636366",
    # Accent (Apple dark-mode blue)
    "accent": "#0A84FF",
    "accent_hover": "#409CFF",
    "accent_disabled_bg": "#48484A",
    # Sidebar
    "sidebar_bg": "#111113",
    "sidebar_selected": "#3A3A3C",
    "sidebar_hover": "#2C2C2E",
    "sidebar_title": "#636366",
    "sidebar_text": "#EBEBF5",
    # Warnings
    "warn_bg": "#3D2B00",
    "warn_text": "#FFD60A",
    # Drop zone (hover only; idle uses surface)
    "drop_zone_hover_bg": "#1A2C3E",
    # Cards (Recent panel)
    "card_bg": "#2C2C2E",
    "card_border": "#3A3A3C",
    "card_hover_bg": "#3A3A3C",
}


# ── Palette factories ─────────────────────────────────────────────────────────


def _make_dark_palette() -> QPalette:
    p = QPalette()
    c = DARK

    def _q(hex_color: str) -> QColor:
        return QColor(hex_color)

    p.setColor(QPalette.ColorRole.Window, _q(c["window"]))
    p.setColor(QPalette.ColorRole.WindowText, _q(c["text"]))
    p.setColor(QPalette.ColorRole.Base, _q("#111113"))
    p.setColor(QPalette.ColorRole.AlternateBase, _q(c["surface"]))
    p.setColor(QPalette.ColorRole.Button, _q(c["surface2"]))
    p.setColor(QPalette.ColorRole.ButtonText, _q(c["text"]))
    p.setColor(QPalette.ColorRole.Text, _q(c["text"]))
    p.setColor(QPalette.ColorRole.BrightText, _q("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Mid, _q(c["border"]))
    p.setColor(QPalette.ColorRole.Dark, _q(c["surface2"]))
    p.setColor(QPalette.ColorRole.Light, _q(c["border"]))
    p.setColor(QPalette.ColorRole.Midlight, _q(c["surface"]))
    p.setColor(QPalette.ColorRole.Shadow, _q("#09090B"))
    p.setColor(QPalette.ColorRole.Highlight, _q(c["accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, _q("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Link, _q(c["accent"]))
    p.setColor(QPalette.ColorRole.LinkVisited, _q("#BF5AF2"))
    p.setColor(QPalette.ColorRole.ToolTipBase, _q(c["surface"]))
    p.setColor(QPalette.ColorRole.ToolTipText, _q(c["text"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, _q(c["text_dim"]))

    # Disabled group
    for role, hex_val in [
        (QPalette.ColorRole.WindowText, c["text_dim"]),
        (QPalette.ColorRole.Text, c["text_dim"]),
        (QPalette.ColorRole.ButtonText, c["text_dim"]),
    ]:
        p.setColor(QPalette.ColorGroup.Disabled, role, _q(hex_val))

    return p


def _make_light_palette() -> QPalette:
    """Explicit Fusion-compatible light palette (safe even on dark-themed systems)."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
    p.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Mid, QColor(160, 160, 160))
    p.setColor(QPalette.ColorRole.Dark, QColor(160, 160, 160))
    p.setColor(QPalette.ColorRole.Shadow, QColor(105, 105, 105))
    p.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 255))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, QColor(0, 102, 204))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(160, 160, 160))
    p.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(120, 120, 120),
    )
    p.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120)
    )
    p.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(120, 120, 120),
    )
    return p


# ── Public API ────────────────────────────────────────────────────────────────


def _detect_system() -> str:
    try:
        from PySide6.QtCore import Qt

        if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    return "light"


def resolve(theme_name: str) -> dict:
    """Return the LIGHT or DARK color dict for a setting value."""
    if theme_name == "dark":
        return DARK
    if theme_name == "light":
        return LIGHT
    return DARK if _detect_system() == "dark" else LIGHT


def build_stylesheet(c: dict) -> str:
    """Return a flat global stylesheet that adapts to the given color dict."""
    a = c["accent"]
    # Hover/pressed overlays — palette-neutral semi-transparent tints
    if c["is_dark"]:
        hover = "rgba(255,255,255,18)"
        pressed = "rgba(255,255,255,30)"
    else:
        hover = "rgba(0,0,0,12)"
        pressed = "rgba(0,0,0,22)"
    # SVG data URIs require '#' encoded as '%23'
    arrow = c["text_secondary"].replace("#", "%23")
    _svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'>"
        f"<polyline points='1,1 5,5 9,1' fill='none' stroke='{arrow}'"
        f" stroke-width='1.5' stroke-linecap='round'"
        f" stroke-linejoin='round'/></svg>"
    )
    down_arrow_url = f'url("data:image/svg+xml,{_svg}")'

    return f"""
/* ── Buttons ──────────────────────────────────────────────────────── */
QPushButton {{
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    background-color: transparent;
}}
QPushButton:hover    {{ background-color: {hover};   }}
QPushButton:pressed  {{ background-color: {pressed}; }}
QPushButton:checked  {{ background-color: {pressed}; }}
QPushButton:disabled {{ color: palette(disabled, button-text); }}

QToolButton {{
    border: none;
    border-radius: 4px;
    padding: 3px 5px;
    background-color: transparent;
}}
QToolButton:hover    {{ background-color: {hover};   }}
QToolButton:pressed  {{ background-color: {pressed}; }}
QToolButton:checked  {{ background-color: {pressed}; }}

/* ── Text inputs ──────────────────────────────────────────────────── */
QLineEdit {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    padding: 4px 8px;
    background-color: palette(base);
    selection-background-color: {a};
}}
QLineEdit:focus {{ border-color: {a}; }}
QLineEdit:disabled {{ color: palette(disabled, text); }}

QPlainTextEdit {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    background-color: palette(base);
}}

/* ── Combo box ────────────────────────────────────────────────────── */
QComboBox {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    padding: 4px 8px 4px 8px;
    background-color: palette(button);
}}
QComboBox:focus {{ border-color: {a}; }}
QComboBox::drop-down {{
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: {down_arrow_url};
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid palette(mid);
    border-radius: 4px;
    selection-background-color: {a};
    outline: none;
}}

/* ── Item views ───────────────────────────────────────────────────── */
QTreeWidget, QListWidget {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    outline: none;
}}
QTableWidget {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    gridline-color: palette(mid);
    outline: none;
}}
QHeaderView::section {{
    background-color: palette(window);
    border: none;
    border-bottom: 1px solid palette(mid);
    padding: 4px 6px;
    font-weight: 600;
}}

/* ── Scroll bars ──────────────────────────────────────────────────── */
QScrollBar:vertical {{
    width: 8px; background: transparent; margin: 2px 2px 2px 0;
}}
QScrollBar::handle:vertical {{
    background: palette(mid); border-radius: 4px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 8px; background: transparent; margin: 0 0 2px 2px;
}}
QScrollBar::handle:horizontal {{
    background: palette(mid); border-radius: 4px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Progress bar ─────────────────────────────────────────────────── */
QProgressBar {{
    border: none;
    border-radius: 2px;
    background-color: palette(mid);
}}
QProgressBar::chunk {{
    background-color: {a};
    border-radius: 2px;
}}

/* ── Splitter ─────────────────────────────────────────────────────── */
QSplitter::handle           {{ background-color: palette(mid); }}
QSplitter::handle:horizontal {{ width:  1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ── Group box (Settings dialog) ──────────────────────────────────── */
QGroupBox {{
    border: 1px solid palette(mid);
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    font-weight: 600;
}}

/* ── Tab widget (Settings dialog) ─────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid palette(mid);
    border-radius: 5px;
}}
QTabBar::tab {{
    border: none;
    padding: 6px 14px;
    border-bottom: 2px solid transparent;
    background: transparent;
}}
QTabBar::tab:selected {{
    border-bottom-color: {a};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ background: {hover}; }}
"""


def apply_theme(app: QApplication, theme_name: str) -> dict:
    """
    Set the application palette + flat global stylesheet.
    Call before showing any widgets, and again whenever the theme changes.
    """
    colors = resolve(theme_name)
    app.setPalette(_make_dark_palette() if colors["is_dark"] else _make_light_palette())
    app.setStyleSheet(build_stylesheet(colors))
    return colors
