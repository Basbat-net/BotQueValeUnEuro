"""Runs the black box on one image, with the detectors that the viewer mode asks for.

The only file of the viewer that knows the black box. With a calibrated camera it also projects
the stones back on the picture (wire boxes), so the viewer shows what the robot would receive.
"""

import numpy as np

from vision.apps.viewer.viewerState import (
    ViewerFrame,
    ViewerState,
    buildPipelineOptions,
    updateFramesPerSecond,
    updateStats,
)
from vision.blackBoxFactory import buildVisionBlackBox
from vision.common.visionConfig import VisionConfig
from vision.common.visionTypes import FrameInput
from vision.geometry.boxProjection import BoxProjector


class ViewerPipeline:
    """The black box of the viewer. Created once at startup."""

    def __init__(self, config: VisionConfig) -> None:
        self.blackBox = buildVisionBlackBox(config)
        calibration = self.blackBox.arucoDetector.calibration
        self.projector: BoxProjector | None = None if calibration is None else BoxProjector(config, calibration)
        # Why the pipeline cannot run (wrong detector config), for the viewer to print
        self.lastError: str = self.blackBox.lastError
        self.isReady: bool = self.blackBox.arucoDetector.isReady

    def process(self, image: np.ndarray, state: ViewerState, isNewFrame: bool) -> ViewerFrame:
        """Runs the detectors of the current mode. While paused the same image comes back every loop."""
        details = self.blackBox.processWithDetails(FrameInput(image, 0), buildPipelineOptions(state.mode))
        viewerFrame: ViewerFrame = ViewerFrame(details)
        if self.projector is not None and viewerFrame.details.isCalibrationUsable:
            viewerFrame.projectedStones = [self.projector.projectStone(stone) for stone in viewerFrame.details.stones]
        # A paused image is processed again (so a change of settings is seen at once), but counted once
        if isNewFrame:
            updateStats(state.stats, viewerFrame.details.aruco)
            updateFramesPerSecond(state.stats)
        return viewerFrame
