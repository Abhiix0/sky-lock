"""Unified dark theme for SkyLock GUI.

All colour constants, palette configuration, and global stylesheets are centralized here.
Individual widgets should import colour constants from this module rather than hard-code values.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ============================================================================
# Base Palette Colours (dark theme foundation)
# ============================================================================

# Background colours
WINDOW_BG = QColor("#111827")  # Main window background
BASE_BG = QColor("#0B1220")  # Input fields, table cells
ALT_BASE_BG = QColor("#1F2937")  # Alternate row background
DARK_BG = QColor("#090D16")  # Camera view letterbox

# Text colours
TEXT_PRIMARY = QColor("#E5E7EB")  # Main text
TEXT_SECONDARY = QColor("#9CA3AF")  # Secondary/disabled text
TEXT_TERTIARY = QColor("#6B7280")  # Placeholders, hints

# Accent colours
HIGHLIGHT_BG = QColor("#2563EB")  # Selection highlight
HIGHLIGHT_TEXT = QColor("#FFFFFF")  # Text on highlighted bg

# Border colours
BORDER_NORMAL = QColor("#374151")  # Standard borders
BORDER_SUBTLE = QColor("#1F2937")  # Subtle dividers


# ============================================================================
# State Colours (for TrackState visualization)
# ============================================================================

STATE_SEARCH_PRIMARY = QColor("#3B82F6")  # Blue
STATE_SEARCH_BG = QColor("#1E3A8A")
STATE_SEARCH_TEXT = QColor("#93C5FD")

STATE_ACQUIRE_PRIMARY = QColor("#F59E0B")  # Amber
STATE_ACQUIRE_BG = QColor("#78350F")
STATE_ACQUIRE_TEXT = QColor("#FDE68A")

STATE_TRACK_PRIMARY = QColor("#10B981")  # Emerald
STATE_TRACK_BG = QColor("#064E3B")
STATE_TRACK_TEXT = QColor("#6EE7B7")

STATE_LOST_PRIMARY = QColor("#F43F5E")  # Rose
STATE_LOST_BG = QColor("#881337")
STATE_LOST_TEXT = QColor("#FECDD3")

STATE_REACQUIRE_PRIMARY = QColor("#F97316")  # Orange
STATE_REACQUIRE_BG = QColor("#7C2D12")
STATE_REACQUIRE_TEXT = QColor("#FED7AA")

STATE_DEFAULT_PRIMARY = BORDER_NORMAL


# ============================================================================
# Verdict Colours (for Benchmark panel)
# ============================================================================

VERDICT_PASS_BG = QColor("#065F46")  # Dark green
VERDICT_FAIL_BG = QColor("#991B1B")  # Dark red
VERDICT_INDETERMINATE_BG = QColor("#92400E")  # Dark amber
VERDICT_NOT_RUN_BG = QColor("#374151")  # Gray
VERDICT_UNKNOWN_BG = QColor("#1F2937")  # Darker gray
VERDICT_TEXT = QColor("#FFFFFF")  # White text on verdict backgrounds


# ============================================================================
# UI Element Colours
# ============================================================================

# Buttons
BUTTON_START_BG = QColor("#065F46")  # Green
BUTTON_STOP_BG = QColor("#991B1B")  # Red
BUTTON_DISABLED_BG = QColor("#6B7280")  # Gray
BUTTON_DISABLED_TEXT = TEXT_SECONDARY

# Status indicators
STATUS_SUCCESS = QColor("#10B981")  # Green
STATUS_ERROR = QColor("#EF4444")  # Red
STATUS_WARNING = QColor("#F59E0B")  # Amber

# Overlay drawing colours (camera view)
OVERLAY_BORESIGHT = QColor(147, 197, 253, 200)  # Light blue, translucent
OVERLAY_DETECTION = QColor(251, 191, 36, 230)  # Amber/gold, bright
OVERLAY_GATE = QColor(96, 165, 250, 180)  # Blue, translucent
OVERLAY_ESTIMATE = QColor(52, 211, 153, 200)  # Emerald, translucent
OVERLAY_GT = QColor(244, 63, 94, 240)  # Rose, nearly opaque
OVERLAY_GT_TEXT = QColor(244, 63, 94, 220)  # Rose, for GT label
OVERLAY_HUD_TEXT = TEXT_PRIMARY
OVERLAY_COORD_TEXT = QColor("#93C5FD")  # Light blue
OVERLAY_LEGEND_TEXT = TEXT_SECONDARY


# ============================================================================
# Global Stylesheet
# ============================================================================

GLOBAL_STYLESHEET = """
QGroupBox {
    border: 1px solid #374151;
    border-radius: 4px;
    margin-top: 0.5em;
    padding-top: 0.75em;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #9CA3AF;
}

