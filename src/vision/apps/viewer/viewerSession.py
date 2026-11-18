"""Main loop of the viewer: read an image, run the detectors, show the result, read a key."""

import numpy as np

from vision.apps.viewer.viewerPipeline import ViewerPipeline
from vision.apps.viewer.viewerScreen import ViewerScreen
from vision.apps.viewer.viewerState import ViewerFrame, ViewerState
from vision.common.visionConfig import VisionConfig
from vision.input.frameSource import FrameSource


class ViewerSession:
    """One run of the viewer, from opening the source to closing the window. Created once."""

    def __init__(self, config: VisionConfig) -> None:
        self.config: VisionConfig = config
        self.frameSource: FrameSource = FrameSource(config.frameSource)
        self.pipeline: ViewerPipeline = ViewerPipeline(config)
        self.screen: ViewerScreen = ViewerScreen("visionViewer", config.viewer.recordingsFolder)
        self.state: ViewerState = ViewerState()

    def run(self) -> str:
        """Shows images until the user quits. Returns why it stopped, or empty if the user quit."""
        if not self.config.showWindow:
            return "the viewer needs a screen: showWindow is false or there is no display"
        if not self.pipeline.isReady:
            return f"wrong detector config: {self.pipeline.lastError}"
        if not self.frameSource.open():
            return f"could not open the frame source: {self.frameSource.lastError}"
        currentImage: np.ndarray = np.zeros((0, 0, 3), dtype=np.uint8)
        errorText: str = ""
        isRunning: bool = True
        while isRunning and errorText == "":
            isNewFrame, currentImage, errorText = self._readNextFrame(currentImage)
            if errorText == "":
                viewerFrame: ViewerFrame = self.pipeline.process(currentImage, self.state, isNewFrame)
                isRunning = self.screen.update(currentImage, viewerFrame, self.state, isNewFrame)
        self.frameSource.close()
        self.screen.close()
        return errorText

    def _readNextFrame(self, currentImage: np.ndarray) -> tuple[bool, np.ndarray, str]:
        """A new image when playing, or one step while paused. Returns (isNewFrame, image, errorText)."""
        if self.state.isPaused and not self.state.isStepRequested:
            return False, currentImage, ""
        self.state.isStepRequested = False
        isRead, frame = self.frameSource.read()
        if isRead:
            return True, frame.image, ""
        if self.frameSource.hasEnded() and currentImage.size > 0:
            # A recorded source ran out: stay on the last image, so it can still be looked at
            self.state.isPaused = True
            self.state.message = "end of the video or folder: q to quit"
            return False, currentImage, ""
        reason: str = self.frameSource.lastError if self.frameSource.lastError != "" else "no image"
        return False, currentImage, f"reading stopped: {reason}"
