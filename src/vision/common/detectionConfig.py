"""Parameters of the detection side: the stone, where the camera is mounted, colour and fusion.

The values live in config/visionConfig.json, never in the code.
The defaults below are only used when a key is missing in the file.
VisionConfig (visionConfig.py) puts these sections together with the rest.
"""

from dataclasses import dataclass


@dataclass
class StoneConfig:
    """Size of a stone: a cardboard box [2027 D.4]."""

    lengthMm: float = 320.0
    # The two short sides are equal: the box is square seen from its end
    widthMm: float = 110.0
    # White square label around the code, centred on each long face (estimated from Figure 5: measure it)
    labelSideMm: float = 104.0


@dataclass
class CameraMountConfig:
    """Where the camera is on the robot, in the robot frame (x forward, y left, z up, origin on the floor).

    Angles are applied in this order: roll about the lens axis, then pitch, then yaw.
    Positive pitch means the camera looks down; positive yaw means it turns to the left.
    """

    # False until someone measures the real mount: the black box then answers NOT_CALIBRATED,
    # so made-up positions never reach the robot. The apps still draw with these values
    isMeasured: bool = False
    xMm: float = 0.0
    yMm: float = 0.0
    zMm: float = 300.0
    pitchDeg: float = 30.0
    yawDeg: float = 0.0
    rollDeg: float = 0.0


@dataclass
class ColorConfig:
    """Colour + shape detector: which pixels are cardboard and which blobs look like a box."""

    # OpenCV HSV ranges: hue 0-179, saturation and value 0-255. Kraft cardboard is a dark orange.
    # Tune them on the real table: the dashboard measures them with a click on a stone
    hueMin: int = 5
    hueMax: int = 25
    saturationMin: int = 60
    saturationMax: int = 255
    valueMin: int = 60
    valueMax: int = 255
    # White of the label: little colour and brighter than the cardboard around it (this many times
    # its mean brightness), so it still works in a darker room. labelValueMin is a floor for very dark images
    labelSaturationMax: int = 60
    labelBrightnessRatio: float = 1.15
    labelValueMin: int = 80
    # Odd sizes in px: blur before the colour test, and the kernel that cleans the mask
    blurKernelPx: int = 5
    cleanKernelPx: int = 7
    # Blobs smaller than this are noise
    minAreaPx: int = 600
    # The bottom edge of a stone on the floor looks more flat than steep in the picture:
    # the ends of the blob outline steeper than this (dy / dx) are vertical edges, not the floor contact
    maxBottomEdgeSlope: float = 1.0
    # Straight parts of the bottom edge are found allowing this much wobble, in mm on the floor
    edgeSimplifyMm: float = 15.0
    # Area of the blob divided by the area of its convex hull: a box is close to 1
    minSolidity: float = 0.8
    # Part of a blob that must be white label to count as "has a label": a far face shows a small one
    minLabelRatio: float = 0.02
    # A flat brown patch on the floor has no height: a real stone stands at least this tall
    minHeightMm: float = 60.0
    # A blob this many stones high or more is a pile (a quarry has 3 [2027 D.4])
    maxStackLevels: int = 3
    # How far a measured side may be from 320 or 110 mm and still count, as a fraction
    sideTolerance: float = 0.35
    # Candidates with a lower score (0 to 1) are rejected
    minScore: float = 0.45
    # Dashboard "pick on image": colour measured in a square of 2 x this + 1 px round the click,
    # and the range opened round it (hue +-, saturation and value - only: brighter is still cardboard)
    pickHalfSidePx: int = 4
    pickHueMargin: int = 8
    pickSaturationMargin: int = 70
    pickValueMargin: int = 80


@dataclass
class FusionConfig:
    """How the detections are merged into stones and how much each one is trusted."""

    # Two ArUco faces closer than this (box centres, in 3D) belong to the same stone
    sameStoneDistanceMm: float = 60.0
    # A colour blob this close to an ArUco stone, on the floor, is the same stone
    colorMatchDistanceMm: float = 150.0
    # The two pose solutions of a marker are a real doubt when the error of the best one is
    # at least this fraction of the other one, and their face directions differ by this angle.
    # Then the physics decides (a resting stone is not tilted). Measured on synthetic side faces:
    # the wrong solution can have the smaller error with a ratio of 0.5
    ambiguityErrorRatio: float = 0.25
    ambiguityMinAngleDeg: float = 10.0
    # Confidence given to each kind of detection (0 to 1)
    arucoConfidence: float = 0.9
    ambiguousConfidence: float = 0.7
    extraFaceBonus: float = 0.05
    colorAgreementBonus: float = 0.05
    colorConfidenceMax: float = 0.5
    # Two colour blobs are pieces of one stone (its middle is covered) when their yaw differs less than this
    # and they are closer than this fraction of the stone length along it (and half a width across)
    pieceYawToleranceDeg: float = 15.0
    pieceAlongFraction: float = 0.8
