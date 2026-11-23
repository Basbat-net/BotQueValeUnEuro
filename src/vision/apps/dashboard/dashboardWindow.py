"""The window of the dashboard: where each panel goes, the toolbar and the keyboard shortcuts.

    ┌ toolbar: mode · pause · step · view · rejected · record · snapshot · fit ─────────────┐
    │ camera with the detections (2D)        │ 3D twin: floor, robot, camera cone, boxes  │
    ├─────────────────────────────────────────┴───────────────────────────────────────────┤
    │ status cards + table of stones          │ cardboard colour (HSV sliders, pick, save) │
    └ status bar: messages ────────────────────────────────────────────────────────────────┘
It only builds widgets: the session connects them to the pipeline.
"""

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from vision.apps.dashboard.cameraPanel import CameraPanel
from vision.apps.dashboard.colorTuningPanel import ColorTuningPanel
from vision.apps.dashboard.stonesPanel import StatusCards, StonesTable, buildLegend
from vision.apps.dashboard.twinPanel import TwinPanel
from vision.common.visionConfig import VisionConfig


class DashboardWindow:
    """The main window and its panels. Created once."""

    def __init__(self, config: VisionConfig, viewCone: list[list[float]]) -> None:
        self.window: QtWidgets.QMainWindow = QtWidgets.QMainWindow()
        self.window.setWindowTitle(f"Vision dashboard · Eurobot 2027 · {config.frameSource.mode.value}")
        self.window.resize(1600, 960)
        self.cameraPanel: CameraPanel = CameraPanel()
        self.twinPanel: TwinPanel = TwinPanel(config.stone, config.aruco.markerSideMm, viewCone)
        self.statusCards: StatusCards = StatusCards({
            "fps": "Images / s", "total": "Process (ms)", "aruco": "ArUco (ms)", "color": "Colour (ms)",
            "stones": "Stones now", "status": "Robot receives", "calibration": "Calibration", "mount": "Camera mount",
        })
        self.stonesTable: StonesTable = StonesTable()
        self.colorPanel: ColorTuningPanel = ColorTuningPanel(config.color)
        self.actions: dict[str, QtGui.QAction] = {}
        self.viewSelector: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.viewSelector.addItems(["Picture", "Colour mask (M)", "ArUco threshold (T)"])
        self._buildToolbar()
        self._buildLayout()

    def show(self) -> None:
        self.window.show()

    def showMessage(self, text: str) -> None:
        """A message in the status bar at the bottom."""
        self.window.statusBar().showMessage(text)

    def addShortcut(self, keys: str, callback: object) -> None:
        """A key that runs callback (a function without arguments) while the window is focused."""
        shortcut: QtGui.QShortcut = QtGui.QShortcut(QtGui.QKeySequence(keys), self.window)
        shortcut.activated.connect(callback)

    def _buildToolbar(self) -> None:
        """Mode buttons (only one checked), playback, view and recording buttons."""
        toolbar: QtWidgets.QToolBar = self.window.addToolBar("Controls")
        toolbar.setMovable(False)
        toolbar.addWidget(QtWidgets.QLabel("Detectors"))
        modeGroup: QtGui.QActionGroup = QtGui.QActionGroup(self.window)
        modes: list[tuple[str, str, str]] = [
            ("aruco", "ArUco (1)", "Only the ArUco detector: exact pose, needs the code to be seen"),
            ("color", "Colour (2)", "Only colour + shape: finds the stone when its code is hidden"),
            ("both", "Both (3)", "Both detectors and the fusion: what the robot receives")]
        for name, text, tip in modes:
            modeGroup.addAction(self._addAction(toolbar, (name, text, tip), isCheckable=True))
        self.actions["both"].setChecked(True)
        toolbar.addSeparator()
        self._addAction(toolbar, ("pause", "Pause (Space)", "Freeze on this image (settings still apply)"), True)
        self._addAction(toolbar, ("step", "Step (N)", "While paused, go to the next image"), False)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("View"))
        self.viewSelector.setToolTip("Picture, what colour takes as cardboard, or what ArUco looks at")
        toolbar.addWidget(self.viewSelector)
        self._addAction(toolbar, ("rejected", "Rejected (X)", "Also draw what each detector threw away, and why"), True)
        toolbar.addSeparator()
        self._addAction(toolbar, ("record", "Record (R)", "Record the raw video in viewer.recordingsFolder"), True)
        self._addAction(toolbar, ("snapshot", "Snapshot (S)", "Save this picture, raw and with drawings"), False)
        self._addAction(toolbar, ("fit", "Fit views (F)", "Back to the whole picture and the default 3D view"), False)

    def _addAction(self, toolbar: QtWidgets.QToolBar, texts: tuple[str, str, str], isCheckable: bool) -> QtGui.QAction:
        """A toolbar button. texts is (name in self.actions, button text, tooltip)."""
        name, text, tip = texts
        action: QtGui.QAction = QtGui.QAction(text, self.window)
        action.setToolTip(tip)
        action.setCheckable(isCheckable)
        toolbar.addAction(action)
        self.actions[name] = action
        return action

    def _buildLayout(self) -> None:
        """Two rows that can be resized: the pictures on top, the numbers and the colour below."""
        twinArea: QtWidgets.QWidget = QtWidgets.QWidget()
        twinLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(twinArea)
        twinLayout.setContentsMargins(0, 0, 0, 0)
        twinLayout.addWidget(buildLegend())
        twinLayout.addWidget(self.twinPanel.widget, stretch=1)
        top: QtWidgets.QSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        top.addWidget(self.cameraPanel.widget)
        top.addWidget(twinArea)
        top.setSizes([800, 800])
        numbers: QtWidgets.QWidget = QtWidgets.QWidget()
        numbersLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(numbers)
        numbersLayout.setContentsMargins(0, 0, 0, 0)
        numbersLayout.addWidget(self.statusCards.widget)
        numbersLayout.addWidget(self.stonesTable.table)
        bottom: QtWidgets.QSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        bottom.addWidget(numbers)
        bottom.addWidget(self.colorPanel.group)
        bottom.setSizes([1050, 550])
        whole: QtWidgets.QSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        whole.addWidget(top)
        whole.addWidget(bottom)
        whole.setSizes([620, 340])
        whole.setContentsMargins(8, 8, 8, 8)
        self.window.setCentralWidget(whole)