QPushButton:disabled {
    background-color: #6B7280;
    color: #9CA3AF;
}

QTableWidget {
    gridline-color: #374151;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QTableWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #1F2937;
    color: #E5E7EB;
    padding: 4px;
    border: 1px solid #374151;
    font-weight: bold;
}

QToolTip {
    background-color: #1F2937;
    color: #E5E7EB;
    border: 1px solid #374151;
    padding: 4px;
}

QScrollBar:vertical {
    background: #111827;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #374151;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #4B5563;
}

QScrollBar:horizontal {
    background: #111827;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: #374151;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background: #4B5563;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
}

QTabWidget::pane {
    border: 1px solid #374151;
    border-top: none;
}

QTabBar::tab {
    background: #1F2937;
    color: #9CA3AF;
    padding: 6px 12px;
    border: 1px solid #374151;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #111827;
    color: #E5E7EB;
}

QTabBar::tab:hover:!selected {
    background: #374151;
}
"""


# ============================================================================
# Theme Application
# ============================================================================

def apply_theme(app: QApplication) -> None:
    """Apply the unified dark theme to the application.

    Sets Fusion style, dark palette, and global stylesheet.
    Should be called once during application startup.
    """
    app.setStyle("Fusion")

    palette = QPalette()

    # Base colours
    palette.setColor(QPalette.ColorRole.Window, WINDOW_BG)
    palette.setColor(QPalette.ColorRole.WindowText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Base, BASE_BG)
    palette.setColor(QPalette.ColorRole.AlternateBase, ALT_BASE_BG)
    palette.setColor(QPalette.ColorRole.ToolTipBase, ALT_BASE_BG)
    palette.setColor(QPalette.ColorRole.ToolTipText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Text, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Button, ALT_BASE_BG)
    palette.setColor(QPalette.ColorRole.ButtonText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.BrightText, HIGHLIGHT_TEXT)

    # Highlight colours
    palette.setColor(QPalette.ColorRole.Highlight, HIGHLIGHT_BG)
    palette.setColor(QPalette.ColorRole.HighlightedText, HIGHLIGHT_TEXT)

    # Disabled state
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, TEXT_SECONDARY)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, TEXT_SECONDARY)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, TEXT_SECONDARY)

    # Link colours
    palette.setColor(QPalette.ColorRole.Link, HIGHLIGHT_BG)
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#7C3AED"))

    app.setPalette(palette)
    app.setStyleSheet(GLOBAL_STYLESHEET)


__all__ = (
    # Base palette
    "WINDOW_BG",
    "BASE_BG",
    "ALT_BASE_BG",
    "DARK_BG",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TEXT_TERTIARY",
    "HIGHLIGHT_BG",
    "HIGHLIGHT_TEXT",
    "BORDER_NORMAL",
    "BORDER_SUBTLE",
    # State colours
    "STATE_SEARCH_PRIMARY",
    "STATE_SEARCH_BG",
    "STATE_SEARCH_TEXT",
    "STATE_ACQUIRE_PRIMARY",
    "STATE_ACQUIRE_BG",
    "STATE_ACQUIRE_TEXT",
    "STATE_TRACK_PRIMARY",
    "STATE_TRACK_BG",
    "STATE_TRACK_TEXT",
    "STATE_LOST_PRIMARY",
    "STATE_LOST_BG",
    "STATE_LOST_TEXT",
    "STATE_REACQUIRE_PRIMARY",
    "STATE_REACQUIRE_BG",
    "STATE_REACQUIRE_TEXT",
    "STATE_DEFAULT_PRIMARY",
    # Verdict colours
    "VERDICT_PASS_BG",
    "VERDICT_FAIL_BG",
    "VERDICT_INDETERMINATE_BG",
    "VERDICT_NOT_RUN_BG",
    "VERDICT_UNKNOWN_BG",
    "VERDICT_TEXT",
    # UI element colours
    "BUTTON_START_BG",
    "BUTTON_STOP_BG",
    "BUTTON_DISABLED_BG",
    "BUTTON_DISABLED_TEXT",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_WARNING",
    # Overlay colours
    "OVERLAY_BORESIGHT",
    "OVERLAY_DETECTION",
    "OVERLAY_GATE",
    "OVERLAY_ESTIMATE",
    "OVERLAY_GT",
    "OVERLAY_GT_TEXT",
    "OVERLAY_HUD_TEXT",
    "OVERLAY_COORD_TEXT",
    "OVERLAY_LEGEND_TEXT",
    # Functions
    "apply_theme",
)
