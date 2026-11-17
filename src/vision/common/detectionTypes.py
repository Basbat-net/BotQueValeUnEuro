"""Internal data of the detectors.

These types never leave the vision module: the robot only sees visionTypes.py.
They also carry debug data (for example the rejected candidates) that only the viewer draws.
"""

from dataclasses import dataclass, field

import numpy as np


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
