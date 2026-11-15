"""Parameters of the vision module, loaded once at startup.

The values live in config/visionConfig.json, never in the code.
The defaults below are only used when a key is missing in the file.
Relative paths in the file are resolved from the vision/ folder.
The camera calibration lives in its own file, written by the calibration app.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class FrameSourceMode(Enum):
    """Where the images come from. The value is the text written in the JSON file."""

    CAMERA = "camera"
    VIDEO = "video"
    IMAGES = "images"


@dataclass
class FrameSourceConfig:
    """Where the images come from and at which size."""

    mode: FrameSourceMode = FrameSourceMode.CAMERA
    cameraIndex: int = 0
    videoPath: str = ""
    imagesFolder: str = ""
    # Size asked to the camera. Only a request: the driver may give another one
    widthPx: int = 1280
    heightPx: int = 720
    # Time between two pictures when reading a folder (there is no real clock)
    imagesPeriodMs: int = 100


@dataclass
class CalibrationBoardConfig:
    """Chessboard used to calibrate the camera, and how the views are collected."""

    # Inner corners, not squares: a 10x7 squares board has 9x6 inner corners
    innerCornersX: int = 9
    innerCornersY: int = 6
    squareSizeMm: float = 25.0
    requiredViews: int = 20
    # With fewer views the calibration is not computed
    minimumViews: int = 5
    # Camera or video only: time between two saved views, so the board can be moved.
    # In a folder every picture is a view
    captureIntervalMs: int = 1500
    # Sub-pixel refinement of the corners: half side of the search window (11 means 23x23 px)
    subPixHalfWindowPx: int = 11
    # It stops after this many iterations or when a corner moves less than subPixEpsilonPx
    subPixMaxIterations: int = 30
    subPixEpsilonPx: float = 0.001


@dataclass
class VisionConfig:
    """Full configuration, loaded once at startup."""

    frameSource: FrameSourceConfig = field(default_factory=FrameSourceConfig)
    calibrationBoard: CalibrationBoardConfig = field(default_factory=CalibrationBoardConfig)
    calibrationFilePath: str = "config/cameraCalibration.json"
    # Debug windows are only used by the test apps, never on the robot
    showWindow: bool = True
    # The test apps stop after this many frames
    testMaxFrames: int = 300


@dataclass
class CameraCalibration:
    """Intrinsic parameters of one camera, only valid at one resolution.

    Read from calibrationFilePath, not from visionConfig.json. No defaults:
    without a real calibration the distances cannot be measured.
    """

    # 3x3 matrix: focal lengths fx, fy and optical center cx, cy, in px
    cameraMatrix: np.ndarray
    # Lens distortion, a flat array of 5 values: k1, k2, p1, p2, k3
    distCoeffs: np.ndarray
    # 0 means an empty calibration (nothing could be loaded)
    widthPx: int
    heightPx: int
    reprojectionErrorPx: float
