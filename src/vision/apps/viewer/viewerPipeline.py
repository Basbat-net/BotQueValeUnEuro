"""Runs the detectors that the viewer mode asks for, on one image.

The only file of the viewer that knows the detectors. It also loads the camera calibration,
to show if it can be used: the pose in mm (phase 2b) will need it.
"""

import numpy as np

from vision.apps.viewer.viewerState import (
    ViewerFrame,
    ViewerMode,
    ViewerState,
    updateFramesPerSecond,
    updateStats,
)
from vision.aruco.arucoStoneDetector import ArucoStoneDetector
from vision.common.configLoader import loadCameraCalibration
from vision.common.visionConfig import CameraCalibration, VisionConfig


class ViewerPipeline:
    """Detectors of the viewer. Created once at startup."""

    def __init__(self, config: VisionConfig) -> None:
        self.arucoDetector: ArucoStoneDetector = ArucoStoneDetector(config.aruco)
        isCalibrationLoaded, calibration = loadCameraCalibration(config.calibrationFilePath)
        self.isCalibrationLoaded: bool = isCalibrationLoaded
        self.calibration: CameraCalibration = calibration
        # Why the pipeline cannot run (wrong detector config), for the viewer to print
        self.lastError: str = self.arucoDetector.lastError
        self.isReady: bool = self.arucoDetector.isReady

    def process(self, image: np.ndarray, state: ViewerState, isNewFrame: bool) -> ViewerFrame:
        """Runs the detectors of the current mode. While paused the same image comes back every loop."""
        viewerFrame: ViewerFrame = ViewerFrame()
        if state.mode in (ViewerMode.ARUCO, ViewerMode.BOTH):
            viewerFrame.aruco = self.arucoDetector.detect(image)
        viewerFrame.calibrationText, viewerFrame.isCalibrationUsable = self._describeCalibration(image)
        # A paused image is processed again (so a change of settings is seen at once), but counted once
        if isNewFrame:
            updateStats(state.stats, viewerFrame.aruco)
            updateFramesPerSecond(state.stats)
        return viewerFrame

    def _describeCalibration(self, image: np.ndarray) -> tuple[str, bool]:
        """Text for the status bar and whether the calibration fits this image size."""
        imageHeight, imageWidth = image.shape[:2]
        if not self.isCalibrationLoaded:
            return "NOT CALIBRATED: distances in mm need the calibration (phase 2b)", False
        calibrationSize: str = f"{self.calibration.widthPx}x{self.calibration.heightPx}"
        if (self.calibration.widthPx, self.calibration.heightPx) != (imageWidth, imageHeight):
            return f"calibration made at {calibrationSize}, image is {imageWidth}x{imageHeight}: not usable", False
        errorText: str = f"{self.calibration.reprojectionErrorPx:.2f}"
        return f"calibrated at {calibrationSize} (reprojection error {errorText} px)", True
