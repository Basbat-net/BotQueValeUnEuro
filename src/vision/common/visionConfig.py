"""Parameters of the vision module, loaded once at startup.

The values live in config/visionConfig.json, never in the code.
The defaults below are only used when a key is missing in the file.
Relative paths in the file are resolved from the vision/ folder.
The camera calibration lives in its own file, written by the calibration app.
The sections of the detection and of the output live in detectionConfig.py and outputConfig.py.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from vision.common.detectionConfig import CameraMountConfig, ColorConfig, FusionConfig, StoneConfig
from vision.common.outputConfig import OutputConfig, SenderConfig


class FrameSourceMode(Enum):
    """Where the images come from. The value is the text written in the JSON file."""

    CAMERA = "camera"
    VIDEO = "video"
    IMAGES = "images"
    # Images sent by the robot over the network (MJPEG over HTTP, RTSP...): a cut is a failure, not an end
    STREAM = "stream"


class MarkerAxis(Enum):
    """Axis of the printed code that runs along the 320 mm side of the stone."""

    X = "x"
    Y = "y"


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
    # Camera mode: format asked to a USB camera, 4 letters. "MJPG" lets most webcams give 30 images/s
    # at 1280 x 720 (the default raw format gave 10 on the team PC). Empty keeps the driver default
    fourcc: str = "MJPG"
    # Time between two pictures when reading a folder (there is no real clock)
    imagesPeriodMs: int = 100
    # Stream mode: address of the video sender, for example http://robot.local:8080/video
    streamUrl: str = ""
    # Stream mode: opening or reading takes at most this long, so a dead stream never blocks
    streamTimeoutMs: int = 3000
    # Stream mode: after a failed reconnection, wait this long before the next try
    reconnectDelayMs: int = 1000


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
class ArucoConfig:
    """ArUco marker printed on the stones and how it is searched."""

    # Name of an OpenCV predefined dictionary (cv2.aruco.DICT_...)
    dictionaryName: str = "DICT_4X4_50"
    # Every stone carries the same ID [2027 D.4]: it says "this is a stone", not which one
    stoneMarkerId: int = 13
    # Side of the black square, not of the white label. Only used for the pose (phase 2b).
    # 80 mm is an estimate from the picture in the rules: measure the printed marker
    markerSideMm: float = 80.0
    # Refines the corners to sub-pixel precision: a bit slower, but the pose depends on it
    useSubPixRefinement: bool = True
    # In the picture of the rules (Figure 5) the x axis of the code runs along the long side, on every face
    markerLongAxis: MarkerAxis = MarkerAxis.X


@dataclass
class ViewerConfig:
    """Options of the viewer app. Never used on the robot."""

    # Where the viewer saves videos and pictures. Empty means recording is turned off.
    # Keep it outside the repo: videos are heavy and are not committed
    recordingsFolder: str = ""
    # Dashboard: a recorded video plays at this rate (0 = as fast as it can be processed)
    playbackFramesPerSecond: float = 30.0
    # Dashboard 3D twin, only for drawing (the robot gets the raw stones): how much of the old position
    # stays each image (0 = raw), how far a stone may jump and still be the same, how long a lost one stays
    twinSmoothing: float = 0.5
    twinMatchDistanceMm: float = 150.0
    twinGhostSeconds: float = 1.0
    # Length of the camera cone drawn in the 3D twin
    twinViewConeDepthMm: float = 400.0


@dataclass
class VisionConfig:
    """Full configuration, loaded once at startup."""

    frameSource: FrameSourceConfig = field(default_factory=FrameSourceConfig)
    calibrationBoard: CalibrationBoardConfig = field(default_factory=CalibrationBoardConfig)
    aruco: ArucoConfig = field(default_factory=ArucoConfig)
    viewer: ViewerConfig = field(default_factory=ViewerConfig)
    stone: StoneConfig = field(default_factory=StoneConfig)
    cameraMount: CameraMountConfig = field(default_factory=CameraMountConfig)
    color: ColorConfig = field(default_factory=ColorConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    sender: SenderConfig = field(default_factory=SenderConfig)
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
