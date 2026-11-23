"""What the dashboard does with each image, without any window: take the newest one, process it, smooth it.

No Qt here, so it can be tested without a screen. The window only shows what this class has.
It reuses the viewer pipeline (the same black box and drawings as the OpenCV viewer).
"""

import numpy as np

from vision.apps.dashboard.twinSmoother import TwinSmoother, TwinStone
from vision.apps.viewer.viewerPipeline import ViewerPipeline
from vision.apps.viewer.viewerState import ViewerFrame, ViewerMode, ViewerState
from vision.common.visionConfig import VisionConfig
from vision.input.latestFrameReader import buildLatestFrameReader


class DashboardPipeline:
    """Reader thread + black box + twin smoothing. Created once."""

    def __init__(self, config: VisionConfig) -> None:
        self.viewerPipeline: ViewerPipeline = ViewerPipeline(config)
        self.reader = buildLatestFrameReader(config.frameSource, config.viewer.playbackFramesPerSecond)
        self.smoother: TwinSmoother = TwinSmoother(config.viewer.twinSmoothing, config.viewer.twinMatchDistanceMm,
                                                   config.viewer.twinGhostSeconds)
        self.state: ViewerState = ViewerState(mode=ViewerMode.BOTH)
        self.image: np.ndarray = np.zeros((0, 0, 3), dtype=np.uint8)
        # Capture time of the current image, in s: the twin ages its ghosts with it (frozen while paused)
        self.imageTimeSeconds: float = 0.0
        self.frame: ViewerFrame = ViewerFrame()
        self.tracks: list[TwinStone] = []
        self.isRefreshRequested: bool = False
        # While paused, only a step lets one new image in (the reader may already hold the next one)
        self.isStepPending: bool = False
        self.processedCount: int = 0

    def start(self) -> str:
        """Starts reading. Returns why it cannot, or empty."""
        if not self.viewerPipeline.isReady:
            return f"wrong detector config: {self.viewerPipeline.lastError}"
        if not self.reader.start():
            return f"could not open the frame source: {self.reader.lastError}"
        return ""

    def update(self) -> bool:
        """Processes a new image, or the same one again after a change of settings. True if there is news."""
        canTakeNewFrame: bool = not self.state.isPaused or self.isStepPending
        isNewFrame, frame = self.reader.takeLatest(0.0) if canTakeNewFrame else (False, None)
        if isNewFrame and frame is not None:
            self.image = frame.image
            self.imageTimeSeconds = frame.timestampMs / 1000
            self.isStepPending = False
        elif not (self.isRefreshRequested and self.image.size > 0):
            return False
        self.isRefreshRequested = False
        self.frame = self.viewerPipeline.process(self.image, self.state, isNewFrame)
        # Also on a refresh: a change of mode or colour range changes the stones of the same image
        self.tracks = self.smoother.update(self.frame.details.stones, self.imageTimeSeconds)
        if isNewFrame:
            self.processedCount += 1
        return True

    def setMode(self, modeName: str) -> None:
        """aruco, color or both: which detectors run."""
        modes: dict[str, ViewerMode] = {"aruco": ViewerMode.ARUCO, "color": ViewerMode.COLOR, "both": ViewerMode.BOTH}
        self.state.mode = modes[modeName]
        # Other detectors, other stones: the twin starts again instead of showing ghosts of the old mode
        self.smoother.clear()
        self.requestRefresh()

    def setPaused(self, isPaused: bool) -> None:
        self.state.isPaused = isPaused
        self.reader.setPaused(isPaused)

    def requestStep(self) -> None:
        """While paused: process exactly one more image."""
        self.isStepPending = True
        self.reader.requestStep()

    def requestRefresh(self) -> None:
        """Process the current image again (a setting changed while paused)."""
        self.isRefreshRequested = True

    def describeSource(self) -> str:
        """Why no new images arrive, or empty while all is well."""
        if self.reader.hasEnded:
            return "end of the video or folder"
        if self.reader.hasFailed or self.reader.lastError != "":
            return f"source problem: {self.reader.lastError}"
        return ""

    def stop(self) -> None:
        self.reader.stop()
