"""Look of the dashboard: a dark theme, the colours of each source and the style sheet (QSS) of Qt.

All colours live here, so the 2D view, the 3D twin and the panels speak the same language:
green = ArUco, orange = colour only, cyan = both detectors, grey = lost (ghost), yellow = selected.
"""

from pyqtgraph.Qt import QtWidgets


class DashboardColors:
    """Colours of the dashboard, as #rrggbb. Class attributes, not globals (team rule)."""

    background: str = "#111318"
    panel: str = "#1a1d24"
    raised: str = "#232733"
    border: str = "#2c3240"
    text: str = "#e6e8ee"
    muted: str = "#8a93a6"
    accent: str = "#22c3e6"
    good: str = "#4cd964"
    warning: str = "#ffb340"
    bad: str = "#ff5a52"
    aruco: str = "#4cd964"
    color: str = "#ff9500"
    both: str = "#22c3e6"


def buildStyleSheet() -> str:
    """The Qt style sheet of the whole window (like CSS, applied to every widget)."""
    colors = DashboardColors
    return f"""
    QWidget {{ background: {colors.background}; color: {colors.text}; font-size: 13px; }}
    QToolBar {{ background: {colors.panel}; border: none; border-bottom: 1px solid {colors.border}; spacing: 6px;
               padding: 6px; }}
    QLabel {{ background: transparent; }}
    QToolBar QLabel {{ color: {colors.muted}; padding: 0 4px; }}
    QToolButton, QPushButton {{ background: {colors.raised}; border: 1px solid {colors.border}; border-radius: 6px;
                               padding: 5px 12px; }}
    QToolButton:hover, QPushButton:hover {{ border-color: {colors.accent}; }}
    QToolButton:checked, QPushButton:checked {{ background: {colors.accent}; color: {colors.background};
                                               border-color: {colors.accent}; font-weight: bold; }}
    QComboBox {{ background: {colors.raised}; border: 1px solid {colors.border}; border-radius: 6px; padding: 4px 8px; }}
    QGroupBox {{ background: {colors.panel}; border: 1px solid {colors.border}; border-radius: 8px; margin-top: 14px;
                padding: 10px 8px 8px 8px; font-weight: bold; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {colors.accent}; }}
    QFrame#card {{ background: {colors.panel}; border: 1px solid {colors.border}; border-radius: 8px; }}
    QLabel#cardTitle {{ background: transparent; color: {colors.muted}; font-size: 11px; }}
    QLabel#cardValue {{ background: transparent; font-size: 18px; font-weight: bold; }}
    QTableWidget {{ background: {colors.panel}; border: 1px solid {colors.border}; border-radius: 8px;
                   gridline-color: {colors.border}; selection-background-color: {colors.raised}; }}
    QHeaderView::section {{ background: {colors.raised}; color: {colors.muted}; border: none; padding: 5px; }}
    QSlider::groove:horizontal {{ height: 6px; background: {colors.raised}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {colors.accent}; width: 14px; margin: -5px 0; border-radius: 7px; }}
    QSplitter::handle {{ background: {colors.border}; }}
    QStatusBar {{ background: {colors.panel}; color: {colors.muted}; border-top: 1px solid {colors.border}; }}
    """


def applyStyle(application: QtWidgets.QApplication) -> None:
    """Applies the dark theme to every window of the application."""
    application.setStyle("Fusion")
    application.setStyleSheet(buildStyleSheet())
