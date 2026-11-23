"""Internal data of the detectors.

These types never leave the vision module: the robot only sees visionTypes.py.
They also carry debug data (for example the rejected candidates) that only the apps draw.
"""

from dataclasses import dataclass, field

import numpy as np

from vision.common.visionTypes import DetectionSource, VisionResult, VisionStatus


@dataclass
class ArucoMarker:
    """One ArUco marker found in the image. With the stone ID, it is one face of a stone."""

    markerId: int
    # 4 x 2 array in px, in the order of the printed code, not of the image:
    # top-left, top-right, bottom-right, bottom-left of the code, even if it is upside down
    cornersPx: np.ndarray
    centerPx: tuple[float, float]
    # Mean length of the 4 sides in px. The smaller it is, the farther the marker
    sidePx: float
    # Phase 2b: True only when the camera is calibrated at the size of this image
    hasPose: bool = False
    # Camera frame (x right, y down, z forward). Rotation as a Rodrigues vector, in rad
    rotationVector: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Position of the center of the code, in mm
    translationMm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Mean distance in px between the corners found and the corners the pose predicts
    reprojectionErrorPx: float = 0.0
    # A flat square seen from far can be explained by two poses (tilted one way or the other).
    # The second one is kept so the fusion can choose with what it knows about the stone
    hasAlternativePose: bool = False
    alternativeRotationVector: tuple[float, float, float] = (0.0, 0.0, 0.0)
    alternativeTranslationMm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    alternativeErrorPx: float = 0.0


@dataclass
class ArucoDetection:
    """Everything the ArUco detector found in one image."""

    # Markers with the stone ID: one per visible face, so one stone can give two
    stoneFaces: list[ArucoMarker] = field(default_factory=list)
    # Markers with any other ID (for example the ones of the table): not stones
    otherMarkers: list[ArucoMarker] = field(default_factory=list)
    # Squares that looked like a marker but could not be read. Debug only: 4 x 2 px each
    rejectedCornersPx: list[np.ndarray] = field(default_factory=list)
    processingTimeMs: float = 0.0


@dataclass
class ColorCandidate:
    """One brown blob, measured as a possible stone."""

    # Outline of the blob, N x 2 px
    contourPx: np.ndarray
    centerPx: tuple[float, float]
    areaPx: float
    # Blob area / convex hull area: 1 for a clean box outline
    solidity: float
    # Part of the blob that is the white label: a stone face with its label is above 0
    labelRatio: float = 0.0
    # The rest needs a calibrated camera: where it stands on the floor, in the robot frame
    hasPosition: bool = False
    centerMm: tuple[float, float] = (0.0, 0.0)
    yawDeg: float = 0.0
    # Longest straight part of the bottom edge on the floor, how far the stone reaches behind it
    # (about 110 mm for a long side, 320 mm for an end) and how tall the blob stands
    bottomEdgeMm: float = 0.0
    depthMm: float = 0.0
    heightMm: float = 0.0
    # Relative error between what was measured and the side we think we see: 0 is a perfect match
    sideMatchError: float = 1.0
    # Lying stones piled up in this blob (a quarry is 3), from its height
    stackLevels: int = 1
    # Bottom edge projected on the floor, N x 2 mm (robot x, y): drawn by the apps
    bottomEdgeFloorMm: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    # From 0 to 1: how much it looks like a stone
    score: float = 0.0
    # Empty when accepted; otherwise why it was rejected (debug)
    rejectReason: str = ""


@dataclass
class ColorDetection:
    """Everything the colour + shape detector found in one image."""

    candidates: list[ColorCandidate] = field(default_factory=list)
    rejected: list[ColorCandidate] = field(default_factory=list)
    # Black and white picture of the pixels taken as cardboard (or label), for the apps to show
    maskPx: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint8))
    processingTimeMs: float = 0.0


@dataclass
class StoneEstimate:
    """One stone after the fusion, with everything the apps need to draw it in 3D."""

    # Centre of the box in the robot frame (x forward, y left, z up), in mm
    centerMm: np.ndarray
    # Columns: long side, short side and the third axis, in the robot frame
    rotation: np.ndarray
    yawDeg: float
    # False for a standing stone: its long side is vertical
    isYawDefined: bool
    # 0 on the floor, 1 on top of another stone...
    level: int
    source: DetectionSource
    confidence: float
    # Indexes in ArucoDetection.stoneFaces and ColorDetection.candidates (-1: none)
    faceIndexes: list[int] = field(default_factory=list)
    colorIndex: int = -1
    # True when the two poses of a code were a real doubt and the fusion had to choose
    wasAmbiguous: bool = False


@dataclass
class ProjectedStone:
    """A stone drawn back on the picture: its 8 corners in px (see geometry/boxProjection.py)."""

    stone: StoneEstimate
    cornersPx: np.ndarray
    # False when part of the box is behind the camera: then it is not drawn
    isInFront: bool


@dataclass
class PipelineOptions:
    """Which detectors run. The apps switch them; the robot runs both."""

    useAruco: bool = True
    useColor: bool = True


@dataclass
class VisionDetails:
    """What happened inside the black box for one image: the result plus everything to draw it."""

    result: VisionResult = field(default_factory=lambda: VisionResult(0, 0.0, VisionStatus.NO_FRAME))
    aruco: ArucoDetection = field(default_factory=ArucoDetection)
    color: ColorDetection = field(default_factory=ColorDetection)
    # Stones in the robot frame. Filled even when the camera mount is not measured
    # (provisional positions, to draw them), but then the result has no stones
    stones: list[StoneEstimate] = field(default_factory=list)
    isCalibrationUsable: bool = False
    calibrationText: str = ""
    isMountMeasured: bool = False
    fusionTimeMs: float = 0.0
