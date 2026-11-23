"""Connects the window with the pipeline: a timer, the buttons, the keys, recording and snapshots.

Every 10 ms the timer asks the pipeline for news; if there is a new image (or a setting changed),
every panel is redrawn. Nothing here waits: the images are read by another thread.
"""

from pyqtgraph.Qt import QtCore

from vision.apps.dashboard.dashboardPipeline import DashboardPipeline
from vision.apps.dashboard.dashboardWindow import DashboardWindow
from vision.apps.viewer.frameRecorder import FrameRecorder
from vision.common.configLoader import saveConfigSection
from vision.common.visionConfig import VisionConfig


class DashboardSession:
    """One run of the dashboard. Created once."""

    def __init__(self, config: VisionConfig, configPath: str, screenshotPath: str, screenshotAfterFrames: int) -> None:
        self.config: VisionConfig = config
        self.configPath: str = configPath
        self.pipeline: DashboardPipeline = DashboardPipeline(config)
        projector = self.pipeline.viewerPipeline.projector
        viewCone: list[list[float]] = [] if projector is None else projector.buildViewCone(
            config.viewer.twinViewConeDepthMm).tolist()
        self.window: DashboardWindow = DashboardWindow(config, viewCone)
        self.recorder: FrameRecorder = FrameRecorder(config.viewer.recordingsFolder)
        self.timer: QtCore.QTimer = QtCore.QTimer()
        self.selectedTrackId: int = 0
        # For the automatic check: save a picture of the window after this many images, then quit
        self.screenshotPath: str = screenshotPath
        self.screenshotAfterFrames: int = screenshotAfterFrames
        self._connectControls()

    def start(self) -> str:
        """Opens the source and the window. Returns why it cannot start, or empty."""
        errorText: str = self.pipeline.start()
        if errorText != "":
            return errorText
        self.window.show()
        self.window.showMessage("Drag the 3D view to turn it, wheel to zoom. Keys: 1 2 3, Space, N, M, T, X, R, S, F, P")
        self.timer.timeout.connect(self._tick)
        self.timer.start(10)
        return ""

    def stop(self) -> None:
        """Stops the timer, the reader and an open recording."""
        self.timer.stop()
        self.recorder.stopRecording()
        self.pipeline.stop()

    def _tick(self) -> None:
        """One turn of the timer: redraw if there is news, and record the new image."""
        countBefore: int = self.pipeline.processedCount
        if not self.pipeline.update():
            sourceText: str = self.pipeline.describeSource()
            if sourceText != "":
                self.window.showMessage(sourceText)
            return
        if self.pipeline.processedCount > countBefore:
            self.recorder.writeFrame(self.pipeline.image)
        self._refreshViews()
        if self.screenshotPath != "" and self.pipeline.processedCount >= self.screenshotAfterFrames:
            self.window.window.grab().save(self.screenshotPath)
            self.stop()
            QtCore.QCoreApplication.quit()

    def _refreshViews(self) -> None:
        """Every panel shows the current image, its stones and its numbers."""
        frame = self.pipeline.frame
        details = frame.details
        self.window.cameraPanel.showFrame(self.pipeline.image, frame, self.pipeline.state)
        self.window.twinPanel.showTwin(self.pipeline.tracks, self.selectedTrackId)
        self.window.stonesTable.showTracks(self.pipeline.tracks, self.selectedTrackId)
        cards = self.window.statusCards
        cards.setCard("fps", f"{self.pipeline.state.stats.framesPerSecond:.1f}")
        cards.setCard("total", f"{details.result.processingTimeMs:.1f}")
        cards.setCard("aruco", f"{details.aruco.processingTimeMs:.1f}")
        cards.setCard("color", f"{details.color.processingTimeMs:.1f}")
        cards.setCard("stones", str(len(details.stones)))
        statusName: str = details.result.status.name
        cards.setCard("status", statusName, "good" if statusName == "OK" else "warning")
        cards.setCard("calibration", "OK" if details.isCalibrationUsable else "missing",
                      "good" if details.isCalibrationUsable else "bad")
        cards.setCard("mount", "measured" if details.isMountMeasured else "NOT measured",
                      "good" if details.isMountMeasured else "warning")

    def _connectControls(self) -> None:
        """Buttons, keys and panel callbacks to their handlers."""
        actions = self.window.actions
        for modeName in ("aruco", "color", "both"):
            actions[modeName].triggered.connect(lambda checked=False, name=modeName: self.pipeline.setMode(name))
        actions["pause"].toggled.connect(self.pipeline.setPaused)
        actions["step"].triggered.connect(self.pipeline.requestStep)
        actions["rejected"].toggled.connect(self._setShowRejected)
        actions["record"].toggled.connect(self._setRecording)
        actions["snapshot"].triggered.connect(self._saveSnapshot)
        actions["fit"].triggered.connect(self._fitViews)
        self.window.viewSelector.currentIndexChanged.connect(self._setView)
        self.window.colorPanel.onRangeChanged = self.pipeline.requestRefresh
        self.window.colorPanel.saveButton.clicked.connect(self._saveColorRange)
        self.window.cameraPanel.onImageClicked = self._handleImageClick
        self.window.stonesTable.onTrackSelected = self._selectTrack
        shortcuts: dict[str, object] = {
            "1": actions["aruco"].trigger, "2": actions["color"].trigger, "3": actions["both"].trigger,
            "Space": actions["pause"].toggle, "N": actions["step"].trigger, "X": actions["rejected"].toggle,
            "R": actions["record"].toggle, "S": actions["snapshot"].trigger, "F": actions["fit"].trigger,
            "M": lambda: self._toggleView(1), "T": lambda: self._toggleView(2),
            "P": self.window.colorPanel.pickButton.toggle, "Q": self.window.window.close,
        }
        for keys, callback in shortcuts.items():
            self.window.addShortcut(keys, callback)

    def _setShowRejected(self, isShown: bool) -> None:
        self.pipeline.state.showRejected = isShown
        self.pipeline.requestRefresh()

    def _setView(self, viewIndex: int) -> None:
        """0 the picture, 1 the colour mask, 2 the ArUco threshold view."""
        self.pipeline.state.showMask = viewIndex == 1
        self.pipeline.state.showThreshold = viewIndex == 2
        self.pipeline.requestRefresh()

    def _toggleView(self, viewIndex: int) -> None:
        isShown: bool = self.window.viewSelector.currentIndex() == viewIndex
        self.window.viewSelector.setCurrentIndex(0 if isShown else viewIndex)

    def _setRecording(self, isOn: bool) -> None:
        """Starts or stops a raw video (no drawings) in viewer.recordingsFolder."""
        image = self.pipeline.image
        if isOn and image.size > 0:
            isStarted: bool = self.recorder.startRecording((image.shape[1], image.shape[0]),
                                                           max(self.pipeline.state.stats.framesPerSecond, 1.0))
            self.window.showMessage("recording" if isStarted else self.recorder.lastError)
        elif not isOn:
            self.window.showMessage(f"video saved: {self.recorder.stopRecording()}")

    def _saveSnapshot(self) -> None:
        isSaved, fileName = self.recorder.saveSnapshot(self.pipeline.image, self.window.cameraPanel.lastCanvas)
        self.window.showMessage(f"snapshot saved: {fileName}" if isSaved else self.recorder.lastError)

    def _fitViews(self) -> None:
        self.window.cameraPanel.fitView()
        self.window.twinPanel.resetView()

    def _handleImageClick(self, xPx: float, yPx: float) -> None:
        """With Pick on, a click measures the colour of the cardboard under it."""
        if self.window.colorPanel.pickButton.isChecked():
            self.window.showMessage(self.window.colorPanel.pickFrom(self.pipeline.image, xPx, yPx))

    def _saveColorRange(self) -> None:
        isSaved: bool = saveConfigSection(self.configPath, "color", self.window.colorPanel.readValues())
        self.window.showMessage(f"colour range saved in {self.configPath}" if isSaved else "could not save the config")

    def _selectTrack(self, trackId: int) -> None:
        self.selectedTrackId = trackId
        self.window.twinPanel.showTwin(self.pipeline.tracks, trackId)
