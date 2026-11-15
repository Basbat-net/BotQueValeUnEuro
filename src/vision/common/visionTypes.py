"""Data contract of the vision black box.

Everything that enters or leaves the vision module is defined here.
VisionResult, StoneDetection and the two enums will reach the rest of the robot (the ESP32)
through a message format still to be agreed. FrameInput never leaves the Python program.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class VisionStatus(Enum):
    """Result state of one processing cycle."""

    # These numbers will be the codes sent to the robot: never renumber, only add at the end
    OK = 0
    NO_FRAME = 1
    NOT_CALIBRATED = 2
    CONFIG_ERROR = 3


class DetectionSource(Enum):
    """Which detector found the stone."""

    # Codes sent to the robot too: never renumber, only add at the end
    ARUCO = 0
    COLOR = 1
    BOTH = 2


@dataclass
class FrameInput:
    """Input of the black box: one image and when it was captured."""

    # BGR color image as given by OpenCV: height x width x 3, uint8
    image: np.ndarray
    # Capture time in ms. Which clock (system time or one that only moves forward) is still
    # to be agreed with the team
    timestampMs: int


@dataclass
class StoneDetection:
    """One stone, expressed in the robot frame (x forward, y left)."""

    xMm: float
    yMm: float
    yawDeg: float
    # From 0 (pure guess) to 1 (certain)
    confidence: float
    source: DetectionSource


@dataclass
class VisionResult:
    """Output of the black box for one frame.

    timestampMs is copied from the FrameInput, so the robot knows how old the data is.
    stones is always empty when status is not OK, and may be empty when it is.
    """

    timestampMs: int
    processingTimeMs: float
    status: VisionStatus
    stones: list[StoneDetection] = field(default_factory=list)
