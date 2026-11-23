"""Builds the vision black box from the config: the only place that knows how its parts are made.

Kept apart from visionBlackBox.py so the box only knows its parts, not the config files
(and each file stays within the 6 imports of the team rules).
"""

from vision.aruco.arucoStoneDetector import ArucoStoneDetector
from vision.color.colorShapeDetector import ColorShapeDetector
from vision.common.configLoader import loadCameraCalibration
from vision.common.visionConfig import CameraCalibration, VisionConfig
from vision.fusion.stoneFusion import StoneFusion
from vision.visionBlackBox import VisionBlackBox


def buildVisionBlackBox(config: VisionConfig, calibration: CameraCalibration | None = None) -> VisionBlackBox:
    """The black box ready to use. Without a calibration given, it reads calibrationFilePath.

    A missing or broken calibration file is not an error here: the box then answers NOT_CALIBRATED.
    """
    if calibration is None:
        isLoaded, loadedCalibration = loadCameraCalibration(config.calibrationFilePath)
        calibration = loadedCalibration if isLoaded else None
    return VisionBlackBox(
        ArucoStoneDetector(config.aruco, calibration),
        ColorShapeDetector(config, calibration),
        StoneFusion(config),
        config.cameraMount.isMeasured,
    )
