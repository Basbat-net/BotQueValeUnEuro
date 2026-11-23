"""The numbers of the dashboard: status cards (speed, calibration...) and the table of stones.

The table shows the twin of each stone (smoothed, with its track number). The robot gets the raw
values of each image, which differ from these by a few mm at most.
"""

from collections.abc import Callable

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from vision.apps.dashboard.dashboardStyle import DashboardColors
from vision.apps.dashboard.twinSmoother import TwinStone
from vision.geometry.poseTransforms import computeYawDeg, snapToFloor


class StatusCards:
    """A row of small cards: a title and a big value each. Created once."""

    def __init__(self, cardTitles: dict[str, str]) -> None:
        self.widget: QtWidgets.QWidget = QtWidgets.QWidget()
        layout: QtWidgets.QGridLayout = QtWidgets.QGridLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        cardsPerRow: int = 4
        self.values: dict[str, QtWidgets.QLabel] = {}
        for index, (key, title) in enumerate(cardTitles.items()):
            card: QtWidgets.QFrame = QtWidgets.QFrame()
            card.setObjectName("card")
            cardLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(card)
            cardLayout.setContentsMargins(12, 8, 12, 8)
            titleLabel: QtWidgets.QLabel = QtWidgets.QLabel(title)
            titleLabel.setObjectName("cardTitle")
            cardLayout.addWidget(titleLabel)
            self.values[key] = QtWidgets.QLabel("-")
            self.values[key].setObjectName("cardValue")
            cardLayout.addWidget(self.values[key])
            layout.addWidget(card, index // cardsPerRow, index % cardsPerRow)

    def setCard(self, key: str, text: str, level: str = "normal") -> None:
        """Changes one value. level: normal, good, warning or bad (its colour)."""
        colors: dict[str, str] = {"normal": DashboardColors.text, "good": DashboardColors.good,
                                  "warning": DashboardColors.warning, "bad": DashboardColors.bad}
        self.values[key].setText(text)
        self.values[key].setStyleSheet(f"color: {colors.get(level, DashboardColors.text)};")


class StonesTable:
    """The table of the stones of the twin. Selecting a row highlights its box in 3D. Created once."""

    def __init__(self) -> None:
        headers: list[str] = ["#", "Source", "x (mm)", "y (mm)", "Yaw (deg)", "Level", "Confidence"]
        self.table: QtWidgets.QTableWidget = QtWidgets.QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # Set by the session: what to do when a stone is selected (its track number, 0 = none)
        self.onTrackSelected: Callable[[int], None] | None = None
        self.shownTrackIds: list[int] = []
        self.table.itemSelectionChanged.connect(self._handleSelection)

    def showTracks(self, tracks: list[TwinStone], selectedTrackId: int) -> None:
        """Fills the table: seen stones first, lost ones (ghosts) after, in grey."""
        ordered: list[TwinStone] = sorted(tracks, key=lambda track: (track.isGhost, track.trackId))
        sourceColors: dict[str, str] = {"ARUCO": DashboardColors.aruco, "COLOR": DashboardColors.color,
                                        "BOTH": DashboardColors.both}
        self.table.blockSignals(True)
        self.table.setRowCount(len(ordered))
        for row, track in enumerate(ordered):
            snapped, _, verticalIndex = snapToFloor(track.rotation)
            isYawDefined, yawDeg = computeYawDeg(snapped, verticalIndex)
            cells: list[str] = [str(track.trackId), track.source.name, f"{track.centerMm[0]:.0f}",
                                f"{track.centerMm[1]:.0f}", f"{yawDeg:+.1f}" if isYawDefined else "standing",
                                str(track.level), "lost" if track.isGhost else f"{track.confidence:.0%}"]
            textColor: str = DashboardColors.muted if track.isGhost else DashboardColors.text
            for column, text in enumerate(cells):
                item: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                isSourceCell: bool = column == 1 and not track.isGhost
                item.setForeground(QtGui.QColor(sourceColors.get(track.source.name, textColor) if isSourceCell
                                                else textColor))
                self.table.setItem(row, column, item)
            if track.trackId == selectedTrackId:
                self.table.selectRow(row)
        self.shownTrackIds = [track.trackId for track in ordered]
        self.table.blockSignals(False)

    def _handleSelection(self) -> None:
        """Passes on the track number of the selected row."""
        rows: list[int] = sorted({index.row() for index in self.table.selectedIndexes()})
        selectedTrackId: int = self.shownTrackIds[rows[0]] if rows and rows[0] < len(self.shownTrackIds) else 0
        if self.onTrackSelected is not None:
            self.onTrackSelected(selectedTrackId)


def buildLegend() -> QtWidgets.QLabel:
    """One line that says what each colour of the boxes means, for the top of the 3D view."""
    colors = DashboardColors
    entries: list[tuple[str, str]] = [(colors.aruco, "ArUco"), (colors.color, "colour only"), (colors.both, "both"),
                                      (colors.muted, "lost (ghost)"), ("#ffd60a", "selected")]
    squares: str = "&nbsp;&nbsp;".join(f'<span style="color:{color}">&#9632;</span> {name}' for color, name in entries)
    legend: QtWidgets.QLabel = QtWidgets.QLabel(f"3D twin (robot frame, mm) &nbsp; {squares} &nbsp; "
                                                f'<span style="color:{colors.muted}">drag: turn · wheel: zoom</span>')
    legend.setTextFormat(QtCore.Qt.TextFormat.RichText)
    legend.setStyleSheet(f"padding: 6px; background: {colors.panel};")
    return legend
